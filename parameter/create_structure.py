#!/usr/bin/env python

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


def parseOne(masterfilepath, masterfile, ownerpath):
    parameters = []
    tabletext = ""

    # Create WIKI page
    name = masterfile.split('.')
    filename = "wiki/%s.layer.txt" % name[0]
    with open(filename, 'w') as f:
        writetext = "The include structure of the nv xml files. The number"
        writetext += " within parenthesis are the amount of NvItems within"
        writetext += " that particular xml file.<br><br>\n"
        f.write(writetext)

    # Read the xml files
    dom_param = parse("%s/%s" % (masterfilepath, masterfile))
    tabletext += "%s" % handleXmls(dom_param, masterfilepath, masterfile,
                                   1, parameters, filename)

    return name[0]

# -----------------------------------------

usage = "usage: %prog [options] XMLFILE\n"
parser = optparse.OptionParser(usage=usage)
(options, args) = parser.parse_args()

if len(args) != 3:
    parser.print_help()
    parser.error("Incorrect number of arguments")

masterfilepath = args[0]
masterfile = args[1]
ownerpath = args[2]

print parseOne(masterfilepath, masterfile, ownerpath)
