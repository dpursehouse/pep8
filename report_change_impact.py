#!/usr/bin/env python

"""Given a change that has been uploaded to Gerrit, checks which
manifest branch(es) will be affected when that change is eventually
merged. If more than one branch will be affected a note is added
to the change to remind the uploader that additional verification
might be necessary.

The script is intended to be invoked when a change (or a new patch set
to an existing change) has been uploaded to Gerrit but it works fine
for interactive use as well.

Supports regular expression based inclusion/exclusion patterns for
both manifest branches and the destination branches of the changes
being inspected.
"""

import optparse
import re
import sys

import gerrit
import manifest
import manifestbranches
import processes
import semcutil


# The default value of the command line option to select which
# branches of the gits listed in each manifest that should be
# examined.
DEFAULT_GIT_BRANCH_INCLUDES = [r"^"]

# The default value of the command line option to select which refs
# from the manifest that should be examined.
DEFAULT_MANIFEST_REF_INCLUDES = [r"^refs/remotes/origin/"]

# The URL of the Gerrit server
GERRIT_SERVER_URL = "review.sonyericsson.net"


class IncludeExcludeMatcher():
    """Maintains two lists of regular expression patterns for matching
    strings against. Input strings are matched against all patterns in
    the list of inclusion patterns and thereafter all patterns in the
    exclusion pattern list. An input string must be matched by at
    least one of the patterns in the inclusion list and must not be
    matched by any of the patterns in the exclusion list (i.e. the
    exclusion list has precedence).
    """

    def __init__(self, include_patterns, exclude_patterns):
        """Initialize an IncludeExcludeFilter object with the given
        initial values for the inclusion and exclusion pattern
        lists. Each initial value may be None, in which case it counts
        as an empty list.
        """

        if include_patterns is not None:
            self.include_patterns = include_patterns
        else:
            self.include_patterns = []
        if exclude_patterns is not None:
            self.exclude_patterns = exclude_patterns
        else:
            self.exclude_patterns = []

    def match(self, string):
        """Match `string` against the inclusion and exclusion patterns
        and return True if there's a match and False otherwise. This
        function is suitable to pass to the filter() function.
        """

        matches = False
        for regexp in self.include_patterns:
            if re.search(regexp, string):
                matches = True
                break
        for regexp in self.exclude_patterns:
            if re.search(regexp, string):
                # Could return immediately here, but doing the
                # assignment for symmetry.
                matches = False
                break
        return matches


def _main():
    usage = "usage: %prog CHANGE_NR -m MANIFEST_PATH [options]"
    options = optparse.OptionParser(usage=usage)
    options.add_option("-m", "--manifest-path", dest="manifest_path",
                       default=None,
                       help="The path to the local directory where the " \
                           "manifest git that we should compare against " \
                           "can be found.")
    options.add_option("-u", "--gerrit-user", dest="gerrit_user",
                       default=None,
                       help="The username that should be used when logging " \
                           "into the Gerrit server with SSH. If omitted, " \
                           "the SSH client will decide the username based " \
                           "on $LOGNAME and its own configuration file " \
                           "(if present).")
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

    (options, args) = options.parse_args()
    if len(args) != 1:
        semcutil.fatal(1, "Incorrect number of arguments. Use -h for help.")
    if not options.manifest_path:
        semcutil.fatal(1, "Path to manifest git missing (use -m option).")

    change_nr = args[0]

    # Obtain information from Gerrit about the change that we're being
    # interrogated about; which git it has been uploaded to and which
    # branch of the git it will be merged to when submitted.
    querystring = change_nr
    try:
        gerrit_conn = gerrit.GerritSshConnection(GERRIT_SERVER_URL,
                                                 username=options.gerrit_user)
        change_info = gerrit_conn.query(querystring)
    except (processes.ChildExecutionError, gerrit.GerritSshConfigError), err:
        semcutil.fatal(2, "Error connecting to Gerrit to obtain "
                       "information about change %s: %s" % (change_nr, err))
    except gerrit.GerritQueryError, err:
        semcutil.fatal(2, "Gerrit rejected the query: %s" % err)
    if len(change_info) == 1:
        try:
            affected_git = change_info[0]["project"]
            affected_branch = change_info[0]["branch"]
            current_patchset = len(change_info[0]["patchSets"])
        except KeyError, err:
            semcutil.fatal(2, "Unexpected response from Gerrit; the %s " \
                           "key was missing." % err)
    else:
        semcutil.fatal(2, "Query was expected to return a single change "
                       "but instead returned %d changes: %s" %
                       (len(change_info), querystring))

    branch_matcher = IncludeExcludeMatcher(options.git_branch_in,
                                           options.git_branch_ex)
    if not branch_matcher.match(affected_branch):
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
        return 0

    # Extract the manifest XML data from all manifest branches found
    # earlier. Store the subset of branches that would be affected if
    # the change is submitted in `affected_manifests`.
    affected_manifests = []
    for branch in branches:
        try:
            manifests = manifestbranches.get_manifests(branch,
                                                       options.manifest_path)
            for ref, prettybranch, mfest in manifests:
                if affected_git in mfest and \
                        affected_branch == mfest[affected_git]["revision"]:
                    affected_manifests.append(prettybranch)
        except processes.ChildExecutionError, err:
            semcutil.fatal(2, err)
        except manifest.ManifestParseError, err:
            print >> sys.stderr, "Skipping %s: %s" % (branch, err)

    # If more than one manifest is affected by this change, craft
    # an informative message and post it as a note to the change.
    if len(affected_manifests) > 1:
        message = """Dear uploader,

The commit you've uploaded will affect more than one system branch
(aka manifest), namely the following:

"""
        for branch in affected_manifests:
            message += "* %s\n" % branch
        message += """
Before submitting this change, make sure you don't inadvertently break
any of these branches. Depending on the branch and the nature of your
change, you may have to verify the commit separately on each branch,
or it might be safe to assume that your change will behave in the same
good manner everywhere, or one or more of the branches might be
managed by dedicated teams (i.e. it isn't your problem if it
breaks because of your change). Please use good judgement."""
        print message
        if not options.dry_run:
            try:
                gerrit_conn.review_patchset(change_nr=int(change_nr),
                                            patchset=int(current_patchset),
                                            message=message)
            except processes.ChildExecutionError, err:
                semcutil.fatal(2, "Error scoring change: %s" % err)

if __name__ == "__main__":
    try:
        sys.exit(_main())
    except KeyboardInterrupt:
        sys.exit(1)
