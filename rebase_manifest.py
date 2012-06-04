#!/usr/bin/env python

import logging
import optparse
import os
import re
from shutil import copy, rmtree
import sys
from xml.parsers.expat import ExpatError

from find_reviewers import FindReviewers, AddReviewersError
from gerrit import GerritSshConfigError
import getmanifest
import git
from include_exclude_matcher import IncludeExcludeMatcher
from manifest import RepoXmlManifest, ManifestParseError, ManifestError
import processes
from repo import Repo, RepoError
import semcutil

# Global variables
CLONE_DIR = "clone"
#Gerrit server URL
GERRIT_URL = "review.sonyericsson.net"
ASW_MANIFEST = "platform/manifest"
AMSS_MANIFEST = "platform/amssmanifest"
AMSS_PACKAGE = "util/data/amssmanifest.xml"
MANIFEST_PATH = ".repo/manifests/default.xml"
STR_REVISION = "revision"


class GerritError(Exception):
    """Class to handle exceptions in Gerrit functionalities"""


class Gerrit:
    """Gerrit functionalities to support rebase"""
    def __init__(self, gerrit_username=None):
        """Initilization method

        Creates 'FindReviewers' object. 'FindReviewers' internally
        creates Gerrit connection.

        Exception raised: GerritError
        Exception case:
            Gerrit config error.

        """
        try:
            self.finder = FindReviewers(user=gerrit_username)
            self.gerrit = self.finder.gerrit
            self.username = self.gerrit.username
        except GerritSshConfigError, err:
            raise GerritError("Gerrit config error: %s" % err)

    def upload_gerrit(self, git_name, branch, path=".", reviewers=[],
                      force_push=False, review_msg=None):
        """Uploads the change to Gerrit

        Arguments:
            git_name: name of the git.
            branch: branch to which the change need to be pushed.
            path: path where the git is cloned and change is committed.
            reviewers: list containing email-ids to be added as reviewers.
            force_push: True/False. Flag to enable force push.

        The change is pushed to Gerrit for review. If any reviewers are
        there in the list 'reviewers', they are added as reviewers to the
        new gerrit change.

        Return:
        Gerrit review link if link present
        Empty string if review link not found

        Exception raised: GerritError
        Exception cases:
            Failed to push the change.
            Failed to retrieve the commit id of the change.

        Exception raised: AddReviewersError
        Exception case:
            Failed to add reviewers.

        """
        try:
            rev_path = "ssh://%s@%s:29418/%s.git" % \
                           (self.username, GERRIT_URL, git_name)
            refs = "HEAD:refs/for/%s" % branch
            command = ["git", "push"]
            if force_push:
                command += ["-f"]
            command += [rev_path, refs]
            (ret, res, err) = processes.run_cmd(command, path=path)
        except processes.ChildExecutionError, err:
            raise GerritError("Failed to push the change: %s" % err)

        result = ""
        match = re.search("https?://%s/([0-9]+)" % GERRIT_URL, err)
        if match:
            #collect the Gerrit ID
            result = match.group(0)
            # Add reviewers to the Gerrit change.
            try:
                (ret, commit_id, err) = \
                    processes.run_cmd("git", "rev-parse", "HEAD",
                                      path=path)
            except processes.ChildExecutionError, err:
                raise GerritError("Failed to retrieve commit ID for "
                                  "change %s: %s" % (result, err))
            if reviewers:
                self.finder.add(commit_id.strip(), reviewers)
            if review_msg:
                try:
                    self.gerrit.review_patchset(commit_id.strip(),
                                                message=review_msg)
                except processes.ChildExecutionError, err:
                    raise GerritError("Failed to add review message for "
                                      "change %s: %s" % (result, err))
        return result


class UpdateMerge:
    """Update manifest and Merge component branches

    Manifest rebase supports ASW and AMSS manifest files according to the
    option provided. By default, rebase is done for ASW manifest.
    By default, component rebase is done for gits those are having
    revision same as target branch. Additional branches are added
    depending upon the options provided by user. Component rebases use
    "git merge".
    Upload the changes to Gerrit is added as an option.

    """

    def __init__(self, options, log):
        """Initilization method

        Arguments:
            options: 'optparse' object containing input options.
            log: 'logging' object for logging.

        Clone/download the manifest files needed and creates parsed manifest
        xml objects.

        Exception raised: UpdateMergeError
        Exception cases:
            Workspace already exists.
            Error cloning 'platform/manifest' git.
            Error downloading base static manifest.
            Error parsing manifest file.

        """

        self.options = options
        self.gerrit_handler = Gerrit(self.options.gerrit_user)
        self.revision_field = "XB-SEMC-Manifest-Revision"
        self.branch_field = "XB-SEMC-Manifest-Branch"
        self.amss_revision_field = "Modem-Manifest-Revision"
        self.amss_branch_field = "Modem-Manifest-Branch"
        self.log = log.logger
        self.reviewers = []

        # Save the list of gits and respective Gerrit URLs to file.
        # Enable only if upload to Gerrit is enabled.
        if self.options.file_report and not self.options.flag_upload:
            self.log.info("Disabling -f/--file-report as -u/--upload option "
                          "is not defined.")
            self.options.file_report = None
        if self.options.force_push and not self.options.flag_upload:
            self.log.info("Disabling --force-push as -u/--upload option "
                          "is not defined.")
            self.options.force_push = False

        if self.options.no_reviewers:
            self.log.info("Disabled adding reviewers listed in source commit."
                          "\nStill reviewers provided by `--reviewer` option "
                          "will be added.")
        if self.options.reviewers_on_conflict:
            self.log.info("Reviewers will be added only for merge conflict "
                          "commits.\nReviewers provided by `--reviewer` "
                          "option will be added for all commits.")
            self.options.no_reviewers = True

        current_dir = os.getcwd()
        options.workspace = os.path.normpath(os.path.join(current_dir,
                                                          options.workspace))
        if not os.path.isdir(options.workspace):
            try:
                os.makedirs(options.workspace)
            except EnvironmentError, e:
                raise UpdateMergeError("Failed to create workspace: %s: %s" %
                                       (e.strerror, e.filename))

        self.clone_dir = os.path.normpath(os.path.join(options.workspace,
                                                       CLONE_DIR))
        if not os.path.exists(self.clone_dir):
            os.mkdir(self.clone_dir)
        else:
            self.log.error("Cleanup workspace and run again")
            raise UpdateMergeError("Cleanup workspace and run again")

        self.exclude_git_matcher = \
            IncludeExcludeMatcher(options.exclude_git, None)

        self.include_git_matcher = \
            IncludeExcludeMatcher(options.include_git, None)

        self.include_branch_matcher = \
            IncludeExcludeMatcher(options.component_branch, None)

        self.manifest_git_path = ASW_MANIFEST
        self.manifest_file_path = MANIFEST_PATH
        if options.amss_version:
            self.manifest_git_path = AMSS_MANIFEST

        # Variable to store the path of static manifest (source) file
        self.source_file = os.path.normpath(
            os.path.join(options.workspace, "manifest_static.xml"))
        # Variable to store the path of deafult manifest (source) file
        self.source_default = os.path.normpath(os.path.join(options.workspace,
                                                            "ref_default.xml"))
        # Temporary output file created in the workspace directory
        self.output_file = os.path.normpath(os.path.join(options.workspace,
                                                         "default_new.xml"))
        # Final output file inside the manifest git directory
        self.target_file = os.path.normpath(
            os.path.join(self.clone_dir, self.manifest_file_path))

        try:
            self.log.info("Initializing repo for %s" % options.target_branch)
            self.repo_handler = Repo(options.target_branch,
                                     self.manifest_git_path,
                                     self.clone_dir)
        except RepoError, err:
            self.log.error(str(err))
            raise UpdateMergeError(str(err))

        try:
            (ret, res, err) = processes.run_cmd("semc-swversion-convert",
                                                "%s" % options.source_version)
            self.flag_sw_ver = True
        except processes.ChildExecutionError, err:
            self.flag_sw_ver = False
        if self.flag_sw_ver and options.amss_version:
            try:
                cmd = ["repository", "list", options.source_version, "-g",
                       "fw-.*modem"]
                if options.repo_url:
                    cmd += ["-ru", options.repo_url]
                (ret, res, err) = processes.run_cmd(cmd)
            except processes.ChildExecutionError, err:
                self.log.critical("Failed to get modem package for label "
                                  "%s: %s" % (options.source_version, err))
                self.clean_up()
                raise UpdateMergeError("Failed to get modem package for label "
                                       "%s: %s" % (options.source_version,
                                                   err))
            packages = filter(lambda a: options.amss_version in a,
                              res.splitlines())
            if len(packages):
                package_name = packages[0].split()[0]
            else:
                self.log.critical("No package found with revision %s" %
                                  options.amss_version)
                self.clean_up()
                raise UpdateMergeError("No package found with revision %s" %
                                       options.amss_version)
            self.log.info("Downloading base static manifest")
            try:
                getmanifest.get_file_from_package(options.source_version,
                                                  package_name,
                                                  self.source_file,
                                                  AMSS_PACKAGE,
                                                  repo_url=options.repo_url)
            except getmanifest.GetManifestError, err:
                self.log.critical("Failed to download manifest: %s" % err)
                self.clean_up()
                raise UpdateMergeError("Failed to download manifest: %s" % err)
        # Download source build-metadata package and extract the
        # static manifest
        elif self.flag_sw_ver:
            self.log.info("Downloading base static manifest")
            try:
                getmanifest.get_manifest(options.source_version,
                                         self.source_file,
                                         repo_url=options.repo_url)
            except getmanifest.GetManifestError, err:
                self.log.critical("Failed to download manifest: %s" % err)
                self.clean_up()
                raise UpdateMergeError("Failed to download manifest: %s" % err)

        elif os.path.isfile(options.source_version):
            src_abs_path = os.path.abspath(options.source_version)
            if not os.path.samefile(os.path.dirname(src_abs_path),
                                    self.options.workspace):
                self.log.info("Copying source manifest")
                copy(options.source_version, self.source_file)

        if options.prev_version:
            self.log.info("Downloading previous base static manifest")
            try:
                # Path of prev label static manifest (source) file
                self.prev_src_file = os.path.normpath(
                    os.path.join(options.workspace, "prev_static.xml"))
                getmanifest.get_manifest(options.prev_version,
                                         self.prev_src_file,
                                         repo_url=options.repo_url)
            except getmanifest.GetManifestError, err:
                self.log.error("Error getting previous manifest version:"
                               " %s %s" % (options.prev_version, err))
                options.prev_version = None
        # Construct the manifest objects
        try:
            with open(self.source_file) as fp:
                self.src_manifest = RepoXmlManifest(fp)
            with open(self.target_file) as fp:
                self.target_manifest = RepoXmlManifest(fp)
            with open(self.target_file) as fp:
                self.final_manifest = RepoXmlManifest(fp)
                self.final_manifest.set_mutable(True)
            if options.prev_version:
                with open(self.prev_src_file) as fp:
                    self.prev_manifest = RepoXmlManifest(fp)
        except (ExpatError, ManifestParseError, IOError), err:
            self.log.critical("Error parsing one of the manifests: %s" % err)
            self.clean_up()
            raise UpdateMergeError("Error parsing one of the manifests: %s" %
                                   err)
        # List out the branched out gits from the target manifest
        self.branched_gits = self.target_manifest.get_branched_out_gits()
        self.source_projects = set(self.src_manifest.projects.keys())
        self.target_projects = set(self.target_manifest.projects.keys())

        # Get the delta projects between two snapshot.
        # Extract the project names that are only in the source version
        self.added_projects = self.source_projects.difference(
            self.target_projects)
        # Extract the project names that are only in the destination branch
        self.removed_projects = self.target_projects.difference(
            self.source_projects)
        # Extract the project names that are in both manifests
        self.common_projects = self.source_projects.intersection(
            self.target_projects)

        self.flag_manifest_rev = False
        if self.flag_sw_ver:
            try:
                if not options.amss_version:
                    res = getmanifest.get_control_fields(
                        options.source_version, repo_url=options.repo_url)
                    manifest_branch = res[self.branch_field]
                    manifest_revision = res[self.revision_field]
                else:
                    res = getmanifest.get_control_fields(
                        options.source_version,
                        package_name,
                        repo_url=options.repo_url)
                    manifest_branch = res[self.amss_branch_field]
                    manifest_revision = res[self.amss_revision_field]
                self.flag_manifest_rev = True
            except getmanifest.GetManifestError, err:
                self.log.error("Failed to copy manifest_revision %s" % err)
            else:
                try:
                    self.log.info("Initializing repo for %s" % manifest_branch)
                    Repo(manifest_branch, self.manifest_git_path,
                         self.options.workspace)
                except RepoError, err:
                    self.flag_manifest_rev = False
                    self.log.error("Failed to init repo for branch %s: %s" %
                                   (manifest_branch, str(err)))
                else:
                    try:
                        git_handle = \
                            git.GitRepository("%s/%s" %
                                              (self.options.workspace,
                                               ".repo/manifests"))
                        git_handle.run_cmd(["checkout",
                                            "%s" % manifest_revision])
                    except processes.ChildExecutionError, err:
                        self.log.info("Error checking out source default "
                                      "manifest revision %s:%s" %
                                      (manifest_revision, err))
                    copy("%s/.repo/manifests/default.xml" % options.workspace,
                         self.source_default)
                    rmtree("%s/.repo" % options.workspace)
                    try:
                        with open(self.source_default) as fp:
                            self.src_default = RepoXmlManifest(fp)
                    except (ManifestParseError, IOError), err:
                        self.log.error("Error parsing ref default manifest: "
                                       "%s" % err)
                        self.flag_manifest_rev = False
        if self.options.file_report:
            self.options.file_report = \
                os.path.normpath(os.path.join(options.workspace,
                                              self.options.file_report))
        # Currently adding hardcoded review message.
        version = ""
        if self.options.amss_version:
            version = self.options.amss_version
        elif self.flag_sw_ver:
            version = self.options.source_version
        self.review_msg = "Dear Reviewers,\n" \
                          "This is a rebase commit from %s to %s." \
                          "\n\nPlease add SDA (if not included) and more " \
                          "appropriate reviewers if needed." % \
                          (version, self.options.target_branch)
        self.confilct_msg = "\nTHIS IS A CONFLICT REBASE UPLOAD:\n" \
                            "This change is uploaded to inform you about a " \
                            "conflict happen during rebase. Kindly upload a " \
                            "patch on this change to solve the conflict and " \
                            "verify it."

    def clean_up(self):
        """Clean up the workspace, if something goes wrong in-between.

        Exception raised: UpdateMergeError
        Exception case:
            Error cleaning the workspace.

        """
        try:
            script_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
            workspace = self.options.workspace
            cwd = os.getcwd()
            if workspace in [cwd, script_dir]:
                # If workspace is same as either current directory or
                # script directory then delete the related files and
                # directories only.
                for file_name in ["manifest_static.xml", "ref_default.xml",
                                  "prev_static.xml"]:
                    file_path = os.path.join(workspace, file_name)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                dir_path = os.path.join(workspace, CLONE_DIR)
                if os.path.isdir(dir_path):
                    rmtree(dir_path)
            else:
                rmtree(self.options.workspace)
        except EnvironmentError, err:
            raise UpdateMergeError("Could not remove the workspace %s" %
                                   self.options.workspace)

    def component_rebase(self):
        """Component rebase for branched-out gits.

        By default, component rebase is done only for those git which
        are having revision same as target branch.
        Additional gits are added depending on the optional arguments
        (--include-gits, --component-branch) provided by the user.

        """

        #Component Rebase
        if self.options.prev_version:
            rebased_gits = self.revision_diff(
                self.src_manifest, self.prev_manifest,
                set(self.branched_gits).difference(self.removed_projects))

        self.merge_review = {}
        self.merge_failed = {}
        self.merge_uptodate = []
        self.merge_done = []

        if self.options.flag_component or self.options.flag_cmpnt_all:
            self.log.info("Starting component rebase")
            for project in self.branched_gits:
                if (self.options.prev_version and
                    project not in rebased_gits) or \
                        project in self.removed_projects:
                    continue
                branch_name = \
                    self.target_manifest.projects[project][STR_REVISION]
                if self.exclude_git_matcher.match(project) or \
                       (branch_name != self.options.target_branch and
                        not self.include_branch_matcher.match(branch_name) and
                        not self.include_git_matcher.match(project) and
                        not self.options.flag_cmpnt_all):
                    continue
                try:
                    self.log.info("Syncing %s git..." % project)
                    self.log.info("Branch:%s" % branch_name)
                    self.repo_handler.sync(project)
                except RepoError, err:
                    self.log.error("Failed to sync git: %s" % str(err))
                    self.merge_failed[project] = "%s \n" % str(err)
                    continue

                flag_conflict = False
                static_rev = self.src_manifest.projects[project][STR_REVISION]
                rebase_msg = "Category: integration"
                if self.options.commit_message:
                    merge_msg = self.options.commit_message
                elif self.options.amss_version:
                    merge_msg = "Merge delta from %s into %s" % \
                                    (self.options.amss_version, branch_name)
                elif self.flag_sw_ver:
                    merge_msg = "Merge delta from %s into %s" % \
                                    (self.options.source_version, branch_name)
                else:
                    merge_msg = "Merge commit %s into %s" % (static_rev,
                                                             branch_name)
                    rebase_msg = "Component rebase"

                review_message = self.review_msg
                git_path = self.src_manifest.projects[project]["path"]
                runpath = os.path.join(self.clone_dir, git_path)
                if not git.is_sha1(static_rev):
                    rev = static_rev
                    if not git.is_tag(rev):
                        rev = "origin/%s" % rev
                    try:
                        (ret, res, err) = processes.run_cmd("git",
                                                            "rev-parse", rev,
                                                            path=runpath)
                        static_rev = res.strip()
                    except processes.ChildExecutionError, err:
                        self.merge_failed[project] = "%s \n" % str(err)
                        continue
                self.log.info("Commit id %s" % static_rev)
                try:
                    self.log.info(merge_msg)
                    (ret, res, err) = processes.run_cmd("git", "merge",
                                                        static_rev, "-v",
                                                        "--no-ff", "--stat",
                                                        "--log=300",
                                                        "--no-commit",
                                                        "-m", merge_msg,
                                                        "-m", rebase_msg,
                                                        path=runpath)
                    if "Already up-to-date." in res:
                        self.log.info("Already up-to-date.")
                        self.merge_uptodate.append(project)
                        continue
                except processes.ChildExecutionError, err:
                    (ret, res, err) = err.result
                    self.log.info("Merge conflict.")
                    self.merge_failed[project] = res
                    if self.options.force_push:
                        flag_conflict = True
                        review_message += self.confilct_msg
                    else:
                        continue
                try:
                    # Calling git commit to add change id in commit message.
                    (ret, out, err) = processes.run_cmd("git", "commit", "-a",
                                                        "-F", ".git/MERGE_MSG",
                                                        path=runpath)
                except processes.ChildExecutionError, err:
                    self.log.info("Failed to commit.")
                    self.merge_failed[project] = res
                    continue

                if not flag_conflict:
                    self.merge_done.append(project)
                if self.options.flag_upload:
                    reviewers = []
                    if not self.options.no_reviewers or \
                           (self.options.reviewers_on_conflict and \
                            flag_conflict):
                        try:
                            gerrit_handle = self.gerrit_handler.gerrit
                            (reviewers, url) = \
                                gerrit_handle.get_review_information(
                                    static_rev, include_owner=True)
                        except Exception, err:
                            self.log.error("Failed to get reviewers list: %s" %
                                           err)
                    reviewers += self.options.reviewers
                    if reviewers:
                        self.log.info("Reviewers: %s" % ",".join(reviewers))
                    if not self.options.flag_review_msg:
                        review_message = None
                    try:
                        self.log.info("Uploading to gerrit.")
                        res = self.gerrit_handler.upload_gerrit(project,
                                                                branch_name,
                                                                runpath,
                                                                reviewers,
                                                                flag_conflict,
                                                                review_message)
                        self.merge_review[project] = res
                    except AddReviewersError, err:
                        # Error message is having the commit id. So
                        # changing to url to sync with other outputs.
                        pattern = "[a-zA-Z0-9]{%s}" % git.SHA1_STR_LEN
                        commit_id = \
                            filter(git.is_sha1, re.findall(pattern, str(err)))
                        if len(commit_id):
                            gerrit_handle = self.gerrit_handler.gerrit
                            try:
                                (reviewers, url) = \
                                    gerrit_handle.get_review_information(
                                        commit_id[0])
                                err = re.sub(pattern, url, str(err))
                            except:
                                pass
                        self.merge_review[project] = str(err)
                    except GerritError, err:
                        self.log.error("%s" % err)
                        self.merge_review[project] = str(err)

    def manifest_rebase(self):
        """Rebase manifest file

        Rebase the manifest file and commit the changes.Upload the commit
        if Gerrit upload option is enabled.

        Exception raised: UpdateMergeError
        Exception cases:
            Error adding project to manifest.
            Error removing project from manifest.
            Error updating manifest revision.
            Failed to commit the change.

        """
        if not self.options.flag_manifest:
            self.log.info("Disabled manifest rebase")
            self.manifest_review = ""
            return
        self.log.info("Starting manifest rebase")
        # Add any new gits to target manifest
        for project in self.added_projects:
            if self.exclude_git_matcher.match(project):
                continue
            category = None
            if self.flag_manifest_rev and \
                   project in self.src_default.projects:
                category = self.src_default.get_category(project)
                def_rev = self.src_default.projects[project][STR_REVISION]
                if git.is_tag(def_rev):
                    self.src_manifest.projects[project][STR_REVISION] = def_rev
            try:
                # Child node is maintained in separate list. Check for
                # child nodes and add if necessary.
                child_node = None
                if project in self.src_manifest.child_nodes:
                    child_node = self.src_manifest.child_nodes[project]
                self.final_manifest.add_new_project(
                    self.src_manifest.projects[project], category, child_node)
            except (ManifestError, TypeError), err:
                self.log.critical("Error adding project to manifest: %s" % err)
                self.clean_up()
                raise UpdateMergeError("Error adding project to manifest: "
                                       "%s" % err)

        # Remove gits which got removed from target manifest
        for project in self.removed_projects:
            if not self.exclude_git_matcher.match(project) and \
                   project not in self.branched_gits:
                try:
                    self.final_manifest.remove_project(project)
                except (ManifestError, TypeError), err:
                    self.log.critical("Error removing project from manifest:"
                                      " %s" % err)
                    self.clean_up()
                    raise UpdateMergeError("Error removing project from "
                                           "manifest: %s" % err)
        # Update the common gits' revision
        self.rev_updated = []
        for project in self.common_projects:
            if self.exclude_git_matcher.match(project) or \
                   project in self.branched_gits:
                continue
            try:
                src_rev = self.src_manifest.projects[project][STR_REVISION]
                if self.flag_manifest_rev and \
                       project in self.src_default.projects:
                    def_rev = self.src_default.projects[project][STR_REVISION]
                    if git.is_tag(def_rev):
                        src_rev = def_rev
                tgt_rev = self.final_manifest.projects[project][STR_REVISION]
                if src_rev != tgt_rev:
                    self.log.info("%s:%s" % (project, src_rev))
                    self.rev_updated.append(project)
                    self.final_manifest.update_revision(project, src_rev)
            except (ManifestError, TypeError), err:
                self.log.error("Error updating manifest revision: %s" % err)
                self.clean_up()
                raise UpdateMergeError("Error updating manifest revision: "
                                       "%s" % err)
        # Write the target manifest file
        # Create a temporary output file in the workspace folder
        gits_added = \
            set(filter(lambda a: not self.exclude_git_matcher.match(a),
                   set(self.added_projects).difference(self.branched_gits)))
        gits_removed = \
            set(filter(lambda a: not self.exclude_git_matcher.match(a),
                   set(self.removed_projects).difference(self.branched_gits)))
        try:
            if len(gits_added | gits_removed | set(self.rev_updated)):
                self.final_manifest.write_to_xml(self.output_file)
            else:
                self.log.info("Manifest rebase: nothing to commit")
                self.manifest_review = ""
                return
        except (ManifestError, IOError), err:
            raise UpdateMergeError("Failed to write the output file: %s" % err)
        else:
            if os.path.isfile(self.output_file) and \
                   os.path.isfile(self.target_file):
                copy(self.output_file, self.target_file)
                os.remove(self.output_file)

            self.log.info("Updated manifest file %s" % self.target_file)
            # Commit the change on the target (topic) branch
            commit_msg = "Manifest rebase\nCategory: integration"
            if self.options.commit_message:
                commit_header = self.options.commit_message
            elif self.options.amss_version:
                commit_header = "Merge delta from %s into %s" % \
                                    (self.options.amss_version,
                                     self.options.target_branch)
            elif self.flag_sw_ver:
                commit_header = "Merge delta from %s into %s" % \
                                    (self.options.source_version,
                                     self.options.target_branch)
            else:
                file_name = os.path.basename(self.options.source_version)
                commit_header = "Merge manifest %s into %s" % \
                                    (file_name, self.options.target_branch)
                commit_msg = "Manifest rebase"
            if gits_added:
                commit_msg = "%s\nAdded New git(s):\n%s" % \
                             (commit_msg, ("\n").join(gits_added))
            if gits_removed:
                commit_msg = "%s\nRemoved git(s):\n%s" % \
                                 (commit_msg, ("\n").join(gits_removed))
            runpath = os.path.join(self.clone_dir,
                                   os.path.dirname(self.manifest_file_path))
            self.log.info("Done rebasing. Committing changes...")
            try:
                (ret, res, err) = processes.run_cmd(
                    "git", "commit", "-a", "-m", commit_header,
                    "-m", commit_msg, path=runpath)
            except processes.ChildExecutionError, err:
                raise UpdateMergeError("Failed to commit the change: %s" % err)

            if self.options.flag_upload:
                self.log.info("Uploading manifest change to gerrit.")
                try:
                    self.manifest_review = self.gerrit_handler.upload_gerrit(
                        self.manifest_git_path, self.options.target_branch,
                        runpath, self.options.reviewers)
                except GerritError, err:
                    self.manifest_review = "Manifest upload: %s" % err
                    self.log.info(self.manifest_review)

    def revision_diff(self, src_manifest, prev_manifest, branched_gits):
        """List of gits whose revision field got updated.

        Compares the revision field of current static manifest with
        previous manifest.

        """
        rev_diff = []
        for project in branched_gits:
            if project in src_manifest.projects and \
                   project in prev_manifest.projects:
                if src_manifest.projects[project][STR_REVISION] != \
                       prev_manifest.projects[project][STR_REVISION]:
                    rev_diff.append(project)
        return rev_diff

    def log_list(self, list):
        """ Log each element in the list."""
        if len(list):
            self.log.info("\n".join(list))
        else:
            self.log.info("None")

    def log_dict(self, dict):
        """ Log the key:value pairs in the dictionary."""
        if len(dict):
            for (key, value) in dict.items():
                self.log.info("%s \n %s" % (key, value))
        else:
            self.log.info("None")

    def print_report(self):
        """Logs the final status of rebase.

        Exception raised: UpdateMergeError
        Exception cases:
            Error saving report file.
         """

        manifest_changed = False
        if self.options.flag_manifest:
            self.log.info("\nManifest rebase status")
            self.log.info("Updated the revision for the following projects:")
            self.log_list(self.rev_updated)

            self.log.info("\nAdded the following projects:")
            gits = set(self.added_projects).difference(self.branched_gits)
            temp_added = \
                set(filter(lambda a: not self.exclude_git_matcher.match(a),
                       gits))
            self.log_list(temp_added)

            self.log.info("\nRemoved the following projects:")
            gits = set(self.removed_projects).difference(self.branched_gits)
            temp_removed = \
                set(filter(lambda a: not self.exclude_git_matcher.match(a),
                       gits))
            self.log_list(temp_removed)

            if not len(set(self.rev_updated) | temp_added | temp_removed):
                self.log.info("platform/manifest: Nothing to commit")
            elif self.options.flag_upload:
                manifest_changed = True
                self.log.info("\nManifest file Gerrit upload:")
                self.log.info("platform/manifest: %s" % self.manifest_review)
        else:
            self.log.info("\nDisabled manifest rebase")

        if self.options.flag_component or self.options.flag_cmpnt_all:
            self.log.info("\nComponent Rebase")
            self.log.info("\nMerge Up-to-date:")
            self.log_list(self.merge_uptodate)
            self.log.info("\nMerge-Failed:")
            self.log_dict(self.merge_failed)
            self.log.info("\nMerge-Done:")
            if self.options.flag_upload and len(self.merge_review):
                self.log.info("Gerrit Upload")
                self.log_dict(self.merge_review)
            else:
                self.log_list(self.merge_done)

        if self.options.file_report and (manifest_changed or \
                                         len(self.merge_review)):
            try:
                with open(self.options.file_report, "w") as fp:
                    pattern = re.compile("https?://%s/([0-9]+)" % GERRIT_URL)
                    # Manifest upload URL
                    if manifest_changed:
                        gerrit_url = ""
                        match = pattern.search(self.manifest_review)
                        if match:
                            gerrit_url = match.group(0)
                        fp.write("%s: %s\n" % (self.manifest_git_path,
                                               gerrit_url))
                    # Component rebase Gerrit uploads
                    if len(self.merge_review):
                        for (key, value) in self.merge_review.items():
                            gerrit_url = ""
                            match = pattern.search(value)
                            if match:
                                gerrit_url = match.group(0)
                            to_write = "%s: %s" % (key, gerrit_url)
                            if key in self.merge_failed:
                                to_write = "%s: conflict" % to_write
                            to_write = "%s\n" % to_write
                            fp.write(to_write)
            except IOError, err:
                self.log.error("Error saving report: %s" % err)
                raise UpdateMergeError("Error saving report: %s" % err)


class UpdateMergeLogger:
    """Log output to file or standard output"""
    def __init__(self, filename=None):
        """ Creates 'logging' object.

        Arguments:
            filename: log file name.

        If file name is provided, creates 'logging' object to write the
        log to file, else to standard output.

        """
        self.logger = logging.getLogger("UpdateMerge")
        self.logger.setLevel(logging.DEBUG)
        # Create handler.
        if filename:
            # By default 'FileHandler' will open file in append mode.
            handler = logging.FileHandler(filename, 'w')
        else:
            # By default 'StreamHandler' will log to STDERR.
            handler = logging.StreamHandler(sys.stdout)
        # Set log level.
        handler.setLevel(logging.DEBUG)
        self.logger.addHandler(handler)


class UpdateMergeError(Exception):
    """Class to handle exception in Rebase """


def _main():
    """Main function"""
    # Argument handling
    parser = optparse.OptionParser("%prog <-s source-version> "
                                   "<-t target-branch> "
                                   "[-u ]"
                                   "[-c ]"
                                   "[-b component-branch]"
                                   "[-a ]"
                                   "[-m amss-version]"
                                   "[-p previous-version]"
                                   "[-r repo-url]"
                                   "[-x exclude-git]"
                                   "[-i include-git]"
                                   "[-w workspace]"
                                   "[-l log-file]"
                                   "[-f file-report]"
                                   "[--gerrit-user gerrit_user]"
                                   "[--reviewer reviewer]"
                                   "[--force-push]"
                                   "[--review-msg]"
                                   "[--manifest]"
                                   "[--no-reviewers]"
                                   "[--reviewers-on-conflict]"
                                   "[--commit-message]")
    parser.add_option("-s", "--source-version", dest="source_version",
                      default=None,
                      help="Official label for the base manifest version. " \
                           "Manifest file path can also be given as source " \
                           "instead of label")
    parser.add_option("-t", "--target-branch", dest="target_branch",
                      default=None,
                      help="Branch name in the target manifest")
    parser.add_option("-u", "--upload", action="store_true",
                      dest="flag_upload", default=False,
                      help="Enable upload to Gerrit")
    parser.add_option("-c", "--component-rebase", action="store_true",
                      dest="flag_component", default=False,
                      help="Enable component rebase")
    parser.add_option("-b", "--component-branch", dest="component_branch",
                      action="append", metavar="REGEXP",
                      default=None,
                      help="A regular expression that will be matched " \
                           "against the branches of the gits found in " \
                           "the target manifest to include them in the " \
                           "component rebase. This option can be used " \
                           "multiple times to add more expressions.")
    parser.add_option("-a", "--component-all", action="store_true",
                      dest="flag_cmpnt_all", default=False,
                      help="Enable component rebase for all the branches")
    parser.add_option("-m", "--amss-version", dest="amss_version",
                      default=None,
                      help="Official label of amss build. Provide the label "
                           "for amss rebase.")
    parser.add_option("-p", "--previous-version", dest="prev_version",
                      default=None,
                      help="Previous base manifest label")
    parser.add_option("-r", "--repo-url", dest="repo_url",
                      default=None,
                      help="Override default repository url")
    parser.add_option("-x", "--exclude-git", dest="exclude_git",
                      action="append", metavar="REGEXP",
                      default=None,
                      help="A regular expression that will be matched " \
                           "against the gits found in the target " \
                           "manifest to exclude them from the " \
                           "rebase. This option can be used " \
                           "multiple times to add more expressions.")
    parser.add_option("-i", "--include-git", dest="include_git",
                      action="append", metavar="REGEXP",
                      default=None,
                      help="A regular expression that will be matched " \
                           "against the gits found in the target " \
                           "manifest to include them in the " \
                           "component rebase. This option can be used " \
                           "multiple times to add more expressions.")
    parser.add_option("-w", "--workspace", dest="workspace",
                      default=".",
                      help="Workspace to clone gits. Default " \
                           "is current working directory")
    parser.add_option("-l", "--log-file", dest="log_file",
                      default=None,
                      help="File name to log the result to file. " \
                           "Default output to terminal")
    parser.add_option("-f", "--file-report", dest="file_report",
                      default=None,
                      help="File name to save the final report " \
                           "of git and gerrit upload URLs. " \
                           "Option can only be used along with -u/--upload.")
    parser.add_option("--gerrit-user", dest="gerrit_user",
                      default=None,
                      help="Gerrit username to be used in the git commands.")
    parser.add_option("--reviewer", dest="reviewers",
                      action="append", default=[],
                      help="Reviewer email address. This option can be used "
                           "multiple times to add more reviewers.")
    parser.add_option("--force-push", action="store_true",
                      dest="force_push", default=False,
                      help="Enable force push to gerrit")
    parser.add_option("--review-msg", action="store_true",
                      dest="flag_review_msg", default=False,
                      help="Enable adding review message")
    parser.add_option("--manifest", action="store_false",
                      dest="flag_manifest", default=True,
                      help="Disable manifest rebase")
    parser.add_option("--no-reviewers", action="store_true",
                      dest="no_reviewers", default=False,
                      help="Disable adding reviewers, from the source commit, "
                           "to the commit message")
    parser.add_option("--reviewers-on-conflict", action="store_true",
                      dest="reviewers_on_conflict", default=False,
                      help="Enable adding reviewers only for merge conflict "
                           "commits.")
    parser.add_option("--commit-message", dest="commit_message",
                      default=None,
                      help="Message to be used as commit message header.")

    (options, args) = parser.parse_args()

    if not options.source_version:
        parser.print_usage(file=sys.stderr)
        semcutil.fatal(1, "Must specify '--source-version'.")

    if not options.target_branch:
        parser.print_usage(file=sys.stderr)
        semcutil.fatal(1, "Must specify '--target-branch'.")

    logger = UpdateMergeLogger(options.log_file)
    rebase_handler = UpdateMerge(options, logger)
    try:
        rebase_handler.manifest_rebase()
        rebase_handler.component_rebase()
        rebase_handler.print_report()
    except UpdateMergeError, err:
        rebase_handler.clean_up()
        logger.log(str(err))

if __name__ == "__main__":
    _main()
