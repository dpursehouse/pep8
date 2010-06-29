#!/usr/bin/python

import sys
import os
import re

def _usage():
    myname = os.path.basename(sys.argv[0])
    usagestr = """repository list LABEL | %s
    Parses the input from repository list and prints any applications
    that are built with both make and semc-build.""" % (myname)
    print >> sys.stderr, usagestr

def _main(argv):
    if len(argv) !=1:
        _usage()
        sys.exit(9)

    findsemcbuildandmake(sys.stdin.readlines())

def findsemcbuildandmake(packagelines):
    makebuilt = set()
    semcbuilt = set()
    appPattern = re.compile("^(app-[a-z]+)-[a-z]+-(eng|user|userdebug)-release$")
    for line in packagelines:
        app = line.split()
        if len(app) > 0:
            appPatternMatch = appPattern.match(app[0])
            if appPatternMatch:
                makebuilt.add(appPatternMatch.groups()[0])
            else:
                semcbuilt.add(app[0])

    # Print result
    for app in semcbuilt.intersection(makebuilt):
        print app

if __name__ == "__main__":
    _main(sys.argv)
