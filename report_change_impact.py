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
import sys
from xml.parsers.expat import ExpatError

from branch_policies import BranchPolicyError
from cm_server import CMServer, CMServerError
from commit_message import CommitMessage
from dmsutil import DMSTagServer, DMSTagServerError
import gerrit
from include_exclude_matcher import IncludeExcludeMatcher
import manifest
import manifestbranches
import processes
from retry import retry
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

# Default value (kB) to use when checking commit size.
DEFAULT_MAX_COMMIT_SIZE = 0

# Filename of the commit-size script
_COMMIT_SIZE_SCRIPT = "commit_size.sh"

# This file's location
_mydir = os.path.abspath(os.path.dirname(__file__))

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
notation. If so, have a look at the commit message guideline:

https://wiki.sonyericsson.net/androiki/Commit_messages"""

# Message when DMS in the commit message do not have required tag
MESSAGE_DMS_TAG_REQUIRED = \
"""The change will affect the %s system branch. That branch requires all
issues listed in the commit message to be accepted by triage with one of the
following tags: %s. One or more issues found for this commit (%s) did not
conform to this."""

# Message when no DMS found in the commit message
MESSAGE_DMS_REQUIRED = \
"""The change will affect the %s system branch. That branch requires a
DMS issue to be present in the commit message."""

# Message when no DMS found in the commit message and tag is required
MESSAGE_TAG_REQUIRED = \
""" Additionally, all issues listed must be accepted by triage with one of the
following tags: %s."""

# Message when the commit is too large
MESSAGE_COMMIT_TOO_LARGE = \
"""

WARNING: Your commit is very large (%s kB).

Please make sure that you don't commit large binary files as git
does not handle these very efficiently.

If you are committing test input (or similar), you might want to
consider saving them outside the git repository."""


class ChangeImpactCheckerError(Exception):
    """ Raised when an error occurs during change impact check. """


def _find_commit_size_script():
    '''Attempt to find the script that will be used to check the size
    of the commit.
    Return the absolute path to the script.
    Raise an Exception if it could not be found.
    '''
    script_file = os.path.join(_mydir, _COMMIT_SIZE_SCRIPT)
    if os.path.exists(script_file):
        return script_file
    raise Exception("Could not find %s" % _COMMIT_SIZE_SCRIPT)


@retry(DMSTagServerError, tries=3, backoff=2, delay=10)
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
    return server_conn.dms_for_tags(issues, tags, target_branch)


@retry(ChangeImpactCheckerError, tries=2, backoff=2, delay=30)
def _get_patchset_fixed_issues(gerrit_handle, revision):
    """ Returns a list of issues fixed in the patchset specified by `revision`.
    """
    results = gerrit_handle.query(revision)
    if not results:
        raise ChangeImpactCheckerError("Gerrit didn't find revision %s" % \
                                       revision)
    # Extract the commit message and find any DMS issues in it.
    commit_message = CommitMessage(results[0]["commitMessage"])
    return commit_message.get_fixed_issues()


def _get_dms_violations(config, dmslist, affected_manifests):
    """ Checks `dmslist` against the `affected_manifests` and returns a
    list of violations (empty if there are none), code review score, and
    verify score.
    """
    violations = []
    code_review = None
    verify = None

    for branch in filter(config.branch_requires_dms,
                         affected_manifests):
        msg = None
        if dmslist:
            tagnames = config.get_branch_tagnames(branch)

            # If this branch does not require DMS tags, there is no
            # need to process further.
            if not tagnames:
                continue

            logging.info("Branch %s requires tags: %s",
                         branch, ', '.join(tagnames))

            try:
                tagged_issues = _get_tagged_issues(dmslist, tagnames, branch)
            except DMSTagServerError, e:
                semcutil.fatal(1, "DMS tag server error: %s" % e)

            # Find any DMS issues that are not tagged with the
            # required tag(s) for this branch.
            invalid_issues = []
            for issue in dmslist:
                if issue not in tagged_issues:
                    invalid_issues += [issue]

            if invalid_issues:
                msg = MESSAGE_DMS_TAG_REQUIRED % (branch,
                                                  ", ".join(tagnames),
                                                  ", ".join(invalid_issues))
        else:
            msg = MESSAGE_DMS_REQUIRED % branch
            tagnames = config.get_branch_tagnames(branch)
            if tagnames:
                msg += MESSAGE_TAG_REQUIRED % ", ".join(tagnames)

        if msg:
            violations.append(msg)
            _code_review, _verify = config.get_branch_score_values(branch)
            if _code_review:
                if code_review is None or _code_review < code_review:
                    code_review = _code_review
            if _verify:
                if verify is None or _verify < verify:
                    verify = _verify

    return violations, code_review, verify


def _main():
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("", "--gerrit-url", dest="gerrit_url",
                      default=DEFAULT_GERRIT_SERVER,
                      help="The URL to the Gerrit server.")
    parser.add_option("-m", "--manifest-name", dest="manifest_name",
                      default="platform/manifest",
                      help="The project name of the manifest git that should " \
                          "be used to check impact of changes.")
    parser.add_option("-u", "--gerrit-user", dest="gerrit_user",
                      default=None,
                      help="The username that should be used when logging " \
                          "into the Gerrit server with SSH. If omitted, " \
                          "the SSH client will decide the username based " \
                          "on $LOGNAME and its own configuration file " \
                          "(if present).")
    parser.add_option("-v", "--verbose", dest="verbose", default=0,
                      action="count", help="Verbose logging.")
    parser.add_option("", "--dry-run", dest="dry_run", action="store_true",
                      help="Do everything except actually add the note " \
                          "to the affected change.")
    parser.add_option("", "--include-manifest-ref", dest="manifest_ref_in",
                      action="append", metavar="REGEXP", default=[],
                      help="A regular expression that will be matched " \
                          "against the fully-qualified ref names of the " \
                          "available manifest branches to include them " \
                          "in the examination. This option can be used " \
                          "multiple times to add more expressions. The " \
                          "first use of this option will clear the default " \
                          "value (%s) before appending the new expression." %
                          ", ".join(DEFAULT_MANIFEST_REF_INCLUDES))
    parser.add_option("", "--exclude-manifest-ref", dest="manifest_ref_ex",
                      action="append", metavar="REGEXP",
                      help="Same as --include-manifest-ref but for " \
                          "excluding refs from examination. Exclusion has " \
                          "higher precedence than inclusion. This option " \
                          "can also be used multiple times to add more " \
                          "expressions (default: <empty>).")
    parser.add_option("", "--include-git", dest="git_in",
                      action="append", metavar="REGEXP", default=[],
                      help="A regular expression that will be matched " \
                          "against the name of the git to which the " \
                          "change has been uploaded. This option can be " \
                          "used multiple times to add more expressions. " \
                          "The first use of this option will clear the " \
                          "default value (%s) before appending the new " \
                          "expression." % ", ".join(DEFAULT_GIT_INCLUDES))
    parser.add_option("", "--exclude-git", dest="git_ex",
                      action="append", metavar="REGEXP",
                      help="Same as --include-git but for excluding " \
                          "gits. This option can also be used " \
                          "multiple times to add more expressions " \
                          "(default: <empty>).")
    parser.add_option("", "--include-git-branch", dest="git_branch_in",
                      action="append", metavar="REGEXP", default=[],
                      help="A regular expression that will be matched " \
                          "against the branches of the gits found in the " \
                          "manifests to include them in the examination. " \
                          "This option can be used multiple times to add " \
                          "more expressions. The first use of this option " \
                          "will clear the default value (%s) before " \
                          "appending the new expression." % \
                          ", ".join(DEFAULT_GIT_BRANCH_INCLUDES))
    parser.add_option("", "--exclude-git-branch", dest="git_branch_ex",
                      action="append", metavar="REGEXP",
                      help="Same as --include-git-branch but for " \
                          "excluding branches on gits found in the " \
                          "manifests. This option can also be used " \
                          "multiple times to add more expressions " \
                          "(default: <empty>).")
    parser.add_option("", "--change", dest="change_nr", type="int",
                      help="The change number to check.")
    parser.add_option("", "--patchset", dest="patchset_nr", type="int",
                      help="The patchset number.")
    parser.add_option("", "--project", dest="project",
                      help="The name of the project on which the " \
                          "change is uploaded.")
    parser.add_option("", "--branch", dest="affected_branch",
                      help="The name of the branch on which the " \
                          "change is uploaded.")
    parser.add_option("", "--revision", dest="revision",
                      help="The patchset revision.")
    parser.add_option("", "--commit-size", dest="commit_size",
                      help="Limit (kB) before warning about commit size " \
                           "(default %d).  Setting 0 disables this " \
                           "warning." % DEFAULT_MAX_COMMIT_SIZE,
                      type="int", default=DEFAULT_MAX_COMMIT_SIZE)
    (options, _args) = parser.parse_args()

    if not os.path.isdir(options.manifest_name):
        semcutil.fatal(1, "Manifest path %s does not exist" % \
                          options.manifest_name)
    if not options.change_nr:
        semcutil.fatal(1, "Change nr. missing. Use --change option.")
    if not options.patchset_nr:
        semcutil.fatal(1, "Patchset nr. missing. Use --patchset option.")
    if not options.project:
        semcutil.fatal(1, "Project name missing. Use --project option.")
    if not options.affected_branch:
        semcutil.fatal(1, "Branch name missing. Use --branch option.")
    if not options.revision:
        semcutil.fatal(1, "Patchset revision missing. Use --revision option.")

    level = logging.WARNING
    logging.basicConfig(format='[%(levelname)s] %(message)s',
                        level=level)
    if (options.verbose > 1):
        level = logging.DEBUG
    elif (options.verbose > 0):
        level = logging.INFO
    logging.getLogger().setLevel(level)

    # Use default patterns unless the user has specified replacement
    # patterns explicitly.
    if not options.git_in:
        options.git_in = DEFAULT_GIT_INCLUDES
    if not options.git_branch_in:
        options.git_branch_in = DEFAULT_GIT_BRANCH_INCLUDES
    if not options.manifest_ref_in:
        options.manifest_ref_in = DEFAULT_MANIFEST_REF_INCLUDES

    # If the git does not match our patterns there's no reason
    # to continue.
    git_matcher = IncludeExcludeMatcher(options.git_in, options.git_ex)
    if not git_matcher.match(options.project):
        logging.info("No match for git %s", options.project)
        return 0

    # If the git branch does not match our patterns there's no reason
    # to continue.
    branch_matcher = IncludeExcludeMatcher(options.git_branch_in,
                                           options.git_branch_ex)
    if not branch_matcher.match(options.affected_branch):
        logging.info("No match for git branch %s", options.affected_branch)
        return 0

    # Find all available manifest branches. Let `branches`
    # be a list of (full ref name, branch name) tuples.
    try:
        manifest_matcher = IncludeExcludeMatcher(options.manifest_ref_in,
                                                 options.manifest_ref_ex)
        _ret, out, _err = processes.run_cmd("git", "for-each-ref",
                                            "--format=%(refname)",
                                            path=options.manifest_name)
        branches = filter(manifest_matcher.match, str(out).splitlines())
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
    logging.info("Finding %s branches affected by change %d...",
                 options.manifest_name, options.change_nr)
    for branch in branches:
        try:
            manifests = manifestbranches.get_manifests(branch,
                                                       options.manifest_name)
            for _ref, prettybranch, mfest in manifests:
                if options.project in mfest and \
                        options.affected_branch == \
                            mfest[options.project]["revision"]:
                    affected_manifests.append(prettybranch)
                    logging.info("- %s", prettybranch)
        except processes.ChildExecutionError, err:
            logging.error("Unable to get manifest branch info: %s", err)
        except manifest.ManifestParseError, err:
            logging.error("Unable to parse manifest %s: %s", branch, err)

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

    code_review = None
    verify = None

    try:
        gerrit_handle = gerrit.GerritSshConnection(options.gerrit_url,
                                                   username=options.gerrit_user)
    except gerrit.GerritSshConfigError, err:
        semcutil.fatal(1, "Error establishing connection to Gerrit: %s" % err)

    # Get the branch configs for the specified manifest.
    logging.info("Getting branch configuration from CM server...")
    try:
        server = CMServer()
        config = server.get_branch_config(options.manifest_name)
    except (BranchPolicyError, CMServerError, ExpatError, IOError), err:
        semcutil.fatal(2, "Error getting branch configuration for %s: %s" % \
                          (options.manifest_name, err))

    # Check that the commit follows the policy.

    # Check this commit's DMS tags if at least one affected manifest
    # branch has a policy associated with it.
    if not filter(config.branch_has_policy, affected_manifests):
        logging.info("No affected system branches with DMS tag policy")
    else:
        logging.info("Checking DMS policies...")
        # Find the DMS issue(s) listed in the commit message of this patch
        # set.
        try:
            dmslist = _get_patchset_fixed_issues(gerrit_handle,
                                                 options.revision)
            if not len(dmslist):
                logging.info("No DMS found in commit message")
            else:
                logging.info("Found DMS: %s", ", ".join(dmslist))
        except (ChangeImpactCheckerError, gerrit.GerritQueryError), err:
            semcutil.fatal(2, "Error extracting DMS issue information: "
                              "%s:" % err)

        violations, code_review, verify = \
            _get_dms_violations(config, dmslist, affected_manifests)

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

    # Check that the size of the commit is not too large
    if options.commit_size > 0:
        # This does not work as expected.  Disable for now.
        logging.info("commit size check is disabled!")
        #try:
        #    script = _find_commit_size_script()
        #    _ret, out, err = processes.run_cmd([script])
        #    commit_size = int(out)
        #    logging.info("Commit size: %d", commit_size)
        #    if commit_size > options.commit_size:
        #        if not message:
        #            message = MESSAGE_GREETING
        #        message += MESSAGE_COMMIT_TOO_LARGE % commit_size
        #except (ValueError, processes.ChildExecutionError), e:
        #    logging.error("Failed to check commit size: %s", e)

    # If any message has been generated, post it as a note to the change
    # along with code review and verify scores.
    if message:
        logging.info("\nReview message: \n====\n%s\n====", message)
        logging.info("\nCode review: %s", code_review)
        logging.info("Verify: %s", verify)

        try:
            # It is possible that the change has been merged, abandoned,
            # or a new patch set added during the time it has taken for this
            # script to run.
            # Only attempt to include code review and verify scores if
            # the change is still open and the patch set is still current.
            is_open, current_patchset = \
                gerrit_handle.change_is_open(options.change_nr)
            if not is_open:
                logging.info("Change %d is closed: adding review message " \
                             "without code review or verify scores",
                             options.change_nr)
                code_review = None
                verify = None
            elif options.patchset_nr != current_patchset:
                logging.info("Patchset %d has been replaced by patchset " \
                             "%d: adding review message without code " \
                             "review or verify scores",
                             options.patchset_nr, current_patchset)
                code_review = None
                verify = None
            if not options.dry_run:
                gerrit_handle.review_patchset(change_nr=options.change_nr,
                                              patchset=options.patchset_nr,
                                              message=message,
                                              codereview=code_review,
                                              verified=verify)
        except processes.ChildExecutionError, err:
            semcutil.fatal(2, "Error submitting review to Gerrit: %s" % err)
        except gerrit.GerritQueryError, err:
            semcutil.fatal(3, "Error submitting review to Gerrit: %s" % err)

if __name__ == "__main__":
    try:
        sys.exit(_main())
    except KeyboardInterrupt:
        semcutil.fatal(4, "Interrupted by user")
