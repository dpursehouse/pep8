#------------------------------------------------------------------
#  ____                      _____      _
# / ___|  ___  _ __  _   _  | ____|_ __(_) ___ ___ ___  ___  _ __
# \___ \ / _ \| '_ \| | | | |  _| | '__| |/ __/ __/ __|/ _ \| '_ \
#  ___) | (_) | | | | |_| | | |___| |  | | (__\__ \__ \ (_) | | | |
# |____/ \___/|_| |_|\__, | |_____|_|  |_|\___|___/___/\___/|_| |_|
#                    |___/
#
#------------------------------------------------------------------
# Sony Ericsson Mobile Communications, Tokyo, Japan
#------------------------------------------------------------------
#
# Prepared: David Pursehouse
# Approved:
# Checked :
#
# No.     :
# Date    : 2010-11-15 (YYYY-MM-DD)
# Rev.    :
# Location:
#
# Title   : commitcheck.py
#
# Modified:
# 2011-02-18: Rewritten to check the whole commit message
# 2011-03-04: Add check for the invalid tag DMS=
#             Add "DO NOT MERGE" to list of excluded subjects
#             Check for excluded subject with simpler construct
#
#-----------------------------------------------------------------

import sys
import re

errors = 0
warnings = 0

def is_excluded_subject(subject):
    '''
    Check if a given subject should be excluded
    '''
    excludedSubjects = ["Merge remote branch",
                        "Revert \"",
                        "Merge \"",
                        "Merge commit \'",
                        "Merge branch \'",
                        "DO NOT MERGE",
                        "DO NOT SUBMIT",
                        "DON\'T SUBMIT"]
    for index in excludedSubjects:
        if subject.startswith(index):
            return True
    return False

def fatal_error(error):
    '''
    Print an error message and exit with error status
    '''
    print >> sys.stderr, "Fatal error: " + error
    sys.stderr.flush()
    exit(1)

def report_error(error):
    '''
    Print an error message and increment the count
    '''
    global errors
    print "Error: " + error
    errors += 1

def report_warning(warning):
    '''
    Print a warning message and increment the count
    '''
    global warnings
    print "Warning: " + warning
    warnings += 1

def is_utf8_string(s):
    '''
    Check if a string is UTF8 only
    '''
    try:
        s.decode('utf_8')
    except:
        return False
    else:
        return True

def check_line(line, line_no):
    '''
    Check the content of a line
    '''
    if line_no == 1:
        # Check for DMS mentioned in the subject
        dmslist = re.findall('DMS[\d]{6,8}', line)
        if len(dmslist):
            report_warning("Line 1: It is not recommended to list DMS in the "
                           "subject line.")
    else:
        # Check for invalid tag DMS=DMS00123456
        dmspattern = re.compile('(DMS=DMS[\d]{6,8})+', re.IGNORECASE)
        if re.search(dmspattern, line) is not None:
            report_warning("Line %d: DMS should be listed with FIX= tag"
                           % line_no)

        # Check for invalid FIX= tags in the message body
        dmspattern = re.compile('(FIX.{1,3}?DMS[\d]{6,8})+', re.IGNORECASE)
        dmslist = re.findall(dmspattern, line)
        if len(dmslist):
            if len(dmslist) > 1:
                report_error("Line %d: Only one DMS should be listed per "
                             "line." % line_no)
            else:
                dmspattern = re.compile('^FIX.*?DMS[\d]{6,8}$', re.IGNORECASE)
                if not re.match(dmspattern, line):
                    report_error("Line %d: DMS should be listed on a "
                                 "separate line, with no leading whitespace "
                                 "or trailing text." % line_no)
            for dms in dmslist:
                if not re.match('FIX=DMS[\d]{6,8}', dms):
                    report_error("Line %d: Tag '%s' is formatted incorrectly."
                                 %(line_no, dms))

    # Make sure a blank line follows the subject
    if line_no == 2:
        if len(line):
            report_error("Line 2: Subject should be followed by a blank "
                         "line.")

    # Check line length
    if len(line) > 70:
        report_error("Line %d: Length should be limited to 70 characters."
                      % line_no)

    # Check for non-UTF8 characters
    if not is_utf8_string(line):
        report_error("Line %d: Should not include non-UTF-8 characters."
                     % line_no)

def check_header(header):
    '''
    Check the commit header to verify that it only contains
    expected tokens: 'tree', 'parent', 'author', or 'committer'
    '''
    headerLines = header.split('\n')
    line_no = 0
    for line in headerLines:
        line_no += 1
        if not re.match("^(tree|parent|author|committer) ", line):
            fatal_error("Header: Unexpected token at line %d." % line_no)

def check_commit_message(message):
    '''
    Check the commit message subject and body
    '''
    commitLines = message.split('\n')
    line_no = 0
    for line in commitLines:
        line_no += 1
        line = line.rstrip('\n')
        if line_no == 1:
            # Check the subject line
            if is_excluded_subject(line):
                print ("Found excluded commit type.  "
                       "Skipping message body check.")
                break
            else:
                check_line(line, line_no)
        elif line_no >= 2:
            # Check the message body
            check_line(line, line_no)

    print "\nProcessed %d lines" % line_no
    print "Errors: %d" % errors
    print "Warnings: %d" % warnings

def main():
    '''
    Commit checker main function.   Expected input on stdin
    is the output from the "git cat-file -p HEAD" command
    '''
    input = sys.stdin.read()
    check_header(input[0:input.find('\n\n')])
    check_commit_message(input[input.find('\n\n')+2:])

    if errors > 0:
        exit(1)
    else:
        exit(0)

if __name__ == '__main__':
    main()
