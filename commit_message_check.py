import re
import sys

import commit_message
from semcutil import enum, fatal


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


class CommitMessageChecker:

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

    def is_excluded_subject(self, subject):
        '''
        Check if a given subject should be excluded.
        '''

        excludedSubjects = ["Merge ",
                            "Revert ",
                            "DO NOT MERGE",
                            "DO NOT SUBMIT",
                            "DON\'T SUBMIT"]
        for index in excludedSubjects:
            if subject.startswith(index):
                return True
        return False

    def is_utf8_string(self, s):
        '''
        Check if a string is UTF8.
        '''

        try:
            s.decode('utf_8')
        except:
            return False
        else:
            return True

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
        if not self.is_utf8_string(subject):
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
        if not self.is_utf8_string(line):
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
        if not self.is_excluded_subject(self.commit.subject):
            # Check the subject
            self.check_subject(self.commit.subject)

            # Check the message body
            commitLines = self.commit.message.split('\n')
            line_no = 0
            for line in commitLines:
                line_no += 1
                line = line.rstrip()
                self.check_line(line, line_no)

        return self.errors


def check_and_display_results(results):
    '''
    Display the results of the commit message check.
    Return non-zero if any errors occurred.
    '''

    messages = {ERROR_SEVERITY.ERROR: "Error",
                ERROR_SEVERITY.WARNING: "Warning"}

    for line, code in results:
        severity, message = ERRORS[code]
        output = "%s: " % messages[severity]
        if line:
            output += "Line %d: " % line
        output += message
        print output

    errors = [ERRORS[c][0] for l, c in results].count(ERROR_SEVERITY.ERROR)
    warnings = [ERRORS[c][0] for l, c in results].count(ERROR_SEVERITY.WARNING)

    print "\nErrors: %d" % errors
    print "Warnings: %d" % warnings

    return errors


def main():
    '''
    Commit checker main function.   Expected input on stdin
    is the output from the "git cat-file -p HEAD" command.
    '''

    try:
        input = sys.stdin.read()
        message = commit_message.CommitMessage(input)
        checker = CommitMessageChecker(message)
        errors = checker.check()
        exit(check_and_display_results(errors))
    except IOError, e:
        fatal(1, "IOError when reading input stream: %s" % (str(e)))
    except commit_message.CommitMessageError, e:
        fatal(1, "Commit message error: %s" % (str(e)))

if __name__ == '__main__':
    main()
