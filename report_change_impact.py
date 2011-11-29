#!/usr/bin/env python

"""Given a change that has been uploaded to Gerrit, checks which manifest
branch(es) will be affected when that change is eventually merged.

If any of these branches have requirements on DMS issues being mentioned
in the commit message and which tags these issues must have, the
uploaded commit is evaluated against those rules.

If more than one branch will be affected a note is added to the change
to remind the uploader that additional verification might be necessary.

The script is intended to be invoked when a change (or a new patch set
to an existing change) has been uploaded to Gerrit but it works fine for
interactive use as well.

Supports regular expression based inclusion/exclusion patterns for git
project, and both manifest branches and the destination branches of the
changes being inspected. """


import logging
import optparse
import os
import re
import sys
from xml.parsers.expat import ExpatError

from branch_policies import BranchPolicies
from commit_message import CommitMessage, CommitMessageError
from dmsutil import DMSTagServer, DMSTagServerError
import gerrit
from git import CachedGitWorkspace
from include_exclude_matcher import IncludeExcludeMatcher
import manifest
import manifestbranches
import processes
import semcutil


# The default value of the command line option to select which
# branches of the gits listed in each manifest should be examined.
DEFAULT_GIT_BRANCH_INCLUDES = [r"^"]

# The default value of the command line option to select which gits
# should be examined.
DEFAULT_GIT_INCLUDES = [r"^"]

# The default value of the command line option to select which refs
# from the manifest should be examined.
DEFAULT_MANIFEST_REF_INCLUDES = [r"^refs/remotes/origin/"]

# The default URL of the Gerrit server
DEFAULT_GERRIT_SERVER = "review.sonyericsson.net"

# The name of the host that runs the specialized DMS tag server.
DMS_TAG_SERVER_HOSTNAME = "android-cm-web.sonyericsson.net"

# Greeting to start the message that will be posted to Gerrit
MESSAGE_GREETING = "Dear uploader,"

# First part of the message about multiple systems impact
MESSAGE_MULTIPLE_SYSTEMS_PART_1 = \
"""

The commit you've uploaded will affect more than one system branch
(aka manifest), namely the following:

"""

# Second part of the message about multiple systems impact
MESSAGE_MULTIPLE_SYSTEMS_PART_2 = \
"""
Before submitting this change, make sure you don't inadvertently break
any of these branches. Depending on the branch and the nature of your
change, you may have to verify the commit separately on each branch, or
it might be safe to assume that your change will behave in the same good
manner everywhere, or one or more of the branches might be managed by
dedicated teams (i.e. it isn't your problem if it breaks because of your
change). Please use good judgement."""

# First part of the message about DMS policy violation
MESSAGE_DMS_VIOLATION_PART_1 = \
"""

One or more system branches (aka manifest branches) affected by this
change have DMS-based restrictions on which changes may be submitted.
It looks like you will violate one or more of these restrictions if you
submit this change.

"""

# Second part of the message about DMS policy violation
MESSAGE_DMS_VIOLATION_PART_2 = \
"""
This report is based on a configuration listing valid tags for each
branch, maintained by CM. If tags have been recently introduced this
configuration may be out of date. Please send an email to
DL-WW-Android-SW-CM and tell us about this.

If you think you have listed the DMS issue in the commit message but
you're still getting this report, you might not be using the correct
notation. If so, have a look at
https://wiki.sonyericsson.net/androiki/Commit_messages."""

# Message when DMS in the commit message do not have required tag
MESSAGE_DMS_TAG_REQUIRED = \
"""The change will affect the %s system branch. That branch requires all
issues listed in the commit message to have one of the following tags:
%s. One or more issues found for this commit (%s) did not conform to
this."""

# Message when no DMS found in the commit message
MESSAGE_DMS_REQUIRED = \
"""The change will affect the %s system branch. That branch requires a
DMS issue to be present in the commit message."""

# Message when no DMS found in the commit message and tag is required
MESSAGE_TAG_REQUIRED = \
""" Additionally, all issues listed must have one of the following
tags: %s."""


def _get_tagged_issues(issues, tags, target_branch):
    """Retrieves the subset of `issues` that have at least one of
    `tags` set in their "Fix For" field.
    Returns a list of issues.  If an issue does not have one of the
    tags, it is omitted from the list.
    Raises DMSTagServerError if any error occurs when retrieving tags
    from the DMS tag server.
    """
    # If the tag list is empty, we don't need to check with the tag
    # server.  Just return the same issue list.
    if not tags:
        return issues

    # Get the list of tagged issues from the tag server.
    server_conn = DMSTagServer(DMS_TAG_SERVER_HOSTNAME)
    return server_conn.dms_for_tags(",".join(issues),
                                    ",".join(tags),
                                    target_branch)


def _get_patchset_fixed_issues(options):
    """ Returns a list of issues fixed in the patchset.
    """
    try:
        logging.info("Fetching patch set %s" % options.patchset_ref)
        git = CachedGitWorkspace(
            os.path.join("git://", options.gerrit_url, options.affected_git),
            options.cache_path)
        git.fetch(options.patchset_ref)

        # Extract the commit message and find any DMS issues in it.
        errcode, msg, err = processes.run_cmd("git",
                                              "cat-file",
                                              "-p",
                                              "FETCH_HEAD",
                                              path=git.git_path)
        commit_message = CommitMessage(msg)
        return commit_message.get_fixed_issues()
    except processes.ChildExecutionError, err:
        semcutil.fatal(2, err)
    except EnvironmentError, err:
        semcutil.fatal(2, "Error extracting DMS issue information: "
                          "%s: %s" % (err.strerror, err.filename))


def _get_dms_violations(config, dmslist, affected_manifests):
    """ Checks `dmslist` against the `affected_manifests` and
    returns a list of violations, or an empty list if there are no
    violations.
    """
    violations = []
    if dmslist:
        for branch in filter(config.branch_has_policy,
                             affected_manifests):
            tagnames = config.get_branch_tagnames(branch)

            if not tagnames:
                continue

            try:
                tagged_issues = _get_tagged_issues(dmslist, tagnames, branch)
            except DMSTagServerError, e:
                semcutil.fatal(1, "DMS tag server error: %s" % e)

            invalid_issues = []
            for issue in dmslist:
                if issue not in tagged_issues:
                    invalid_issues += [issue]

            if invalid_issues:
                violations.append(MESSAGE_DMS_TAG_REQUIRED % \
                    (branch,
                     ", ".join(tagnames),
                     ", ".join(invalid_issues)))
    else:
        for branch in filter(config.branch_has_policy,
                             affected_manifests):
            msg = MESSAGE_DMS_REQUIRED % branch
            tagnames = config.get_branch_tagnames(branch)
            if tagnames:
                msg += MESSAGE_TAG_REQUIRED % ", ".join(tagnames)
            violations.append(msg)
    return violations


def _main():
    usage = "usage: %prog [options]"
    options = optparse.OptionParser(usage=usage)
    options.add_option("", "--gerrit-url", dest="gerrit_url",
                       default=DEFAULT_GERRIT_SERVER,
                       help="The URL to the Gerrit server.")
    options.add_option("-c", "--cache-path", dest="cache_path",
                       default="cache",
                       help="The path to the local directory where the " \
                           "downloaded gits are cached to avoid cloning " \
                           "them for each invocation of the script.")
    options.add_option("-m", "--manifest-path", dest="manifest_path",
                       default=None,
                       help="The path to the local directory where the " \
                           "manifest git that we should compare against " \
                           "can be found.")
    options.add_option("-p", "--policy", dest="policy_file",
                       default=None,
                       help="Name of a file containing the configuration " \
                           "of DMS policies per branch.")
    options.add_option("-u", "--gerrit-user", dest="gerrit_user",
                       default=None,
                       help="The username that should be used when logging " \
                           "into the Gerrit server with SSH. If omitted, " \
                           "the SSH client will decide the username based " \
                           "on $LOGNAME and its own configuration file " \
                           "(if present).")
    options.add_option("-v", "--verbose", dest="verbose", default=False,
                       action="store_true", help="Verbose mode.")
    options.add_option("", "--dry-run", dest="dry_run", action="store_true",
                       help="Do everything except actually add the note " \
                           "to the affected change.")
    options.add_option("", "--include-manifest-ref", dest="manifest_ref_in",
                       action="append", metavar="REGEXP",
                       default=DEFAULT_MANIFEST_REF_INCLUDES,
                       help="A regular expression that will be matched " \
                           "against the fully-qualified ref names of the " \
                           "available manifest branches to include them " \
                           "in the examination. This option can be used " \
                           "multiple times to add more expressions. The " \
                           "first use of this option will clear the default " \
                           "value (%s) before appending the new expression." %
                           ", ".join(DEFAULT_MANIFEST_REF_INCLUDES))
    options.add_option("", "--exclude-manifest-ref", dest="manifest_ref_ex",
                       action="append", metavar="REGEXP",
                       help="Same as --include-manifest-ref but for " \
                           "excluding refs from examination. Exclusion has " \
                           "higher precedence than inclusion. This option " \
                           "can also be used multiple times to add more " \
                           "expressions (default: <empty>).")
    options.add_option("", "--include-git", dest="git_in",
                       action="append", metavar="REGEXP",
                       default=DEFAULT_GIT_INCLUDES,
                       help="A regular expression that will be matched " \
                           "against the name of the git to which the " \
                           "change has been uploaded. This option can be " \
                           "used multiple times to add more expressions. " \
                           "The first use of this option will clear the " \
                           "default value (%s) before appending the new " \
                           "expression." % ", ".join(DEFAULT_GIT_INCLUDES))
    options.add_option("", "--exclude-git", dest="git_ex",
                       action="append", metavar="REGEXP",
                       help="Same as --include-git but for excluding " \
                           "gits. This option can also be used " \
                           "multiple times to add more expressions " \
                           "(default: <empty>).")
    options.add_option("", "--include-git-branch", dest="git_branch_in",
                       action="append", metavar="REGEXP",
                       default=DEFAULT_GIT_BRANCH_INCLUDES,
                       help="A regular expression that will be matched " \
                           "against the branches of the gits found in the " \
                           "manifests to include them in the examination. " \
                           "This option can be used multiple times to add " \
                           "more expressions. The first use of this option " \
                           "will clear the default value (%s) before " \
                           "appending the new expression." % \
                           ", ".join(DEFAULT_GIT_BRANCH_INCLUDES))
    options.add_option("", "--exclude-git-branch", dest="git_branch_ex",
                       action="append", metavar="REGEXP",
                       help="Same as --include-git-branch but for " \
                           "excluding branches on gits found in the " \
                           "manifests. This option can also be used " \
                           "multiple times to add more expressions " \
                           "(default: <empty>).")
    options.add_option("", "--change", dest="change_nr",
                       help="The change number to check.")
    options.add_option("", "--patchset", dest="patchset_nr",
                       help="The patchset number.")
    options.add_option("", "--patchset-ref", dest="patchset_ref",
                       help="The patch set refspec.")
    options.add_option("", "--project", dest="affected_git",
                       help="The name of the project on which the " \
                           "change is uploaded.")
    options.add_option("", "--branch", dest="affected_branch",
                       help="The name of the branch on which the " \
                           "change is uploaded.")
    (options, args) = options.parse_args()

    if not options.manifest_path:
        semcutil.fatal(1, "Path to manifest git missing. " \
                          "Use --manifest-path option.")
    if not options.change_nr:
        semcutil.fatal(1, "Change nr. missing. Use --change option.")
    if not options.patchset_nr:
        semcutil.fatal(1, "Patchset nr. missing. Use --patchset option.")
    if not options.patchset_ref:
        semcutil.fatal(1, "Patchset refspec missing. " \
                          "Use --patchset-ref option.")
    if not options.affected_git:
        semcutil.fatal(1, "Project name missing. Use --project option.")
    if not options.affected_branch:
        semcutil.fatal(1, "Branch name missing. Use --branch option.")

    try:
        change_nr = int(options.change_nr)
    except ValueError:
        semcutil.fatal(1, "Change number must be a number.")
    try:
        patchset_nr = int(options.patchset_nr)
    except ValueError:
        semcutil.fatal(1, "Patchset number must be a number.")

    if options.verbose:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
    else:
        logging.basicConfig(format='%(message)s', level=logging.ERROR)

    # If the git does not match our patterns there's no reason
    # to continue.
    git_matcher = IncludeExcludeMatcher(options.git_in, options.git_ex)
    if not git_matcher.match(options.affected_git):
        logging.info("No match for git %s" % options.affected_git)
        return 0

    # If the git branch does not match our patterns there's no reason
    # to continue.
    branch_matcher = IncludeExcludeMatcher(options.git_branch_in,
                                           options.git_branch_ex)
    if not branch_matcher.match(options.affected_branch):
        logging.info("No match for git branch %s" % options.affected_branch)
        return 0

    # Find all available manifest branches. Let `branches`
    # be a list of (full ref name, branch name) tuples.
    try:
        manifest_matcher = IncludeExcludeMatcher(options.manifest_ref_in,
                                                 options.manifest_ref_ex)
        errcode, out, err = processes.run_cmd("git", "for-each-ref",
                                              "--format=%(refname)",
                                              path=options.manifest_path)
        branches = filter(manifest_matcher.match, out.splitlines())
    except processes.ChildExecutionError, err:
        semcutil.fatal(2, "Error finding manifest branches: %s" % err)

    # If no manifest branches matched our patterns there's no reason
    # to continue.
    if not branches:
        logging.info("No match for manifest branch")
        return 0

    # Extract the manifest XML data from all manifest branches found
    # earlier. Store the subset of branches that would be affected if
    # the change is submitted in `affected_manifests`.
    affected_manifests = []
    logging.info("Extracting affected system branches from manifest data...")
    for branch in branches:
        try:
            manifests = manifestbranches.get_manifests(branch,
                                                       options.manifest_path)
            for ref, prettybranch, mfest in manifests:
                if options.affected_git in mfest and \
                        options.affected_branch == \
                            mfest[options.affected_git]["revision"]:
                    affected_manifests.append(prettybranch)
                    logging.info("- " + prettybranch)
        except processes.ChildExecutionError, err:
            semcutil.fatal(2, err)
        except manifest.ManifestParseError, err:
            logging.error("Skipping %s: %s" % (branch, err))

    message = ""

    # If more than one manifest is affected by this change, craft
    # an informative message.
    if len(affected_manifests) > 1:
        message = MESSAGE_GREETING + MESSAGE_MULTIPLE_SYSTEMS_PART_1

        for branch in affected_manifests:
            message += "* %s\n" % branch

        message += MESSAGE_MULTIPLE_SYSTEMS_PART_2
    else:
        logging.info("No impact on multiple system branches")

    # If a policy configuration is specified, check that the commit follows
    # the policy.
    if options.policy_file:
        try:
            config = BranchPolicies(options.policy_file)
        except ExpatError, err:
            semcutil.fatal(2, "Error parsing %s: %s" % \
                (options.policy_file, err))

        # Check this commit's DMS tags if at least one affected manifest
        # branch has a policy associated with it.
        if not filter(config.branch_has_policy, affected_manifests):
            logging.info("No affected system branches with DMS tag policy")
        else:
            # Find the DMS issue(s) listed in the commit message of this patch
            # set.
            dmslist = _get_patchset_fixed_issues(options)
            if not len(dmslist):
                logging.info("No DMS found in commit message")
            else:
                logging.info("Found DMS: " + ", ".join(dmslist))

            violations = _get_dms_violations(config, dmslist,
                                             affected_manifests)

            if violations:
                if not message:
                    message = MESSAGE_GREETING
                message += MESSAGE_DMS_VIOLATION_PART_1

                for violation in violations:
                    # Gerrit creates new bullet items when it gets newline
                    # characters within a bullet list paragraph, so unless
                    # we remove the newlines from the violation texts the
                    # resulting bullet list will contain multiple bullets
                    # and look crappy.
                    message += "* %s\n" % violation.replace("\n", " ")

                message += MESSAGE_DMS_VIOLATION_PART_2
            else:
                logging.info("No DMS violations")
    else:
        logging.info("No DMS policy")

    # If any message has been generated, post it as a note to the change.
    if message:
        logging.info(message)
        if not options.dry_run:
            try:
                gerrit_conn = \
                    gerrit.GerritSshConnection(options.gerrit_url,
                                               username=options.gerrit_user)
                gerrit_conn.review_patchset(change_nr=change_nr,
                                            patchset=patchset_nr,
                                            message=message)
            except gerrit.GerritSshConfigError, err:
                semcutil.fatal(1, "Error: getting Gerrit ssh config: %s" % err)
            except processes.ChildExecutionError, err:
                semcutil.fatal(2, "Error scoring change: %s" % err)

if __name__ == "__main__":
    try:
        sys.exit(_main())
    except KeyboardInterrupt:
        sys.exit(1)
