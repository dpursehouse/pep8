#!/usr/bin/env python

# -----------------------------------------------------------------------------
# create_structure.py
#
# Usage: ./create_structure.py <masterfile>
#
# Given one product/band configuration xml file (masterfile), this script will
# generate a file that is wiki formatted and all xml files related to the
# masterfile and how the relation is.
#
# -----------------------------------------------------------------------------

import sys
import os
from xml.dom.minidom import parse, parseString
import array
import optparse


#
# ----------------------------------------------------------------------
# Read and format the parameters
#


def formatLevel(level, text):
    if level == 1:
        return ";%s" % text
    else:
        return "%s[[File:1a.gif]]%s" % (":" * (level - 1), text)


def handleXmls(parameterlist, path, thisfile, level, parameters, savefile):

    paraIncludes = parameterlist.getElementsByTagName("xi:include")
    paraValues = parameterlist.getElementsByTagName("NvItem")

    with open(savefile, 'a') as f:
        f.write("%s (%s)\n" % (formatLevel(level, thisfile), len(paraValues)))

    for value in paraIncludes:
        nextfilepath = str(value.getAttribute("href")).split('#')
        filename = os.path.basename(nextfilepath[0])
        filepath = os.path.abspath("%s/%s" %
                                   (path, os.path.dirname(nextfilepath[0])))
        dom_temp = parse("%s/%s" % (filepath, filename))
        handleXmls(dom_temp, filepath, filename,
                   level + 1, parameters, savefile)

    return

#
# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
#

htmlfilename = []
xmlfiles = []

##


def parseOne(masterfile):
    parameters = []
    tabletext = ""

    # Create WIKI page
    masterbasename = os.path.basename(masterfile)
    name = masterbasename.split('.')
    filename = "wiki/%s.layer.txt" % name[0]
    with open(filename, 'w') as f:
        writetext = "The include structure of the nv xml files. The number"
        writetext += " within parenthesis are the amount of NvItems within"
        writetext += " that particular xml file.<br><br>\n"
        f.write(writetext)

    # Read the xml files
    dom_param = parse(masterfile)
    tabletext += "%s" % handleXmls(dom_param, os.path.dirname(masterfile),
                                   masterbasename, 1, parameters, filename)

    return name[0]

# -----------------------------------------

usage = "usage: %prog XMLFILE"
parser = optparse.OptionParser(usage=usage)
(options, args) = parser.parse_args()

if len(args) != 1:
    parser.print_help()
    parser.error("Incorrect number of arguments")

masterfile = args[0]

print parseOne(masterfile)
