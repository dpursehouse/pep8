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
#
#-----------------------------------------------------------------

import sys, json

print "<!DOCTYPE html>"
print "<head><title>commitcheck.py results</title>"
print "<meta charset=\"utf-8\"/></head>"

def isExcludedSubject(subject):
    excludedSubjects = ["Merge remote branch",
                        "Revert \"",
                        "Merge commit \'",
                        "Merge branch \'",
                        "DO NOT SUBMIT"]
    for index in excludedSubjects:
        if index in subject:
            return True
    return False

def isExcludedProject(project):
    excludedProjects = ["kernel/msm",
                        "tools/gerrit",
                        "kernel/st-ericsson",
                        "semctools/c2d",
                        "platform/sdk",
                        "semctools/hudson/hudson-slave-files",
                        "indus/tsce"]
    for index in excludedProjects:
        if index == project:
            return True
    return False

for line in sys.stdin:
    data = json.loads(line)
    if "subject" in data and "project" in data \
                         and "branch" in data \
                         and "url" in data:
        if not isExcludedProject(data["project"]) \
           and not isExcludedSubject(data["subject"]) \
           and len(data["subject"]) > 70:
            print "<p>"
            print "[" + data["project"] + "]"
            print "[" + data["branch"] + "]"
            print "<a href=\"" + data["url"] + "\">" + data["subject"] + "</a>"
            print "</p>"
