#!/usr/bin/env python

""" Script to check that commit messages are according to the guideline. """

import logging
import optparse
import os
import re
import sys

import commit_message
import gerrit
from git import GitRepository
from include_exclude_matcher import IncludeExcludeMatcher
import processes
from retry import retry
from semcutil import enum, fatal


# The default URL of the Gerrit server
DEFAULT_GERRIT_SERVER = "review.sonyericsson.net"

# The maximum length of a line in the commit message body
MAX_LINE_LENGTH = 72

# The maximum length of the commit message subject
MAX_SUBJECT_LENGTH = 72

# Error severities
ERROR_SEVERITY = enum('ERROR', 'WARNING')

# Error codes
ERROR_CODE = enum('DMS_IN_TITLE',
                  'DMS_WITHOUT_FIX_TAG',
                  'MULTIPLE_LINES_IN_SUBJECT',
                  'SUBJECT_TOO_LONG',
                  'MULTIPLE_DMS_ON_LINE',
                  'INVALID_TAG_FORMAT',
                  'LINE_TOO_LONG',
                  'NON_UTF8_CHARS')

# Error codes mapped to severity and message
ERRORS = {ERROR_CODE.DMS_IN_TITLE:
            [ERROR_SEVERITY.WARNING,
               "It is not recommended to list DMS in the subject line"],
          ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT:
            [ERROR_SEVERITY.ERROR,
               "Subject should be a single line, separated from the " \
               "message body by a blank line."],
          ERROR_CODE.SUBJECT_TOO_LONG:
            [ERROR_SEVERITY.ERROR,
               "Subject should be limited to %d characters." % \
               MAX_SUBJECT_LENGTH],
          ERROR_CODE.DMS_WITHOUT_FIX_TAG:
            [ERROR_SEVERITY.WARNING,
               "DMS should be listed with FIX= tag"],
          ERROR_CODE.MULTIPLE_DMS_ON_LINE:
            [ERROR_SEVERITY.ERROR,
               "DMS should be listed on a separate line, with no leading " \
               "whitespace or trailing text."],
          ERROR_CODE.INVALID_TAG_FORMAT:
            [ERROR_SEVERITY.ERROR,
               "Tag is formatted incorrectly."],
          ERROR_CODE.LINE_TOO_LONG:
            [ERROR_SEVERITY.ERROR,
               "Length should be limited to %d characters." % \
               MAX_LINE_LENGTH],
          ERROR_CODE.NON_UTF8_CHARS:
            [ERROR_SEVERITY.ERROR,
               "Should not include non-UTF-8 characters."]}

FAIL_MESSAGE = """Commit message does not follow the guideline:

%s

Please check the commit message guideline:
https://wiki.sonyericsson.net/androiki/Commit_messages
"""

EXCLUDED_SUBJECTS = ["Merge ",
                     "Revert ",
                     "DO NOT MERGE",
                     "DO NOT SUBMIT",
                     "DON\'T SUBMIT"]


def is_excluded_subject(subject):
    '''
    Check if `subject` should be excluded.
    '''
    for text in EXCLUDED_SUBJECTS:
        if subject.startswith(text):
            return True
    return False


def is_utf8_string(string):
    '''
    Check if `string` is UTF8.
    '''

    try:
        string.decode('utf_8')
    except UnicodeError:
        return False
    else:
        return True


class CommitMessageChecker:
    """ Commit message checker class.  Checks that commit messages
    are according to the guideline.
    """

    def __init__(self, commit=None):
        self.commit = commit
        self.errors = []

    def error(self, error_code, line_no=0):
        '''
        Append `line_no` and `error_code` pair to the list of errors.
        Raise ValueError if the pair is already in the list.
        '''
        pair = [line_no, error_code]
        if pair in self.errors:
            raise ValueError("Fatal: Bad error_code/line_no.")
        self.errors.append(pair)

    def reset(self):
        '''
        Reset the checker, i.e. clear the list of errors.
        '''
        self.errors = []

    def check_subject(self, subject):
        '''
        Check the content of the commit message subject.
        '''

        # Check for DMS mentioned in the subject
        dmslist = re.findall('DMS\d{6,8}', subject)
        if len(dmslist):
            self.error(ERROR_CODE.DMS_IN_TITLE)

        # Make sure the subject is only one line and within the length limit
        subject_lines = subject.split('\n')
        if len(subject_lines) > 1:
            self.error(ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT)
        if len(subject) > MAX_SUBJECT_LENGTH:
            self.error(ERROR_CODE.SUBJECT_TOO_LONG)

        # Check for non-UTF8 characters
        if not is_utf8_string(subject):
            self.error(ERROR_CODE.NON_UTF8_CHARS)

    def check_line(self, line, line_no):
        '''
        Check the content of a line.
        '''

        # Check for invalid tag DMS=DMS00123456
        dmspattern = re.compile('(DMS=DMS\d{6,8})+', re.IGNORECASE)
        if re.search(dmspattern, line):
            self.error(ERROR_CODE.DMS_WITHOUT_FIX_TAG, line_no)

        # Check for invalid FIX= tags in the message body
        dmspattern = re.compile('(FIX.{1,3}?DMS\d{6,8})+', re.IGNORECASE)
        dmslist = re.findall(dmspattern, line)
        if len(dmslist):
            dmspattern = re.compile('^FIX.{1,3}?DMS\d{6,8}$', re.IGNORECASE)
            if not re.match(dmspattern, line):
                self.error(ERROR_CODE.MULTIPLE_DMS_ON_LINE, line_no)
            for dms in dmslist:
                if not re.match('FIX=DMS\d{6,8}', dms):
                    self.error(ERROR_CODE.INVALID_TAG_FORMAT, line_no)

        # Check line length
        if len(line) > MAX_LINE_LENGTH:
            self.error(ERROR_CODE.LINE_TOO_LONG, line_no)

        # Check for non-UTF8 characters
        if not is_utf8_string(line):
            self.error(ERROR_CODE.NON_UTF8_CHARS, line_no)

    def check(self):
        '''
        Check the commit message subject and body.
        Return list of errors, which is empty if no errors occurred.
        '''

        # Cannot run check without a commit message
        if not self.commit:
            raise ValueError("Fatal: No commit message")

        # Clear errors
        self.reset()

        # Only run the check if the subject line is not excluded
        if not is_excluded_subject(self.commit.subject):
            # Check the subject
            self.check_subject(self.commit.subject)

            # Check the message body
            commit_lines = self.commit.message.split('\n')
            line_no = 0
            for line in commit_lines:
                line_no += 1
                line = line.rstrip()
                self.check_line(line, line_no)

        return self.errors


def format_results(results):
    '''
    Format the results of the commit message check
    Return the formatted results as a string, number of errors, and number
    of warnings
    '''
    messages = {ERROR_SEVERITY.ERROR: "Error",
                ERROR_SEVERITY.WARNING: "Warning"}

    output = ""
    for line, code in results:
        severity, message = ERRORS[code]
        output += "* %s: " % messages[severity]
        if line:
            output += "Line %d: " % line
        output += message + "\n"

    errors = [ERRORS[c][0] for _l, c in results].count(ERROR_SEVERITY.ERROR)
    warnings = [ERRORS[c][0] for _l, c in results].count(ERROR_SEVERITY.WARNING)

    output += "\nErrors: %d Warnings: %d" % (errors, warnings)

    return output, errors, warnings


@retry(processes.ChildExecutionError, tries=3, backoff=2, delay=60)
def get_commit_message(options):
    ''' Get the commit message from the change.
    '''
    patchset_ref = gerrit.get_patchset_refspec(options.change_nr,
                                               options.patchset_nr)

    logging.info("Fetching patch set %s", patchset_ref)
    git = GitRepository(options.cache_path, os.path.join("git://",
                                                         options.gerrit_url,
                                                         options.affected_git))
    git.fetch(refspec=patchset_ref)

    # Extract the commit message and find any DMS issues in it.
    _errcode, msg, _err = processes.run_cmd("git",
                                            "cat-file",
                                            "-p",
                                            "FETCH_HEAD",
                                            path=git.git_path)
    return commit_message.CommitMessage(msg)


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
    options.add_option("", "--change", dest="change_nr", type="int",
                       help="The change number to check.")
    options.add_option("", "--patchset", dest="patchset_nr", type="int",
                       help="The patchset number.")
    options.add_option("", "--project", dest="affected_git",
                       help="The name of the project on which the " \
                            "change is uploaded.")
    options.add_option("", "--exclude-git", dest="git_ex",
                       action="append", metavar="REGEXP",
                       help="A regular expression that will be matched " \
                            "against the name of the git to which the " \
                            "change has been uploaded.  Gits that match " \
                            "the pattern will be excluded from the check.  " \
                            "This option can be used multiple times to add " \
                            "more expressions. (default: <empty>).")
    (options, _args) = options.parse_args()

    if options.verbose:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
    else:
        logging.basicConfig(format='%(message)s', level=logging.ERROR)

    if not options.change_nr:
        fatal(1, "Change nr. missing. Use --change option.")
    if not options.patchset_nr:
        fatal(1, "Patchset nr. missing. Use --patchset option.")
    if not options.affected_git:
        fatal(1, "Project name missing. Use --project option.")

    # By default we include all gits, and then exclude any that are
    # specified by the user with the --exclude-git option.
    git_matcher = IncludeExcludeMatcher([r"^"], options.git_ex)
    if not git_matcher.match(options.affected_git):
        logging.info("git %s is excluded from commit message check",
                     options.affected_git)
        exit(0)

    try:
        message = get_commit_message(options)
    except processes.ChildExecutionError, err:
        fatal(1, err)
    except EnvironmentError, err:
        fatal(1, "Error extracting commit message: %s: %s" % \
                 (err.strerror, err.filename))
    try:
        checker = CommitMessageChecker(message)
        results = checker.check()
        output, errors, warnings = format_results(results)
        logging.info(output)
        if (errors or warnings):
            g = gerrit.GerritSshConnection(options.gerrit_url,
                                           username=options.gerrit_user)
            code_review = None
            # If any errors have been found, set -1 code review score
            if errors:
                # It is possible that the change has been merged, abandoned or
                # a new patch set uploaded during the time it has taken to run
                # this script.
                # Only attempt to include code review score if the change is
                # still open and the patch set is current.
                is_open, current_patchset = \
                    g.change_is_open(options.change_nr)
                if not is_open:
                    logging.info("Change %d is closed.  Not adding code review "
                                 "score.", options.change_nr)
                elif options.patchset_nr != current_patchset:
                    logging.info("Patchset %d has been replaced by patchset " \
                                 "%d.  Not adding code review score.",
                                 options.patchset_nr, current_patchset)
                else:
                    code_review = -1
            if not options.dry_run:
                g.review_patchset(change_nr=options.change_nr,
                                  patchset=options.patchset_nr,
                                  message=FAIL_MESSAGE % output,
                                  codereview=code_review)
    except gerrit.GerritSshConfigError, e:
        fatal(1, "Error getting Gerrit ssh config: %s" % err)
    except processes.ChildExecutionError, err:
        fatal(1, "Error submitting review to Gerrit: %s" % err)
    except gerrit.GerritQueryError, err:
        fatal(1, "Error submitting review to Gerrit: %s" % err)
    except commit_message.CommitMessageError, e:
        fatal(1, "Commit message error: %s" % e)

if __name__ == '__main__':
    try:
        sys.exit(_main())
    except KeyboardInterrupt:
        fatal(1, "Interrupted by user")
