#!/usr/bin/env python

# -----------------------------------------------------------------------------
# create_diff.py
#
# Usage: ./create_diff.py <xmlfile1> <xmlfile2> <buildid>
#
# Compares two xml files, and creates a report, wiki-style.
#
# -----------------------------------------------------------------------------

import sys
import os
from xml.dom.minidom import parse, parseString
import array
import optparse

cm_tools = os.path.dirname(os.path.abspath(os.path.join("..", sys.argv[0])))
sys.path.append(os.path.join(cm_tools, "external-modules"))
sys.path.append(os.path.join(cm_tools, "semcwikitools"))
import wikitools
import semcwikitools

#
# ----------------------------------------------------------------------
#

oldparams = []
newparams = []

#
# ----------------------------------------------------------------------
# Read xml list
#


def readXml(alist, paramlist):
    parameters = alist.getElementsByTagName("item")
    for param in parameters:
        paramlist.append([int(param.getAttribute("id")),
                          str(param.getAttribute("sg")),
                          str(param.getAttribute("source")),
                          str(param.getAttribute("name")),
                          str(param.getAttribute("value"))])
    return


#
# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
#


def makeDiff(oldxmlfile, newxmlfile, oldid, buildid):
    owners = []
    parameters = []
    responsiblelist = ""
    diffs = 0
    global oldparams

    # Read the lists
    dom_file = parse(oldxmlfile)
    readXml(dom_file, oldparams)
    dom_file = parse(newxmlfile)
    readXml(dom_file, newparams)

    print "* <font style='background: pink'>Changed</font> " + \
        "(showing the old value)"
    print "* <font style='background: red'>Removed NvItems</font> " + \
        "(showing the removed item)"
    print "* <font style='background: lightgreen'>Added NvItems</font> " + \
        "(showing the added item)"

    print "{| class='wikitable sortable' border='1'"
    print "|- "
    print "! ID !! Old Owner !! Source "
    print "! class='unsortable'| Old Name !! class='unsortable'| Old Value"
    founddiff = 0

    # x_item[0] = id
    # x_item[1] = sg
    # x_item[2] = source
    # x_item[3] = name
    # x_item[4] = value
    for olditem in oldparams:
        clrsg = ""
        clrname = ""
        clrvalue = ""
        clrremitem = ""
        oldfound = -1
        for index, newitem in enumerate(newparams):
            # find the correct NV/source combination
            if newitem[0] == olditem[0] and newitem[2] == olditem[2]:
                oldfound = index
                # check if the sg, name or value have changed
                if newitem[1] != olditem[1]:
                    clrsg = "style='background: pink' | "
                if newitem[3] != olditem[3]:
                    clrname = "style='background: pink' | "
                if newitem[4] != olditem[4]:
                    clrvalue = "style='background: pink' | "
                if clrsg + clrname + clrvalue != "":
                    diffs = diffs + 1
                    break

        # If the parameter wasn't found among the newparams, the parameter
        # was removed
        if oldfound == -1:
            diffs = diffs + 1
            clrremitem = "style='background: red' | "

        if oldfound > -1:
            newparams.remove(newparams[oldfound])

        if clrsg + clrname + clrvalue + clrremitem != "":
            print "|-"
            print "| %s%s " % (clrremitem, olditem[0])
            print "| %s%s%s " % (clrremitem, clrsg, olditem[1])
            print "| %s%s " % (clrremitem, olditem[2])
            print "| %s%s%s " % (clrremitem, clrname, olditem[3])
            print "| %s%s%s " % (clrremitem, clrvalue, olditem[4])

    print "|} "

    # All parameters that are left in newparam are new
    print "{| class='wikitable sortable' border='1'"
    print "|- "
    print "! ID !! Owner !! Source "
    print "! class='unsortable'| Name !! class='unsortable'| Value"
    clrnewitem = "style='background: lightgreen' | "
    for item in newparams:
        diffs = diffs + 1
        print "|-"
        print "| %s%s " % (clrnewitem, item[0])
        print "| %s%s " % (clrnewitem, item[1])
        print "| %s%s " % (clrnewitem, item[2])
        print "| %s%s " % (clrnewitem, item[3])
        print "| %s%s " % (clrnewitem, item[4])

    print "|} "

    return diffs

# -----------------------------------------

usage = "usage: %prog OLDXML NEWXML BUILDID"
parser = optparse.OptionParser(usage=usage)
(options, args) = parser.parse_args()

if len(args) != 3:
    parser.error("Incorrect number of arguments")

oldxmlfile = args[0]
newxmlfile = args[1]
buildid = args[2]

# Old buildid
oldidfile = "wiki/buildid.txt.old"
with open(oldidfile, 'r') as o:
    oldid = o.readline().lstrip().rstrip()

if not(os.path.isfile(newxmlfile)):
    parser.error("Cannot find %s" % newxmlfile)

print "== Difference between %s and %s ==" % (oldid, buildid)

if not(os.path.isfile(oldxmlfile)):
    print "new product/band"
else:
    differences = makeDiff(oldxmlfile, newxmlfile, oldid, buildid)
    print "%s changes" % differences
