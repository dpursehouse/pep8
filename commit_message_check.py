#!/usr/bin/env python

""" Script to check that commit messages are according to the guideline. """

import logging
import optparse
import re
import sys

from commit_message import CommitMessage
import gerrit
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
                  'NON_UTF8_CHARS',
                  'MULTIPLE_CONFLICTS_SECTIONS',
                  'INVALID_CATEGORY_TAG',
                  'INVALID_CATEGORY',
                  'MULTIPLE_CATEGORIES',
                  'MISSING_CATEGORY',
                  'INVALID_FEATURE_TAG',
                  'MULTIPLE_FEATURE_TAGS',
                  'FEATURE_BEFORE_CATEGORY',
                  'MISSING_FEATURE_ID',
                  'FEATURE_ID_BUT_NO_CATEGORY',
                  'FEATURE_ID_BUT_NOT_FEATURE_CATEGORY')

# Error codes mapped to severity and message
ERRORS = {ERROR_CODE.DMS_IN_TITLE:
          [ERROR_SEVERITY.WARNING,
           "It is not recommended to list DMS in the subject line"],
          ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT:
          [ERROR_SEVERITY.ERROR,
           "Subject should be a single line, separated from the "
           "message body by a blank line."],
          ERROR_CODE.SUBJECT_TOO_LONG:
          [ERROR_SEVERITY.ERROR,
           "Subject should be limited to %d characters." % MAX_SUBJECT_LENGTH],
          ERROR_CODE.DMS_WITHOUT_FIX_TAG:
          [ERROR_SEVERITY.WARNING,
           "DMS should be listed with FIX= tag"],
          ERROR_CODE.MULTIPLE_DMS_ON_LINE:
          [ERROR_SEVERITY.ERROR,
           "DMS should be listed on a separate line, with no leading "
           "whitespace or trailing text."],
          ERROR_CODE.INVALID_TAG_FORMAT:
          [ERROR_SEVERITY.ERROR,
           "Tag is formatted incorrectly."],
          ERROR_CODE.LINE_TOO_LONG:
          [ERROR_SEVERITY.ERROR,
           "Length should be limited to %d characters." % MAX_LINE_LENGTH],
          ERROR_CODE.NON_UTF8_CHARS:
          [ERROR_SEVERITY.ERROR,
           "Should not include non-UTF-8 characters."],
          ERROR_CODE.MULTIPLE_CONFLICTS_SECTIONS:
          [ERROR_SEVERITY.WARNING,
           "Multiple conflicts sections found."],
          ERROR_CODE.INVALID_CATEGORY_TAG:
          [ERROR_SEVERITY.ERROR,
           "Category should be listed as 'Category: category'"],
          ERROR_CODE.INVALID_CATEGORY:
          [ERROR_SEVERITY.ERROR,
           "Invalid category"],
          ERROR_CODE.MULTIPLE_CATEGORIES:
          [ERROR_SEVERITY.ERROR,
           "Cannot specify more than one category"],
          ERROR_CODE.MISSING_CATEGORY:
          [ERROR_SEVERITY.ERROR,
           "Valid category tag was not found"],
          ERROR_CODE.INVALID_FEATURE_TAG:
          [ERROR_SEVERITY.ERROR,
           "Feature ID should be listed as 'Feature: FPNNNN'"],
          ERROR_CODE.MULTIPLE_FEATURE_TAGS:
          [ERROR_SEVERITY.ERROR,
           "Cannot specify same feature ID more than once"],
          ERROR_CODE.FEATURE_BEFORE_CATEGORY:
          [ERROR_SEVERITY.WARNING,
           "Feature ID should be specified after the 'Category:' line"],
          ERROR_CODE.MISSING_FEATURE_ID:
          [ERROR_SEVERITY.ERROR,
           "Category is 'feature' but 'Feature:'  tag was not found"],
          ERROR_CODE.FEATURE_ID_BUT_NO_CATEGORY:
          [ERROR_SEVERITY.ERROR,
           "'Feature:' tag cannot be used without a 'Category:' tag"],
          ERROR_CODE.FEATURE_ID_BUT_NOT_FEATURE_CATEGORY:
          [ERROR_SEVERITY.ERROR,
           "'Feature:' tag can only be used when category is 'feature'"]}

# Message submitted to Gerrit when the check fails
FAIL_MESSAGE = """Commit message does not follow the guideline:

%s

Please check the commit message guideline:
https://wiki.sonyericsson.net/androiki/Commit_messages
"""

# Subjects matching any of the following patterns will be excluded from the
# check
EXCLUDED_SUBJECT_PATTERNS = [re.compile(r'^Merge '),
                             re.compile(r'^Revert '),
                             re.compile(r'^DO NOT MERGE'),
                             re.compile(r'^DO NOT SUBMIT'),
                             re.compile(r'^DON\'T SUBMIT')]

# Lines matching any of the following patterns will be excluded from the check
EXCLUDED_LINE_PATTERNS = [re.compile(r'^Squashed-with: ')]

# String marking the beginning of the conflicts section in the commit message
CONFLICTS_MARKER = re.compile(r'^Conflicts:$')

# Category tag patterns
CATEGORY_MARKER = re.compile(r'^Category:')
CATEGORY_TAG = re.compile(r'^Category: ([a-z]+)$')

# Feature tag patterns
FEATURE_MARKER = re.compile(r'^Feature:')
FEATURE_TAG = re.compile(r'^Feature: (FP[0-9]{4,6})$')

# List of valid category tags
VALID_CATEGORIES = ["integration", "configuration", "development", "bugfix",
                    "feature", "revert", "other"]


def is_excluded_subject(subject):
    '''
    Check if `subject` should be excluded.
    '''
    for pattern in EXCLUDED_SUBJECT_PATTERNS:
        if re.match(pattern, subject):
            return True
    return False


def is_excluded_line(line):
    '''
    Check if `line` should be excluded.
    '''
    for pattern in EXCLUDED_LINE_PATTERNS:
        if re.match(pattern, line):
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


class CommitMessageCheckerError(Exception):
    """ Raised when an error occurs during commit message check. """


class CommitMessageChecker(object):
    """ Commit message checker class.  Checks that commit messages
    are according to the guideline.
    """

    def __init__(self, commit=None, require_category=False):
        self.commit = commit
        self.require_category = require_category
        self.errors = []
        self.conflicts_marker_found = False
        self.in_conflicts_section = False
        self.conflicts_section_processed = False
        self.category = None
        self.feature_id = []

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
        Reset the checker.
        '''
        self.errors = []
        self.conflicts_marker_found = False
        self.in_conflicts_section = False
        self.conflicts_section_processed = False
        self.category = None
        self.feature_id = []

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
        if is_excluded_line(line):
            return

        # Check if this line is a category tag
        if re.match(CATEGORY_MARKER, line):
            match = re.match(CATEGORY_TAG, line)
            if not match:
                self.error(ERROR_CODE.INVALID_CATEGORY_TAG, line_no)
            else:
                if self.category:
                    self.error(ERROR_CODE.MULTIPLE_CATEGORIES, line_no)
                else:
                    category = match.group(1)
                    if category in VALID_CATEGORIES:
                        self.category = category
                    else:
                        self.error(ERROR_CODE.INVALID_CATEGORY, line_no)
        # Check if this line is a feature tag
        elif re.match(FEATURE_MARKER, line):
            match = re.match(FEATURE_TAG, line)
            if not match:
                self.error(ERROR_CODE.INVALID_FEATURE_TAG, line_no)
            else:
                feature_id = match.group(1)
                if feature_id in self.feature_id:
                    self.error(ERROR_CODE.MULTIPLE_FEATURE_TAGS, line_no)
                else:
                    self.feature_id.append(feature_id)
                    if not self.category:
                        self.error(ERROR_CODE.FEATURE_BEFORE_CATEGORY, line_no)
        # Check if we're entering or leaving the conflicts section
        # of the commit message
        elif re.match(CONFLICTS_MARKER, line):
            logging.debug("Found conflicts marker at line %d", line_no)
            # Can only have one conflicts section
            if self.conflicts_marker_found:
                logging.debug("Multiple conflicts markers at line %d", line_no)
                self.error(ERROR_CODE.MULTIPLE_CONFLICTS_SECTIONS, line_no)
            else:
                self.conflicts_marker_found = True
        elif not line or line.startswith('\t'):
            if (self.conflicts_marker_found and
                    not self.conflicts_section_processed and
                    not self.in_conflicts_section):
                if not line:
                    logging.debug("Found conflicts marker separator at line %d",
                                  line_no)
                if not self.in_conflicts_section:
                    logging.debug("Enter conflicts section at line %d", line_no)
                    self.in_conflicts_section = True
                    return
        elif self.in_conflicts_section and not line.startswith('\t'):
            # In the conflicts section, each line must begin with a tab
            logging.debug("Exit conflicts section at line %d", line_no)
            self.in_conflicts_section = False
            self.conflicts_section_processed = True

        # Only check rest of commit message when not in conflicts section
        if self.in_conflicts_section:
            logging.debug("Ignore line inside conflicts section at line %d",
                          line_no)
        else:
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

            # Check that a category was specified, if mandatory
            if self.require_category and not self.category:
                self.error(ERROR_CODE.MISSING_CATEGORY)

            # If feature ID is specified, the category must be "feature",
            # and if the category is "feature" then a feature ID must also
            # be specified.
            if self.category == "feature" and not self.feature_id:
                self.error(ERROR_CODE.MISSING_FEATURE_ID)
            elif self.feature_id and not self.category:
                self.error(ERROR_CODE.FEATURE_ID_BUT_NO_CATEGORY)
            elif self.feature_id and not self.category == "feature":
                self.error(ERROR_CODE.FEATURE_ID_BUT_NOT_FEATURE_CATEGORY)

        return self.errors


def format_results(results):
    '''
    Format the results of the commit message check.
    Return the formatted results as a string, number of errors, and number
    of warnings.
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


@retry(CommitMessageCheckerError, tries=3, backoff=2, delay=60)
def get_commit_message(gerrit_handle, revision):
    ''' Get the commit message from the change specified by `revision`.
    '''
    results = gerrit_handle.query(revision)
    if not results:
        raise CommitMessageCheckerError("Gerrit didn't find revision %s" %
                                        revision)
    return CommitMessage(results[0]["commitMessage"])


def _main():
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("", "--gerrit-url", dest="gerrit_url",
                      default=DEFAULT_GERRIT_SERVER,
                      help="The URL to the Gerrit server.")
    parser.add_option("-u", "--gerrit-user", dest="gerrit_user",
                      default=None,
                      help="The username that should be used when logging "
                           "into the Gerrit server with SSH. If omitted, "
                           "the SSH client will decide the username based "
                           "on $LOGNAME and its own configuration file "
                           "(if present).")
    parser.add_option("-v", "--verbose", dest="verbose", default=False,
                      action="store_true", help="Verbose mode.")
    parser.add_option("", "--dry-run", dest="dry_run", action="store_true",
                      help="Do everything except actually add the note "
                           "to the affected change.")
    parser.add_option("", "--change", dest="change_nr", type="int",
                      help="The change number to check.")
    parser.add_option("", "--patchset", dest="patchset_nr", type="int",
                      help="The patchset number.")
    parser.add_option("", "--project", dest="project",
                      help="The name of the project on which the "
                           "change is uploaded.")
    parser.add_option("", "--revision", dest="revision",
                      help="The patchset revision.")
    parser.add_option("", "--exclude-git", dest="git_ex",
                      action="append", metavar="REGEXP",
                      help="A regular expression that will be matched "
                           "against the name of the git to which the "
                           "change has been uploaded.  Gits that match "
                           "the pattern will be excluded from the check.  "
                           "This option can be used multiple times to add "
                           "more expressions. (default: <empty>).")
    parser.add_option("", "--require-category", dest="require_category",
                      action="store_true", default=False,
                      help="Require commit category tag to be present.")
    (options, _args) = parser.parse_args()

    if options.verbose:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
    else:
        logging.basicConfig(format='%(message)s', level=logging.ERROR)

    if not options.change_nr:
        fatal(1, "Change nr. missing. Use --change option.")
    if not options.patchset_nr:
        fatal(1, "Patchset nr. missing. Use --patchset option.")
    if not options.project:
        fatal(1, "Project name missing. Use --project option.")
    if not options.revision:
        fatal(1, "Patchset revision missing. Use --revision option.")

    # By default we include all gits, and then exclude any that are
    # specified by the user with the --exclude-git option.
    git_matcher = IncludeExcludeMatcher([r"^"], options.git_ex)
    if not git_matcher.match(options.project):
        logging.info("git %s is excluded from commit message check",
                     options.project)
        exit(0)

    try:
        gerrit_handle = gerrit.GerritSshConnection(options.gerrit_url,
                                                   username=options.gerrit_user)
        message = get_commit_message(gerrit_handle, options.revision)
        checker = CommitMessageChecker(message, options.require_category)
        results = checker.check()
        output, errors, warnings = format_results(results)
        logging.info(output)
        if (errors or warnings):
            code_review = None
            # If any errors have been found, set -1 code review score
            if errors:
                # It is possible that the change has been merged, abandoned or
                # a new patch set uploaded during the time it has taken to run
                # this script.
                # Only attempt to include code review score if the change is
                # still open and the patch set is current.
                is_open, current_patchset = \
                    gerrit_handle.change_is_open(options.change_nr)
                if not is_open:
                    logging.info("Change %d is closed.  Not adding code review "
                                 "score.", options.change_nr)
                elif options.patchset_nr != current_patchset:
                    logging.info("Patchset %d has been replaced by patchset "
                                 "%d.  Not adding code review score.",
                                 options.patchset_nr, current_patchset)
                else:
                    code_review = -1
            if not options.dry_run:
                gerrit_handle.review_patchset(change_nr=options.change_nr,
                                              patchset=options.patchset_nr,
                                              message=FAIL_MESSAGE % output,
                                              codereview=code_review)
    except gerrit.GerritSshConfigError, err:
        fatal(1, "Error establishing connection to Gerrit: %s" % err)
    except processes.ChildExecutionError, err:
        fatal(1, "Error submitting review to Gerrit: %s" % err)
    except gerrit.GerritQueryError, err:
        fatal(1, "Gerrit query error: %s" % err)
    except CommitMessageCheckerError, err:
        fatal(1, "Unable to get commit message: %s" % err)

if __name__ == '__main__':
    try:
        sys.exit(_main())
    except KeyboardInterrupt:
        fatal(1, "Interrupted by user")
