import re
import sys

import commit_message
from semcutil import fatal


# The maximum length of a line in the commit message body
MAX_LINE_LENGTH = 72

# The maximum length of the commit message subject
MAX_SUBJECT_LENGTH = 72


class CommitMessageChecker:

    def __init__(self, commit):
        self.commit = commit

    def is_excluded_subject(self, subject):
        '''
        Check if a given subject should be excluded
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

    def report_error(self, error):
        '''
        Print an error message and increment the count
        '''

        print "Error: " + error
        self.errors += 1

    def report_warning(self, warning):
        '''
        Print a warning message and increment the count
        '''

        print "Warning: " + warning
        self.warnings += 1

    def is_utf8_string(self, s):
        '''
        Check if a string is UTF8
        '''

        try:
            s.decode('utf_8')
        except:
            return False
        else:
            return True

    def check_subject(self, subject):
        '''
        Check the content of the commit message subject
        '''

        # Check for DMS mentioned in the subject
        dmslist = re.findall('DMS\d{6,8}', subject)
        if len(dmslist):
            self.report_warning("It is not recommended to list DMS in the "
                                "subject line.")

        # Make sure the subject is only one line and within the length limit
        subject_lines = subject.split('\n')
        if len(subject_lines) > 1:
            self.report_error("Subject should be a single line, separated "
                              "from the message body by a blank line.")
        elif len(subject) > MAX_SUBJECT_LENGTH:
            self.report_error("Subject should be limited to %d characters."
                              % MAX_SUBJECT_LENGTH)

    def check_line(self, line, line_no):
        '''
        Check the content of a line
        '''

        # Check for invalid tag DMS=DMS00123456
        dmspattern = re.compile('(DMS=DMS\d{6,8})+', re.IGNORECASE)
        if re.search(dmspattern, line) is not None:
            self.report_warning("Line %d: DMS should be listed with FIX= tag"
                                % line_no)

        # Check for invalid FIX= tags in the message body
        dmspattern = re.compile('(FIX.{1,3}?DMS\d{6,8})+', re.IGNORECASE)
        dmslist = re.findall(dmspattern, line)
        if len(dmslist):
            dmspattern = re.compile('^FIX.{1,3}?DMS\d{6,8}$', re.IGNORECASE)
            if not re.match(dmspattern, line):
                self.report_error("Line %d: DMS should be listed on a "
                                  "separate line, with no leading whitespace "
                                  "or trailing text." % line_no)
            for dms in dmslist:
                if not re.match('FIX=DMS\d{6,8}', dms):
                    self.report_error("Line %d: Tag '%s' is formatted "
                                      "incorrectly." % (line_no, dms))

        # Check line length
        if len(line) > MAX_LINE_LENGTH:
            self.report_error("Line %d: Length should be limited to %d "
                              "characters." % (line_no, MAX_LINE_LENGTH))

        # Check for non-UTF8 characters
        if not self.is_utf8_string(line):
            self.report_error("Line %d: Should not include non-UTF-8 "
                              "characters." % line_no)

    def check(self):
        '''
        Check the commit message subject and body
        '''

        self.errors = 0
        self.warnings = 0

        # Check for excluded commits
        if self.is_excluded_subject(self.commit.subject):
            print ("Found excluded commit type. Skipping message body check.")
            return 0

        # Check the subject
        self.check_subject(self.commit.subject)

        # Check the message body
        commitLines = self.commit.message.split('\n')
        line_no = 0
        for line in commitLines:
            line_no += 1
            line = line.rstrip()
            self.check_line(line, line_no)

        print "\nErrors: %d" % self.errors
        print "Warnings: %d" % self.warnings

        return self.errors


def main():
    '''
    Commit checker main function.   Expected input on stdin
    is the output from the "git cat-file -p HEAD" command
    '''

    try:
        input = sys.stdin.read()
        message = commit_message.CommitMessage(input)
        checker = CommitMessageChecker(message)
        errors = checker.check()
        exit(errors)
    except IOError, e:
        fatal(1, "IOError when reading input stream: %s" % (str(e)))
    except commit_message.CommitMessageError, e:
        fatal(1, "Commit message error: %s" % (str(e)))

if __name__ == '__main__':
    main()
