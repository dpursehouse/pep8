#!/usr/bin/env python

'''
Find cherry pick candidates in source branch(es) by processing the git log of
each base branch and target branch. From the log, list of DMSs will be checked
with DMS tag server and commits with correct DMS tag will be considered.
Exclusion filters which are mentioned in --exlude-git,--exclude-dms
and --exclude-commit will be excluded. Then the potential commits will be
pushed to Gerrit for review. As a byproduct a .csv file will be created with
the commit list and a _result.csv file with the result of each cherry pick
execution.

During each cherry pick, commit id will be checked in Gerrit commit message,
and cherry pick of this commit will be skipped if corresponding commit is found
in open or abandoned state.

Email will be sent to corresponding persons for each cherry-pick failure with
reason and Gerrit URL. And in dry-run mode, email will be sent only to
executor.

It is possible to simulate the whole process by using the --dry-run option and
possible to create only the cherry pick list and skip the push to Gerrit
action with the -n(--no-push-to-gerrit) option.

repo envirionment must be initialized in working directory before you run this
script.

Example:
 To find out the potential commits for cherry pick from base ginger-mogami to
 target edream4.0-release with DMS tag "4.0 CAF":
 Initialize repo first
 $repo init -u git://review/platform/manifest.git -b ginger-mogami

 1. To find out the potential commits and push to Gerrit for review
    $%prog -b ginger-mogami -t edream4.0-release -d "4.0 CAF"
 2. To simulate the whole execution without actual push to Gerrit
    add --dry-run option
    $%prog -b ginger-mogami -t edream4.0-release -d "4.0 CAF" --dry-run
 3. To create only the csv file with potential cherry pick commit list
    add --no-push-to-gerrit option
    $%prog -b ginger-mogami -t edream4.0-release -d "4.0 CAF" \
    --no-push-to-gerrit
 4. To push the commits from already created csv file
    $%prog -t edream4.0-release -f <csv_file_name>.csv
 5. To add default reviewers with each cherry pick commit add
    -r <reviewers email addresses> option
    $%prog -b ginger-mogami -t edream4.0-release -d "4.0 CAF"
    -r "xx@sonyericsson.com,yy@sonyericsson.com"
'''

import errno
import logging
import optparse
import os
import re
import signal
import StringIO
import subprocess
import tempfile
import threading
import time
import xml.dom.minidom


from branch_policies import BranchPolicies
from branch_policies import BranchPolicyError, CherrypickPolicyError
from cm_server import CMServer, CMServerError, CredentialsError
from cm_server import CherrypickStatus, CherrypickStatusError
from cm_server import DEFAULT_SERVER
from dmsutil import DMSTagServer, DMSTagServerError
from find_reviewers import FindReviewers, AddReviewersError
from gerrit import GerritSshConnection, GerritSshConfigError, GerritQueryError
import git
from include_exclude_matcher import IncludeExcludeMatcher
from processes import ChildExecutionError
from semcutil import enum

__version__ = '0.4.9'

# Disable pylint messages
# pylint: disable-msg=C0103,W0602,W0603,W0703,R0911

REPO = 'repo'
GIT = 'git'
OPT_PARSER = None
OPT = None
dst_manifest = None
manifest_change_required = False
upd_project_list = []
dms_tags = []
cmserver = None

#Error codes
ERROR_CODE = enum('STATUS_OK',
                  'STATUS_CHERRYPICK_FAILED',
                  'STATUS_REPO',
                  'STATUS_DMS_SRV',
                  'STATUS_MANIFEST',
                  'STATUS_ARGS',
                  'STATUS_FILE',
                  'STATUS_GIT_USR',
                  'STATUS_GERRIT_ERR',
                  'STATUS_RM_PROJECTLIST',
                  'STATUS_USER_ABORTED',
                  'STATUS_RM_MANIFEST_DIR',
                  'STATUS_CLONE_MANIFEST',
                  'STATUS_UPDATE_MANIFEST',
                  'STATUS_CM_SERVER')

# The default value of the command line option to select which
# branches in the target manifest can be cherry picked to.
DEFAULT_TARGET_BRANCH_INCLUDES = [r"^"]

# The default value of the command line option to select which
# branches in the target manifest can not be cherry picked to.
DEFAULT_TARGET_BRANCH_EXCLUDES = [r"^rel-", r"^maint-", "refs/tags/"]

#Gerrit server URL
GERRIT_URL = "review.sonyericsson.net"

# Default server to use for DMS tag status
DEFAULT_DMS_TAG_SERVER = "android-cm-web.sonyericsson.net"

# Number of times to attempt git push of the cherry picked change
MAX_PUSH_ATTEMPTS = 3

# Mail server to use when sending notifications
SMTP_MAIL_SERVER = "smtpem1.sonyericsson.net"

# Default email address for sender when sending notification mails
DEFAULT_MAIL_SENDER = "DL-WW-CM@sonymobile.com"

# Mail notification when cherry pick fails
CHERRY_PICK_FAILED_NOTIFICATION_MAIL =  \
"""Hello,

Automated cherry-pick of %s into branch %s has failed.

%s.

If this change is needed for %s, please manually cherry pick it with
'git cherry-pick -x', and add the following persons as reviewers:

%s

Please reply to this mail with the Gerrit link for the new change once it is
done.

Thanks,
Cherry-picker.
Version: %s


Useful links:

How to cherry pick:
  https://wiki.sonyericsson.net/androiki/How_to_cherry-pick
Cherry pick status page:
  http://cmweb.sonyericsson.net/harvest/cherries/
"""

# Mail notification when DMS Tag Server fails and no fallback option is used
TAG_SERVER_FAILED_NOTIFICATION_MAIL = \
"""Hello,

Automated cherry-pick failed.  The DMS tag server, '%s', returned error.
%s
Check the server name or rectify the server error and rerun.

Unable to verify DMS status for target branch %s, for the following commit(s).

%s

Thanks,
Cherry-picker.
Version: %s
"""


class GerritError(Exception):
    ''' GerritError is raised when a problem occurs connecting
    to Gerrit, or when a gerrit command returns an error.
    '''


class Gerrit(object):
    ''' Gerrit interface class to collect data from Gerrit
    '''
    def __init__(self, gerrit_user=None):
        ''' Constructor
        '''
        try:
            self.gerrit_user = gerrit_user
            self.gerrit = GerritSshConnection(GERRIT_URL, gerrit_user)
        except GerritSshConfigError, e:
            raise GerritError("Gerrit config error: %s" % e)

    def collect_email_addresses(self, commit):
        ''' Collect approver email addresses from `commit`.
        Return list of email addresses and review url.
        Raise GerritError if anything goes wrong.
        '''
        try:
            emails, url = \
                self.gerrit.get_review_information(commit,
                                                   exclude_jenkins=True,
                                                   include_owner=True)
            logging.info("Emails: %s", ",".join(emails))
            return emails, url
        except GerritQueryError, e:
            raise GerritError("Gerrit query error: %s" % e)
        except ChildExecutionError, e:
            raise GerritError("Gerrit query execution error: %s" % e)

    def is_commit_available(self, commit):
        ''' Return cherry status object if `commit` is available in open
        or abandoned state.
        Otherwise return None.
        Raise GerritError if anything goes wrong.
        '''
        query = "project:%s status:open branch:%s " \
                "message:cherry.picked.from.commit.%s " \
                "OR " \
                "project:%s status:abandoned branch:%s " \
                "message:cherry.picked.from.commit.%s" % \
                (commit.name, commit.target, commit.commit,
                 commit.name, commit.target, commit.commit)
        try:
            logging.info("Check for existing change in Gerrit...")
            results = self.gerrit.query(query)
            logging.info("Found %d matches", len(results))
            if len(results):
                cherry = CherrypickStatus()
                cherry.sha1 = commit.commit
                cherry.project = commit.name
                cherry.branch = commit.target
                cherry.set_dms(commit.dms)
                if 'number' in results[0] and 'status' in results[0]:
                    cherry.set_change_nr(int(results[0]['number']))
                    cherry.set_status(results[0]['status'])
                    return cherry
            return None
        except GerritQueryError, e:
            raise GerritError("Gerrit query error: %s" % e)
        except ChildExecutionError, e:
            raise GerritError("Gerrit query execution error: %s" % e)

    def approve(self, change_id):
        ''' Approve the `change_id` with +2 score.
        Raise GerritError if anything goes wrong.
        '''
        try:
            self.gerrit.review_patchset(change_nr=int(change_id),
                                        patchset=1,
                                        codereview=2)
        except GerritQueryError, e:
            raise GerritError("Gerrit query error: %s" % e)
        except ChildExecutionError, e:
            raise GerritError("Error setting code review for change %s: %s" % \
                              (change_id, e))

    def add_reviewers(self, change_id, reviewers):
        ''' Add `reviewers` to `change_id`.
        '''
        finder = FindReviewers(user=self.gerrit_user)
        try:
            finder.add(change_id, reviewers)
        except AddReviewersError, e:
            raise GerritError("Error adding reviewers on change %s: %s" % \
                              (change_id, e))


class Commit(object):
    """Data structure for a single commit"""
    def __init__(self, target=None, target_origin=None, path=None, name=None,
                 author_date=None, commit=None, dms=None, title=None):
        self.target = target
        if target_origin:
            self.target_origin = target_origin
        else:
            self.target_origin = 'origin/' + self.target
        self.path = path
        self.name = name
        self.author_date = author_date
        self.commit = commit
        self.dms = dms
        self.title = title

    def cmp(self, commit):
        """compare itself with another commit"""
        if (((self.target, self.name, self.dms) ==
            (commit.target, commit.name, commit.dms)) and
            (self.author_date == commit.author_date or
             self.title == commit.title)):
            #check author date and title if either one match, to detect
            #manual cherry pick which has different author date in base
            #and target
            return True
        return False

    def get_commit_info(self):
        """Returns the original commit's git name, SHA1 ID and associated
        DMS."""
        return "%s %s %s" % (self.name, self.commit, self.dms)

    def __str__(self):
        return "%s,%s,%s,%s,%s" % (self.target, self.path,
                   self.name, self.commit, self.dms)


class ManifestData(object):
    """Functionality for handling manifest XML data"""
    def __init__(self, xml_input_data, base_sha1):
        """Raises xml.parsers.expat.ExpatError if fails to parse data as valid
           XML or ValueError if the passed base SHA1 isn't a valid commit
           SHA1"""
        self.dom = xml.dom.minidom.parseString(xml_input_data)
        if (git.is_sha1(base_sha1)):
            self.base_sha1 = base_sha1
        else:
            raise ValueError('Invalid base SHA1')

    def update_revision(self, project_name, new_revision):
        """Update `project_name` revision to `new_revision`."""
        for element in self.get_projects():
            if (element.attributes['name'].nodeValue.encode('utf-8') ==
                    project_name):
                element.setAttribute('revision', new_revision)
                return True
        return False

    def write_xmldata_to_file(self, file_path):
        """Raises IOError if fails to write data to file"""
        path = os.path.dirname(file_path)
        fd, tmppath = tempfile.mkstemp(dir=path)
        data = self.dom.toxml(encoding="UTF-8")
        # Minidom currently doesn't return a newline-terminated string.
        if data.endswith("\n"):
            os.write(fd, data)
        else:
            os.write(fd, data + "\n")
        os.rename(tmppath, file_path)

    def get_def_rev(self):
        """Raises KeyError if fails to find tag name and/or revision"""
        return self.dom.getElementsByTagName("default")[0]. \
                    getAttribute('revision').encode('utf-8')

    def get_projects(self):
        """Raises KeyError if fails to find tag name"""
        return self.dom.getElementsByTagName("project")

    def get_base_sha1(self):
        """Return base sha1"""
        return self.base_sha1


def get_manifest_str(commit_ref):
    """Reads the manifest file and returns the content as a string and
       the last manifest change SHA1"""
    current_path = os.getcwd()
    os.chdir(os.path.join(OPT.cwd, '.repo/manifests'))
    try:
        manifest_str, err, ret = execmd([GIT, 'show', commit_ref +
                                        ':default.xml'])
        sha1, err1, ret1 = execmd([GIT, 'rev-parse', commit_ref])
    finally:
        os.chdir(current_path)
    if ret != 0:
        cherry_pick_exit(ERROR_CODE.STATUS_MANIFEST,
                         "Can't read the manifest file for %s:\n%s" %
                            (commit_ref, err))
    if ret1 != 0:
        cherry_pick_exit(ERROR_CODE.STATUS_MANIFEST,
                         "Can't get the last manifest change SHA1:\n%s" % err1)
    return manifest_str, sha1


def str_list(commit_list):
    """Helper function to convert a list of Commit to list of strings"""
    commit_list = [str(cmt) for cmt in commit_list]
    commit_list.sort()
    return commit_list


def option_parser():
    """
    Option parser
    """
    usage = ("%prog -s SOURCE_BRANCH -t TARGET_BRANCH [" +
             " --mail-sender SENDER_ADDRESS [options]]")
    opt_parser = optparse.OptionParser(usage=usage,
                                       version='%prog ' + __version__)
    opt_parser.add_option('-b', '--base-branches',
                     dest='base_branches',
                     help='base branches (comma separated), default is all.',
                     action="store", default=None)
    opt_parser.add_option('-t', '--target-branch',
                     dest='target_branch',
                     help='target branch')
    opt_parser.add_option('-s', '--source-branch',
                     dest='source_branch',
                     help='source branch')
    opt_parser.add_option("-i", "--include-target-branch",
                          dest="target_branch_include",
                          action="append", metavar="REGEXP",
                          default=[],
                          help="A regular expression that will be matched " \
                               "against the branches of the gits found in " \
                               "the target manifest to include them in the " \
                               "cherry pick.  This option can be used " \
                               "multiple times to add more expressions. The " \
                               "first use of this option will clear the " \
                               "default value (%s) before appending the new " \
                               "expression." % \
                               ", ".join(DEFAULT_TARGET_BRANCH_INCLUDES))
    opt_parser.add_option("-e", "--exclude-target-branch",
                          dest="target_branch_exclude",
                          action="append", metavar="REGEXP",
                          default=DEFAULT_TARGET_BRANCH_EXCLUDES,
                          help="Same as --include-git-branch but for " \
                               "excluding branches on gits found in the " \
                               "target manifest. This option can also be " \
                               "used multiple times to add more expressions. " \
                               "The first use of this option will append the " \
                               "new expression onto the default value (%s)." % \
                               ", ".join(DEFAULT_TARGET_BRANCH_EXCLUDES))
    opt_parser.add_option('-r', '--reviewers',
                     dest='reviewers',
                     help='default reviewers (comma separated)',
                     action="store", default=None)
    opt_parser.add_option('-w', '--work-dir',
                     dest='cwd',
                     help='working directory, default is current directory',
                     action="store", default=None)
    opt_parser.add_option('--dms-tag-server',
                     dest='dms_tag_server',
                     help='IP address or name of DMS tag server',
                     action="store", default=DEFAULT_DMS_TAG_SERVER)
    opt_parser.add_option('--status-server',
                     dest='status_server',
                     help='IP address or name of status server',
                     action="store", default=DEFAULT_SERVER)
    opt_parser.add_option('--approve',
                     dest='approve',
                     help='Approve uploaded change set in Gerrit with +2',
                     action="store_true", default=False)
    opt_parser.add_option('--mail-sender',
                     dest='mail_sender',
                     help='Mail sender address for mail notification.',
                     action="store", default=DEFAULT_MAIL_SENDER)
    opt_parser.add_option('--exclude-git',
                     dest='exclude_git',
                     help='List of gits to be excluded (comma separated)',
                     default=None,)
    opt_parser.add_option('--exclude-commit',
                     dest='exclude_commit',
                     help='List of commits to be excluded (comma separated)',
                     default=None,)
    opt_parser.add_option('--exclude-dms',
                     dest='exclude_dms',
                     help='List of DMSs to be excluded (comma separated)',
                     default=None,)
    opt_parser.add_option('--include-git',
                     dest='include_git',
                     help='List of gits to be included (comma separated)' +
                     '--exclude-git will be ignored.',
                     default=None,)
    opt_parser.add_option('-m', '--manifest',
                     dest='manifest',
                     help='Specify which manifest to use.',
                     action="store",
                     default="platform/manifest")
    #debug options
    opt_group = opt_parser.add_option_group('Debug options')
    opt_group.add_option('-v', '--verbose',
                     dest="verbose", default=0, action="count",
                     help="Verbose logging")
    opt_group.add_option('--no-rm-projectlist',
                     dest='no_rm_projectlist',
                     help='Do not remove .repo/project.list',
                     action="store_true",
                     default=False)
    opt_group.add_option('--no-repo-sync',
                     dest='no_repo_sync',
                     help='Do not repo sync', action="store_true",
                     default=False)
    opt_group.add_option('--skip-review',
                     dest='skip_review',
                     help='Skip Gerrit review of manifest changes',
                     action="store_true",
                     default=False)
    opt_group.add_option('-n', '--no-push-to-gerrit',
                     dest='no_push_to_gerrit',
                     help='Do not cherry pick and push to Gerrit',
                     action="store_true", default=False)
    opt_group.add_option('-f', '--csv-file',
                     dest='csv_file',
                     help='load the cherry pick list from csv file and push ' +
                     'to gerrit',
                     metavar="FILE")
    opt_group.add_option('--dry-run',
                     dest='dry_run',
                     help='Do not push to Gerrit',
                     action="store_true", default=False)
    opt_group.add_option('--gerrit-user',
                     dest='gerrit_user',
                     help='Use this Gerrit user to push, useful for ' +
                     'hudson job',
                     default=None)
    return opt_parser


def cherry_pick_exit(exit_code, message=None):
    """
    Exit this script with exit code and message
    """
    reason = {
      ERROR_CODE.STATUS_OK: "Cherry pick completed",
      ERROR_CODE.STATUS_CHERRYPICK_FAILED: "Some or all cherry picks failed",
      ERROR_CODE.STATUS_REPO: "Repo error",
      ERROR_CODE.STATUS_DMS_SRV: "DMS tag server is not reachable",
      ERROR_CODE.STATUS_MANIFEST: "Manifest file error",
      ERROR_CODE.STATUS_ARGS: "Using wrong arguments",
      ERROR_CODE.STATUS_FILE: "File error",
      ERROR_CODE.STATUS_GIT_USR: "Git config error",
      ERROR_CODE.STATUS_GERRIT_ERR: "Gerrit server is not reachable",
      ERROR_CODE.STATUS_RM_PROJECTLIST: "Failed to remove .repo/project.list",
      ERROR_CODE.STATUS_USER_ABORTED: "Aborted by user",
      ERROR_CODE.STATUS_RM_MANIFEST_DIR: "Failed to remove /manifest directory",
      ERROR_CODE.STATUS_CLONE_MANIFEST: "Failed to clone the manifest git",
      ERROR_CODE.STATUS_UPDATE_MANIFEST: "Failed to update the manifest",
      ERROR_CODE.STATUS_CM_SERVER: "CM server error"
      }
    msg = reason.get(exit_code)
    if message:
        msg += '\n' + message
    if exit_code != ERROR_CODE.STATUS_OK:
        logging.error(msg)
    else:
        logging.info(msg)
    exit(exit_code)


def parse_base_and_target_manifest(target_branch):
    """Parses base and target manifest files"""
    #parse base manifest
    try:
        manifest_str, base_sha1 = get_manifest_str('HEAD')
        base_manifest = ManifestData(manifest_str, base_sha1)
        base_proj_rev = {}
        for node in base_manifest.get_projects():
            rev = node.getAttribute('revision')
            path = node.getAttribute('path')
            name = node.getAttribute('name')
            rev = base_manifest.get_def_rev() if rev == '' else rev
            if OPT.base_branches:  # consider any base branches mentioned
                for base_branch in  OPT.base_branches.split(','):
                    if rev == base_branch:
                        base_proj_rev[name] = base_branch + ',' + path
                        break
            else:                  # otherwise consider all
                base_proj_rev[name] = rev + ',' + path
    except (KeyError, xml.parsers.expat.ExpatError, ValueError), err:
        cherry_pick_exit(ERROR_CODE.STATUS_MANIFEST,
                         "Failed to parse base manifest: %s" % err)
    #parse target manifest
    try:
        global dst_manifest
        manifest_str, base_sha1 = get_manifest_str('origin/' + target_branch)
        dst_manifest = ManifestData(manifest_str, base_sha1)
        dst_proj_rev = {}
        for node in dst_manifest.get_projects():
            rev = node.getAttribute('revision')
            rev = dst_manifest.get_def_rev() if rev == '' else rev
            dst_proj_rev[node.getAttribute('path')] = rev
    except (KeyError, xml.parsers.expat.ExpatError, ValueError), err:
        cherry_pick_exit(ERROR_CODE.STATUS_MANIFEST,
                         "Failed to parse target manifest: %s" % err)
    return base_proj_rev, dst_proj_rev


def repo_sync():
    """
    Repo sync
    """
    os.chdir(OPT.cwd)
    if not OPT.no_rm_projectlist:
        logging.info("Removing .repo/project.list")
        try:
            os.remove('.repo/project.list')
        except os.error, err:
            if err.errno != errno.ENOENT:
                cherry_pick_exit(ERROR_CODE.STATUS_RM_PROJECTLIST,
                                 "Error removing .repo/project.list: %s" % err)
    logging.info("Repo sync")
    result, err, ret = execmd([REPO, 'sync', '-j5'], 3600)
    log_to_file(result, file_name='repo_sync.log')
    if ret != 0:
        cherry_pick_exit(ERROR_CODE.STATUS_REPO, "Repo sync error %s" % err)


def get_dms_list(target_branch):
    """
    Collect the DMSs from all projects, from MERGE_BASE to  BASE_BRANCH and
    from MERGE_BASE to  TARGET_BRANCH. Return the DMSs list which are not in
    TARGET_BRANCH.
    """
    #Parse base and target manifest file
    base_proj_rev, dst_proj_rev = parse_base_and_target_manifest(target_branch)

    os.chdir(OPT.cwd)
    merge_base_log = open('merge-base.log', 'wb')
    base_log = open('source_commit.log', 'wb')
    target_log = open(target_branch + '_commit.log', 'wb')
    base_commit_list, target_commit_list = [], []

    old_cherries = None
    try:
        global cmserver
        logging.info("Get old cherries from CM server...")
        old_cherries = cmserver.get_old_cherrypicks(OPT.manifest,
                                                    OPT.source_branch,
                                                    target_branch)
        if old_cherries:
            logging.info("Found %s old cherries", len(old_cherries))
        else:
            logging.info("No old cherries found")
    except (CMServerError, CherrypickStatusError), e:
        logging.error("Error getting old cherry data: %s ", e)

    for name, rev_path in base_proj_rev.iteritems():
        target_revision = None
        target_is_sha1 = False
        path = rev_path.split(',')[1]
        base_rev = rev_path.split(',')[0]
        if OPT.include_git:
            if name not in OPT.include_git.split(','):
                logging.info("%s: pass: git is not included", name)
                continue
        elif OPT.exclude_git and name in OPT.exclude_git.split(','):
            logging.info("%s: pass: git is excluded", name)
            continue

        os.chdir(os.path.join(OPT.cwd, path))

        # If the revision of the source git is a sha1 or tag, we don't need
        # to cherry pick from it.
        if git.is_sha1_or_tag(base_rev):
            logging.info("%s: pass: source revision is a sha1 or tag", name)
            continue

        # Skip any source gits that do not have a valid revision
        ret = execmd([GIT, 'show-ref', '-q', '--verify',
                      'refs/remotes/origin/' + base_rev])[2]
        if ret != 0:
            logging.error("%s: pass: invalid revision %s", name, base_rev)
            continue

        # Check that the git is available in the target manifest
        if not path in dst_proj_rev:
            logging.info("%s: pass: project does not exist in target "
                         "manifest", name)
            continue

        t_revision = dst_proj_rev[path]
        if t_revision == base_rev:
            # No need to proceed if source and target both have same revision
            logging.info("%s: pass: project has same revision %s in target "
                         "manifest", name, t_revision)
            continue

        if (git.is_sha1(t_revision)):
            target_revision = t_revision  # it's a sha1
            target_is_sha1 = True
            logging.info("%s: target revision is a sha-1", name)
        else:
            matcher = IncludeExcludeMatcher(OPT.target_branch_include,
                                            OPT.target_branch_exclude)
            if (matcher.match(t_revision)):
                target_revision = 'origin/' + t_revision
                logging.info("%s: target branch is %s", name, t_revision)
            else:
                logging.info("%s: pass: target branch %s is excluded",
                             name, t_revision)
                continue

        os.chdir(os.path.join(OPT.cwd, path))
        mergebase, err, ret = execmd([GIT, 'merge-base', 'origin/' +
                                      base_rev, target_revision])
        if not mergebase:
            logging.info("%s: pass: no merge-base for %s and %s",
                         name, base_rev, target_branch)
            merge_base_log.write('No merge-base for %s and %s\n',
                                 base_rev, target_branch)
            logging.error(err)
            continue
        merge_base_log.write(mergebase + '\n')
        if target_is_sha1:  # add target rev and path to commit
            rev_path = target_branch + ',' + path
        else:
            rev_path = t_revision + ',' + path
        #read merge base to base branch log
        b_commit_list_full = collect_fix_dms('origin/' + base_rev, mergebase,
                                             rev_path + ',' + name, base_log)
        b_commit_list = []

        # Exclude any commits that have already been processed and are
        # registered on the status server.
        if old_cherries:
            all_cherries = [cherry.sha1 for cherry in old_cherries]
            for cmt in b_commit_list_full:
                if cmt.commit in all_cherries:
                    logging.info("%s: commit %s already processed once",
                                 cmt.name, cmt.commit)
                else:
                    b_commit_list.append(cmt)
        else:
            b_commit_list = b_commit_list_full

        #read merge base to target branch log
        t_commit_list = collect_fix_dms(target_revision, mergebase,
                                   rev_path + ',' + name, target_log)
        #handle new branch creation if target git rev is sha1
        if target_is_sha1 and b_commit_list:
            if create_branch(target_branch, b_commit_list,
                                 t_commit_list, name, target_revision):
                for commit in b_commit_list:
                    commit.target_origin = target_revision
            else:
                # Nothing to cherry pick in this git, go to next
                logging.info("%s: pass: nothing to cherry pick", name)
                os.chdir(OPT.cwd)
                continue
        if b_commit_list:
            base_commit_list += b_commit_list
        if t_commit_list:
            target_commit_list += t_commit_list
        os.chdir(OPT.cwd)

    log_to_file('\n'.join(str_list(base_commit_list)),
                file_name='base_dms_list.log')
    log_to_file('\n'.join(str_list(target_commit_list)),
                file_name=target_branch + '_dms_list.log')
    #remove the common commits both in base and target
    final_commit_list = []
    final_commit_list += base_commit_list
    for cmt in base_commit_list:
        for t_cmt in target_commit_list:
            if cmt.cmp(t_cmt):
                final_commit_list.remove(cmt)
                break
    log_to_file('\n'.join(str_list(final_commit_list)),
                file_name=target_branch + '_diff_dms_list.log',
                info='Diff list')
    return final_commit_list


def clone_manifest_git(branch):
    """Clone the manifest git"""
    logging.info("Removing the old manifest clone directory")
    ret = execmd(['rm', '-f', '-r', 'manifest'])[2]
    if (ret != 0):
        cherry_pick_exit(ERROR_CODE.STATUS_RM_MANIFEST_DIR)
    logging.info("Cloning the manifest git of branch %s", branch)
    _out, err, ret = execmd([GIT, 'clone',
                        'git://%s/%s' % (GERRIT_URL, OPT.manifest),
                        'manifest',
                        '-b', branch], 300)

    if (ret != 0):
        cherry_pick_exit(ERROR_CODE.STATUS_CLONE_MANIFEST, err)


def update_manifest(branch, skip_review):
    """
    Uploads the manifest changes upon rebase
    """
    #Clone the target manifest git
    clone_manifest_git(branch)

    global dst_manifest
    global upd_project_list
    logging.info("Updating the target manifest")
    gituser = get_git_user()
    recipient = []
    os.chdir(OPT.cwd + '/manifest')
    #Creates a topic branch for the manifest changes
    #and writes the changes to default.xml
    _out, err, ret = execmd([GIT, 'branch', 'manifest-change',
                             dst_manifest.get_base_sha1()])
    if (ret != 0):
        logging.error(err)
        return ERROR_CODE.STATUS_UPDATE_MANIFEST
    _out, err, ret = execmd([GIT, 'checkout', 'manifest-change'])
    if (ret != 0):
        logging.error(err)
        return ERROR_CODE.STATUS_UPDATE_MANIFEST
    try:
        dst_manifest.write_xmldata_to_file('default.xml')
    except IOError, err:
        logging.error(err)
        return ERROR_CODE.STATUS_UPDATE_MANIFEST
    _out, err, ret = execmd([GIT, 'add', 'default.xml'])
    if (ret != 0):
        logging.error(err)
        return ERROR_CODE.STATUS_UPDATE_MANIFEST
    proj_list = ''
    for upl in upd_project_list:
        proj_list += '    ' + upl + '\n'
    commit_msg = 'Auto cherry-pick change\n\n' \
                 'Update revision(s) to branch:\n' \
                 '    ' + branch + '\n\n' \
                 'Project(s):\n' + proj_list
    _out, err, ret = execmd([GIT, 'commit', '-m', commit_msg])
    if (ret != 0):
        logging.error(err)
        return ERROR_CODE.STATUS_UPDATE_MANIFEST
    #Rebase the manifest git
    _out, err, ret = execmd([GIT, 'fetch'], 300)
    if (ret != 0):
        logging.error(err)
        return ERROR_CODE.STATUS_UPDATE_MANIFEST
    _out, err, ret = execmd([GIT, 'rebase', 'origin/' + branch], 300)
    if (ret != 0):
        logging.error("Can't rebase the manifest: %s", err)
        update_manifest_mail(branch, OPT.manifest, recipient)
        return ERROR_CODE.STATUS_UPDATE_MANIFEST
    #Push the updated manifest
    if (skip_review):
        dst_push = 'heads'
    else:
        dst_push = 'for'
    cmd = [GIT, 'push',
           'ssh://%s@%s:29418/%s' % (gituser, GERRIT_URL, OPT.manifest),
           'HEAD:refs/%s/%s' % (dst_push, branch)]

    _out, err, ret = execmd(cmd, 300)
    if (ret != 0):
        logging.error(err)
        return ERROR_CODE.STATUS_UPDATE_MANIFEST
    elif skip_review:
        email('[Cherrypick] [%s] Manifest updated' % branch,
              'Hello,\n\nThe manifest file of %s was updated and merged. '
              'Updated project(s):\n%s\n\nCherry-picker\nVersion: %s' %
              (branch, proj_list, __version__), recipient)
    else:
        email('[Cherrypick] [%s] Manifest updated' % branch,
              'Hello,\n\nThe manifest file of %s was updated and uploaded '
              'for review. Updated project(s):\n%s\n\nCherry-picker' \
              '\nVersion: %s' % (branch, proj_list, __version__), recipient)
    return ERROR_CODE.STATUS_OK


def create_branch(target_branch, b_commit_list, t_commit_list, git_name, sha1):
    """
    Create branch from sha1 if something to cherry pick
    """
    global dst_manifest
    global manifest_change_required
    global upd_project_list
    delta_list = []
    delta_list += b_commit_list
    for cmt in b_commit_list:
        for t_cmt in t_commit_list:
            if cmt.cmp(t_cmt):
                delta_list.remove(cmt)
                break
    if not delta_list:
        return False
    delta_list = dms_get_fix_for(delta_list)
    if delta_list:
        #We have some change to cherry pick, so need to create branch
        gituser = get_git_user()
        try:
            gerrit = Gerrit(gerrit_user=gituser)
        except GerritError, e:
            logging.error("Gerrit error: %s", e)
            return False

        #take a commit
        cmt = delta_list[0]
        recipient = None
        if OPT.dry_run:
            recipient = []
        else:
            try:
                recipient = gerrit.collect_email_addresses(cmt.commit)[0]
            except GerritError, e:
                logging.error("Unable to get recipient email: %s", e)
        ret = execmd([GIT, 'show-ref', '-q', '--verify',
                      'refs/remotes/origin/' + target_branch])[2]
        if ret == 0:
            logging.info("Branch %s already available for %s. " \
                         "Manifest file will be updated.",
                         target_branch, git_name)
            dst_manifest.update_revision(git_name, target_branch)
            manifest_change_required = True
            upd_project_list.append(git_name)
            return True
        if OPT.dry_run:
            logging.info("Dry run: %s branch for %s will not be created.",
                         target_branch, git_name)
            return True
        else:
            cmd = [GIT, 'push', 'ssh://%s@%s:29418/%s.git' %
                   (gituser, GERRIT_URL, git_name),
                   '%s:refs/heads/%s' % (sha1, target_branch)]
            log, err, ret = execmd(cmd)
            if ret == 0:
                logging.info("Branch %s created on %s.  Branch point: %s",
                             target_branch, git_name, sha1)
                logging.info(log)
                execmd([GIT, 'fetch'])
                dst_manifest.update_revision(git_name, target_branch)
                manifest_change_required = True
                upd_project_list.append(git_name)
                if recipient:
                    create_branch_mail(cmt.target, cmt.name, sha1, recipient)
                return True
            else:
                logging.error("Failed to create %s branch on %s. " \
                              "Branch point: %s",
                              target_branch, git_name, sha1)
                logging.error(log)
                logging.error(err)
                return False
    else:
        return False


def collect_fix_dms(branch, commit_begin, project, log_file):
    """
    Collect FIX=DMSxxxxxxx and commit id from the logs.
    return the list of commits.
    """
    commit_list = []
    git_log = execmd([GIT, 'log', '--pretty=fuller',
                      commit_begin + '..' + branch])[0]
    log_file.write(git_log + '\n')
    git_log_list = git_log.split('\n')
    commit_id, author_date, title = '', '', ''
    for log_str in git_log_list:
        if re.match(r'^commit\s.*?', log_str):
            commit_id = log_str.split(' ')[1]  # sha1
        elif re.match(r'AuthorDate: ', log_str):
            author_date = log_str
        elif re.match(r'CommitDate:', log_str):  # get title 2 lines below it
            title = git_log_list[git_log_list.index(log_str) + 2].strip()
        elif re.match(r'^\s*?FIX\s*=\s*DMS[0-9]+', log_str):  # "FIX=DMSxxxxx"
            dms_str = log_str.split('=')
            dms_id = dms_str[1].strip()     # DMSxxxxxxx
            if (OPT.exclude_commit and
                commit_id in OPT.exclude_commit.split(',')):
                continue                    # exclude commit
            if OPT.exclude_dms and dms_id in OPT.exclude_dms.split(','):
                continue                    # exclude dms
            rev, path, name = project.split(',')
            cmt = Commit(target=rev, path=path, name=name, dms=dms_id,
                         commit=commit_id, author_date=author_date,
                         title=title)
            commit_list.append(cmt)

    return commit_list


def dms_get_fix_for(commit_list):
    """
    Collect DMS status from DMS server. Collect only the commits match with
    OPT.tag_list
    """
    global dms_tags
    commit_tag_list = []
    if not commit_list:
        return commit_tag_list

    # Remove duplicates from the list
    dmss = list(set([x.dms for x in commit_list]))
    if not dmss:
        return commit_tag_list

    try:
        logging.info("DMS tag request (%s) for %d issue(s): %s",
                     OPT.dms_tag_server, len(dmss), ','.join(dmss))
        server = DMSTagServer(OPT.dms_tag_server, timeout=120)
        tags_dmss = server.dms_for_tags(dmss, dms_tags, OPT.target_branch)
        if tags_dmss:
            for cmt in commit_list:
                if cmt.dms in tags_dmss:
                    commit_tag_list.append(cmt)
        return commit_tag_list
    except DMSTagServerError, e:
        # Report the error and quit.
        logging.error('DMS tag server error: %s', e)
        cherry_info = '\n'.join([x.get_commit_info() for x in commit_list])
        recipient = []
        subject = '[Cherrypick] DMS tag server error [%s]' % \
                  OPT.target_branch
        body = TAG_SERVER_FAILED_NOTIFICATION_MAIL % \
                (OPT.dms_tag_server, e, OPT.target_branch,
                cherry_info, __version__)
        email(subject, body, recipient)
        cherry_pick_exit(ERROR_CODE.STATUS_DMS_SRV,
                         'DMS Tag Server Error. Aborting.')


def create_cherry_pick_list(commit_tag_list):
    """
    Make unique list and save it to file
    """
    target_branch = OPT.target_branch
    #make single commit for multiple dms
    commit_dict = {}
    for cmt in commit_tag_list:
        key = cmt.commit
        if key in commit_dict:
            commit_dict[key].dms += '-' + cmt.dms
        else:
            commit_dict[key] = cmt
    unique_commit_tag_list = [v for v in commit_dict.values()]

    os.chdir(OPT.cwd)
    log_to_file('\n'.join(str_list(unique_commit_tag_list)),
                file_name="%s_cherrypick.csv" % (target_branch),
                info="Cherries", echo=True)
    return unique_commit_tag_list


def get_git_user():
    """
    Collect git user id
    """
    gituser = None
    if OPT.gerrit_user:
        gituser = OPT.gerrit_user
    else:
        gituser = execmd([GIT, 'config', '--get', 'user.email'])[0]
        if gituser:
            gituser = gituser.split('@')[0]
        if not gituser:
            message = "user.email is not configured for git yet.\n" \
                      "Please run this after git configuration is done."
            cherry_pick_exit(ERROR_CODE.STATUS_GIT_USR, message)
    return gituser


def cherry_pick(unique_commit_list, target_branch):
    """
    1. Create the topic-cherrypick branch
    2. Collect email addresses for review
    3. Cherry pick the commit
    4. Change the commit message
    5. push it to gerrit
    6. save the status to a file
    7. Move out from topic branch
    8. delete topic-cherrypick branch
    """
    ret_err = ERROR_CODE.STATUS_OK
    gituser = get_git_user()

    #keep the result here
    cherrypick_result = []

    global cmserver

    logging.info("Cherry pick starting")

    try:
        gerrit = Gerrit(gerrit_user=gituser)
    except GerritError, e:
        cherry_pick_exit(ERROR_CODE.STATUS_GERRIT_ERR, "Gerrit error: %s" % e)

    for cmt in unique_commit_list:
        # Check if the commit has already been uploaded to Gerrit
        # but was not registered in the status server.
        found = False
        try:
            cherry = gerrit.is_commit_available(cmt)
            if cherry:
                # It was found.  Update it in the status server.
                found = True
                logging.info('%s: commit %s already in Gerrit: Change %d, %s',
                             cmt.name, cmt.commit, cherry.change_nr,
                             cherry.status)
                if not OPT.dry_run:
                    try:
                        cmserver.update_cherrypick_status(OPT.manifest,
                                                          OPT.source_branch,
                                                          target_branch,
                                                          cherry)
                    except CMServerError, e:
                        logging.error("CM Server Error: %s", e)
        except GerritError, e:
            logging.error("Gerrit error: %s", e)

        # If we've found this commit, no need to cherry pick it
        if found:
            continue

        # Start the cherry pick
        try:
            pick_result = ''
            change_id = None
            logging.info('Cherry picking %s', cmt)
            os.chdir(os.path.join(OPT.cwd, cmt.path))

            # Check out the topic branch
            topic_branch = "cherrypick-%s-%s" % \
                            (cmt.commit, time.strftime("%Y%m%d%H%M%S"))
            r_cmd = [GIT, 'checkout', '-b', topic_branch, cmt.target_origin]
            git_log, err, ret = execmd(r_cmd)
            if ret == 0:
                reviewers = []
                url = None
                try:
                    reviewers, url = gerrit.collect_email_addresses(cmt.commit)
                except GerritError, e:
                    logging.error("Error collecting email addresses: %s", e)

                # If we were unable to get the source change URL, use the
                # sha1 instead.
                if not url:
                    url = cmt.commit

                # Add reviewers specified in options
                if OPT.reviewers:
                    reviewers += OPT.reviewers.split(',')

                # Send failure notification email to the reviewers
                # when not in dry-run mode.
                emails = []
                if not OPT.dry_run:
                    emails += reviewers

                # now cherry pick
                r_cmd = [GIT, 'cherry-pick', '-x', cmt.commit]
                git_log, err, ret = execmd(r_cmd)
                if ret == 0:
                    #now edit commit msg to remove change id
                    commit_msg = open(".git/COMMIT_EDITMSG",
                                      'r').read().split('\n')
                    commit_msg_file = open(".git/COMMIT_EDITMSG", 'w')
                    for msg in commit_msg:
                        if not re.match(r"^Change-Id: \S+\s*$", msg):
                            commit_msg_file.write(msg + '\n')
                    commit_msg_file.close()

                    #amend to add a new change id
                    git_log, err, ret = execmd([GIT, 'commit', '--amend',
                                                '-F', '.git/COMMIT_EDITMSG'])
                    push_attempts = 0
                    push_ok = False
                    while (push_attempts < MAX_PUSH_ATTEMPTS) and (not push_ok):
                        push_attempts += 1
                        cmd = [GIT, 'push',
                               'ssh://%s@%s:29418/%s.git' %
                               (gituser, GERRIT_URL, cmt.name),
                               'HEAD:refs/for/%s' % cmt.target]
                        if OPT.dry_run:
                            cmd.append('--dry-run')
                        git_log, err, ret = execmd(cmd, timeout=90)
                        logging.info(err)
                        if ret == 0:
                            push_ok = True
                            if OPT.dry_run:
                                pick_result = 'Dry-run ok'
                            else:
                                match = re.search('https?://%s/([0-9]+)'
                                                  % GERRIT_URL, err)
                                if match:
                                    # Get the change URL and ID
                                    pick_result = match.group(0)
                                    change_id = match.group(1)
                                    try:
                                        gerrit.add_reviewers(change_id,
                                                             reviewers)
                                        if OPT.approve:
                                            gerrit.approve(change_id)
                                    except GerritError, e:
                                        logging.error("Gerrit error: %s", e)
                                else:
                                    pick_result = 'Failed to find Gerrit URL ' \
                                                  'after push'
                        else:
                            if push_attempts == MAX_PUSH_ATTEMPTS:
                                logging.error(
                                    'Failed to push %d times, giving up.',
                                    MAX_PUSH_ATTEMPTS)
                                pick_result = 'Failed to push to Gerrit'
                            else:
                                logging.info('git push failed.  Retrying...')
                else:
                    if 'the conflicts' in err:
                        pick_result = 'Failed due to merge conflict'
                    elif 'is a merge but no -m' in err:
                        pick_result = 'Failed because it is a merge commit'
                    elif 'nothing to commit' in git_log:
                        pick_result = 'Already merged'
                    else:
                        pick_result = 'Failed due to unknown reason'
                    logging.error(err)
                    logging.error("Resetting to HEAD")
                    git_log, err, ret = execmd([GIT, 'reset', '--hard'])
                    logging.info(git_log)

                # If something went wrong, send failure mail.
                if pick_result.startswith("Failed"):
                    conflict_mail(target_branch, url, cmt.commit,
                                  emails, pick_result)
            else:
                pick_result = '%s %s' % (git_log, err)
                logging.info(pick_result)
        except Exception, e:
            logging.error("Exception occurred: %s", e)
        finally:
            # Move to origin and delete topic branch
            git_log, err, ret = execmd([GIT, 'checkout', cmt.target_origin])
            logging.info(git_log)
            git_log, err, ret = execmd([GIT, 'branch', '-D', topic_branch])
            logging.info(git_log)

        if OPT.dry_run:
            match = re.search('Dry-run ok', pick_result)
        else:
            match = re.search('https?://%s' % GERRIT_URL, pick_result)
        if not match:
            ret_err = ERROR_CODE.STATUS_CHERRYPICK_FAILED

        cherrypick_result.append(str(cmt) + ',' + pick_result)
        if not OPT.dry_run:
            try:
                cherry = CherrypickStatus()
                cherry.sha1 = cmt.commit
                cherry.project = cmt.name
                cherry.branch = target_branch
                if change_id is not None:
                    cherry.set_change_nr(int(change_id))
                else:
                    cherry.set_message(pick_result)
                cherry.set_dms(cmt.dms)
                cmserver.update_cherrypick_status(OPT.manifest,
                                                  OPT.source_branch,
                                                  target_branch,
                                                  cherry)
            except (CMServerError, CherrypickStatusError), e:
                logging.error("Error updating cherry pick status: %s", e)

    os.chdir(OPT.cwd)

    # Report the result if any cherry pick done
    if cherrypick_result:
        cherrypick_result.sort()
        infomsg = "New cherries picked"
        if OPT.dry_run:
            infomsg += " (dry run)"
        log_to_file('\n'.join(cherrypick_result),
                    file_name="%s_cherrypick_result.csv" % (target_branch),
                    info=infomsg, echo=True)
    else:
        logging.info("No new cherries")
    return ret_err


def execmd(cmd, timeout=30):
    """
    Execute a command in a new child process. The child process is killed
    if the timeout is up.
    """
    kill_check = threading.Event()

    def kill_process_after_timeout(pid):
        """Callback method to kill process `pid` on timeout."""
        p = subprocess.Popen(['ps', '--ppid', str(pid)],
                             stdout=subprocess.PIPE)
        child_pids = []
        for line in p.stdout:
            if len(line.split()) > 0:
                local_pid = (line.split())[0]
                if local_pid.isdigit():
                    child_pids.append(int(local_pid))
        os.kill(pid, signal.SIGKILL)
        for child_pid in child_pids:
            os.kill(child_pid, signal.SIGKILL)
        kill_check.set()  # tell the main routine that we had to kill
        return

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        watchdog = threading.Timer(timeout,
                                   kill_process_after_timeout,
                                   args=(process.pid, ))
        watchdog.start()
        out, err = process.communicate()
        result_out = ''.join(out).strip()
        result_err = ''.join(err).strip()
        watchdog.cancel()  # if it's still waiting to run
        if kill_check.isSet():
            result_err = "Timeout: the command \"%s\" did not " \
                         "complete in %d sec." % (" ".join(cmd), timeout)
        kill_check.clear()
        if process.poll() != 0:
            logging.error('Error executing: %s', " ".join(cmd))
        return result_out, result_err, process.poll()
    except OSError, exp:
        logging.error(exp)
    except KeyboardInterrupt:
        kill_process_after_timeout(process.pid)
        watchdog.cancel()
        print
        cherry_pick_exit(ERROR_CODE.STATUS_USER_ABORTED)


def log_to_file(contents, file_name=None, info=None, echo=False):
    """ Open the file specified by `file_name` and write `contents` to it.
    """
    try:
        with open(file_name, 'wb') as f:
            f.write(contents)
    except Exception, e:
        logging.error("Error writing to file %s: %s", file_name, e)

    if echo:
        if info:
            logging.info((10 * '=') + info + (10 * '='))
        logging.info(contents)


def create_branch_mail(branch, name, sha1, recipient):
    """
    Mail to notify branch creation.
    """
    subject = ('[Cherrypick] [%s] New branch created on %s' %
               (branch, name))
    body = ('Hello,\n\nBranch %s has been created on %s.' % (branch, name) +
            '\nBranch point: %s' % sha1 +
            '\nThe manifest for %s will be updated.' % branch +
            '\n\nRegards,\nCherry-picker.\nVersion: %s' % __version__)
    email(subject, body, recipient)


def update_manifest_mail(branch, name, recipient):
    """
    Mail to update manifest request.
    """
    subject = ('[Cherrypick] [%s] Manifest is not updated for %s' %
               (branch, name))
    body = ('Hello,\n\nThe manifest file of %s branch ' % branch +
            'can\'t be updated for the following project(s):\n%s\n\n' % name +
            'Please update the manifest file ' +
            'and reply to this mail with the Gerrit link.' +
            '\n\nThanks,\nCherry-picker.\nVersion: %s' % __version__)
    email(subject, body, recipient)


def conflict_mail(branch, url, change_id, recipient, result):
    """
    Mail for cherry pick conflict.
    """
    subject = ('[Cherrypick] [%s] cherry-pick of change %s has failed.' %
               (branch, change_id))
    body = CHERRY_PICK_FAILED_NOTIFICATION_MAIL % \
           (url, branch, result, branch, '\n'.join(recipient),  __version__)
    email(subject, body, recipient)


def email(subject, body, recipient):
    '''
    Email function
    '''
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header

    sender = OPT.mail_sender
    msg = MIMEText(body)
    msg['Subject'] = Header(subject)
    if not OPT.dry_run:
        recipient.append(sender)
    msg['From'] = sender
    msg['To'] = ', '.join(recipient)
    if recipient:
        # Send the email via our own SMTP server.
        try:
            mailer = smtplib.SMTP(SMTP_MAIL_SERVER)
            mailer.sendmail(sender, recipient, msg.as_string())
            mailer.quit()
        except smtplib.SMTPException, exp:
            logging.error('Failed to send mail due to SMTP error: %s', exp[1])
            return
        logging.info('Mail sent to %s for %s', ', '.join(recipient), subject)
    else:
        logging.error('Mail not sent: No recipients')
        logging.error('%s\n%s', subject, body)


def main():
    """
    Cherry pick main function
    """
    global manifest_change_required
    global OPT_PARSER, OPT
    global dms_tags
    global cmserver
    OPT_PARSER = option_parser()
    OPT = OPT_PARSER.parse_args()[0]

    logging.basicConfig(format='[%(levelname)s] %(message)s',
                        level=logging.WARNING)

    if not OPT.source_branch:
        cherry_pick_exit(ERROR_CODE.STATUS_ARGS,
                         "Must pass source (-s) branch name")

    if not OPT.target_branch:
        cherry_pick_exit(ERROR_CODE.STATUS_ARGS,
                         "Must pass target (-t) branch name")

    if (OPT.verbose > 1):
        level = logging.DEBUG
    elif (OPT.verbose > 0):
        level = logging.INFO

    logging.getLogger().setLevel(level)

    info_msg = "Cherrypick.py " + __version__
    if OPT.dry_run:
        info_msg += " (dry run)"
    logging.info(info_msg)

    if not OPT.cwd:
        OPT.cwd = os.getcwd()
        logging.info("--work-dir not specified, using current dir: %s", OPT.cwd)
    OPT.cwd = os.path.abspath(OPT.cwd)

    if not os.path.exists(os.path.join(OPT.cwd, '.repo')):
        cherry_pick_exit(ERROR_CODE.STATUS_REPO,
                         'repo is not installed in %s. Use "repo init -u ' \
                         'url" to install it.' % OPT.cwd)

    # Get DMS tags and cherrypick policy from the CM server
    try:
        logging.info("Get DMS tags and cherry pick policy from CM server...")
        cmserver = CMServer()
        data = cmserver.get_branch_config(OPT.manifest)
        if not data:
            cherry_pick_exit(ERROR_CODE.STATUS_CM_SERVER, "Empty branch config")
        branch_config = BranchPolicies(StringIO.StringIO(data))
        dms_tags = branch_config.get_branch_tagnames(OPT.target_branch)
        if not dms_tags:
            cherry_pick_exit(ERROR_CODE.STATUS_ARGS,
                             "Config must specify DMS tags")
        logging.info("DMS tags: %s", ", ".join(dms_tags))
        cherry_policy = branch_config.get_cherrypick_policy(OPT.source_branch,
                                                            OPT.target_branch)
        if not cherry_policy:
            cherry_pick_exit(ERROR_CODE.STATUS_ARGS,
                             "No cherrypick policy: %s to %s" % \
                             (OPT.source_branch, OPT.target_branch))
    except BranchPolicyError, e:
        cherry_pick_exit(ERROR_CODE.STATUS_CM_SERVER,
                         "Branch Policy Error: %s" % e)
    except CherrypickPolicyError, e:
        cherry_pick_exit(ERROR_CODE.STATUS_CM_SERVER,
                         "Cherrypick Policy Error: %s" % e)
    except CMServerError, e:
        cherry_pick_exit(ERROR_CODE.STATUS_CM_SERVER, "CM Server Error: %s" % e)
    except CredentialsError, e:
        cherry_pick_exit(ERROR_CODE.STATUS_CM_SERVER,
                         "Credentials Error: %s" % e)

    if not OPT.target_branch_include:
        OPT.target_branch_include = DEFAULT_TARGET_BRANCH_INCLUDES

    args = ["%s = %s" %
            (key, value) for key, value in OPT.__dict__.iteritems()]
    logging.info("Arguments are:\n%s\n", "\n".join(args))
    status_code = ERROR_CODE.STATUS_OK

    if OPT.cwd:
        OPT.cwd = os.path.abspath(OPT.cwd)
        os.chdir(OPT.cwd)

    if not OPT.no_repo_sync:
        repo_sync()

    if  OPT.csv_file:
        commit_list = []
        if OPT.target_branch == None:
            cherry_pick_exit(ERROR_CODE.STATUS_ARGS,
                             "Must pass target (-t) branch name")
        try:
            csv = open(OPT.csv_file, 'r')
            unique_commit_list = csv.read().splitlines()
        except IOError, err:
            logging.error(err)
            cherry_pick_exit(ERROR_CODE.STATUS_FILE)
        for commit in unique_commit_list:
            prts = commit.split(',')
            if len(prts) < 5:
                logging.error('Not enough parameters in %s', commit)
                continue
            else:
                cmt = Commit(target=prts[0], path=prts[1], name=prts[2],
                             commit=prts[3], dms=prts[4])
                commit_list.append(cmt)
        if commit_list:
            status_code = cherry_pick(commit_list, OPT.target_branch)
        cherry_pick_exit(status_code)

    commit_list = get_dms_list(OPT.target_branch)
    if not commit_list:
        cherry_pick_exit(ERROR_CODE.STATUS_OK, "Nothing is found to process")

    commit_tag_list = dms_get_fix_for(commit_list)
    unique_commit_list = create_cherry_pick_list(commit_tag_list)
    if not OPT.no_push_to_gerrit:
        status_code = cherry_pick(unique_commit_list, OPT.target_branch)
    if (not OPT.dry_run and manifest_change_required):
        status_manifest = update_manifest(OPT.target_branch, OPT.skip_review)
        if (status_manifest != ERROR_CODE.STATUS_OK):
            logging.error("Failed to update the manifest")

    cherry_pick_exit(status_code)

if __name__ == '__main__':
    main()
