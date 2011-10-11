#!/usr/bin/env python

# -----------------------------------------------------------------------------
# visualizer.py
#
# Usage: ./visualizer.py <masterfile> <ownerfile>
#
# Given one product/band configuration xml file (masterfile) and an xml file
# containing the owner of all NvItems (ownerfile), this script will generate a
# file that is wiki formatted displaying a table containing the NvItems:
#
# | NvItem ID | SG of the Owner | xmlfile source | NvItem Name | NvItem Value |
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

# ----------------------------------------------------------------------
##


def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)


def repeat(times, what):
    returnval = ""
    for num in range(0, times):
        returnval += "%s" % what
    return returnval


def makeSpace(what):
    returnval = ""
    for ch in what:
        if ch == ',':
            returnval += "%s " % ch
        else:
            returnval += "%s" % ch
    return returnval.lstrip().rstrip()

#
# ----------------------------------------------------------------------
# Read the old raw list
#

oldparams = []


def readOld(oldlist):
    global oldparams
    parameters = oldlist.getElementsByTagName("item")
    for param in parameters:
        oldparams.append([int(param.getAttribute("id")),
                          str(param.getAttribute("sg")),
                          str(param.getAttribute("source")),
                          str(param.getAttribute("name")),
                          makeSpace(str(param.getAttribute("value")))])

    return
#
# ----------------------------------------------------------------------
# Read the owner list
#

defaultresponsible = ""


def handleOwners(ownerlist, owners):
    global defaultresponsible
    param = ownerlist.getElementsByTagName("default")[0]
    defaultresponsible = str(param.getAttribute("responsible"))
    parameters = ownerlist.getElementsByTagName("NV")
    return handleNV(parameters, owners)


def handleNV(parameters, owners):
    for param in parameters:
        owners.append([int(param.getAttribute("id")),
                       str(param.getAttribute("responsible"))])
    return owners

#
# ----------------------------------------------------------------------
# Read the parameters
#

order = 0


def handleParameters(parameterlist, thisfile, level, parameters):
    paraIncludes = parameterlist.getElementsByTagName("xi:include")
    for value in paraIncludes:
        nextfile = str(value.getAttribute("href")).split('#')
        filepath = os.path.abspath(os.path.join(os.path.dirname(thisfile),
                                                nextfile[0]))
        dom_temp = parse(filepath)
        parameters = handleParameters(dom_temp, filepath,
                                      level + 1, parameters)
    paraValues = parameterlist.getElementsByTagName("NvItem")
    return handleParaValues(paraValues, os.path.basename(thisfile),
                            parameters, level)


def handleParaValues(values, thisfile, parameters, level):
    global order
    for value in values:
        order = order + 1
        #if (str(value.getAttribute("encoding")) == "dec"):
        # TODO: add encoding types
        parameters.append([int(value.getAttribute("id")),
                           order,
                           thisfile,
                           str(value.getAttribute("name")),
                           getText(value.childNodes),
                           order])
    return parameters


#
# ----------------------------------------------------------------------
# Match owners to parameters
#


def matchOwners(parameters, owners):
    reponsiblelist = ""
    for param in sorted(parameters):
        for owner in owners:
            if (param[0] == owner[0]):
                reponsiblelist += "---\n"
                reponsiblelist += "%s\n" % str(param)
                reponsiblelist += "%s\n" % str(owner)
    return reponsiblelist

#
# ----------------------------------------------------------------------
# Check if this diff from latest run
#

oldparams = []


def diff(pid, sg, source, name, value):
    global oldparams
    returnstring = ""
    for para in oldparams:
        if(para[0] == pid and para[2] == source):
            if para[1] != sg:
                returnstring = " sg "
            if para[3] != name:
                returnstring += " name "
            if para[4] != value:
                returnstring += " value "
            if returnstring != "":
                return returnstring
    return ""


#
# ----------------------------------------------------------------------
# Create HTML page with all parameters
#


def createWikiCode(parameters, owners, filename):

    oldidfile = "wiki/buildid.txt.old"
    with open(oldidfile, 'r') as o:
        oldid = o.readline()

    rawfile = "%s.xml" % filename
    with open(rawfile, 'w') as r:
        r.write("<NV>")

    newfile = "%s.txt" % filename
    with open(newfile, 'a') as f:

        f.write("<br>''(default)'' = %s\n" % defaultresponsible)
        f.write("<br><strike>Striked through</strike> = overwritten values\n")
        f.write("<br><font style='background: lightpink'>Pink background")
        f.write("</font> = changed parameter from previous run (%s)\n" % oldid)
        f.write("{| class='wikitable sortable' border='1'\n")
        f.write("|- \n")
        f.write("! ID !! Owner !! Source !! class='unsortable'|")
        f.write("Name !! class='unsortable'|Value\n")

        previousparam = 0

        params = sorted(parameters)
        for i in xrange(len(params)):
            pretext = ""
            afttext = ""

            if i + 1 < len(params):
                if params[i][0] == params[i + 1][0]:
                    pretext += "<strike>"
                    afttext = "</strike>"

            f.write("|- \n")
            f.write("| %s%s%s |" % (pretext, str(params[i][0]), afttext))

            foundowner = 0
            ownertext = "(default)"
            for owner in owners:
                if (params[i][0] == owner[0]):
                    ownertext = str(owner[1])
                    break

            diffval = diff(params[i][0], ownertext, str(params[i][2]).lstrip(),
                           str(params[i][3]).lstrip(),
                           makeSpace(str(params[i][4])).lstrip().rstrip())
            if diffval != "":
                # TODO: mark only the changed in pink, not the entire row
                pretext = "style='background: pink' | " + pretext

            f.write("| %s%s%s |" % (pretext, ownertext, afttext))
            f.write("| %s%s%s |" % (pretext, str(params[i][2]).lstrip(),
                                    afttext))
            f.write("| %s%s%s |" % (pretext, str(params[i][3]).lstrip(),
                                    afttext))
            f.write("| %s%s%s \n" % (pretext, makeSpace(str(params[i][4])),
                                     afttext))

            with open(rawfile, 'a') as r:
                r.write("<item id=\"%s\" sg=\"%s\" source=\"%s\"" %
                        (params[i][0], ownertext, str(params[i][2]).lstrip()))
                r.write(" name=\"%s\" value=\"%s\"/>\n" %
                        (str(params[i][3]).lstrip(),
                         makeSpace(str(params[i][4]))))

        with open(rawfile, 'a') as r:
            r.write("</NV>")
        f.write("|}\n")

#
# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
#


def parseOne(masterfile, ownerfile):
    owners = []
    parameters = []
    responsiblelist = ""

    masterbasename = os.path.basename(masterfile)
    name = masterbasename.split('.')

    # Read the list of previous parameters if it exists
    if os.path.isfile("wiki/%s.xml.old" % name[0]):
        dom_oldlist = parse("wiki/%s.xml.old" % name[0])
        readOld(dom_oldlist)

    # Read the owner list
    dom_owner = parse(ownerfile)
    handleOwners(dom_owner, owners)

    # Read the parameters
    dom_param = parse(masterfile)
    handleParameters(dom_param, masterfile, 1, parameters)

    # Match owners to parameters
    responsiblelist = matchOwners(parameters, owners)

    # Create WIKI page
    filename = "wiki/%s" % name[0]
    htmltext = createWikiCode(parameters, owners, filename)

    return name[0]

# -----------------------------------------

usage = "usage: %prog XMLFILE OWNERFILE"
parser = optparse.OptionParser(usage=usage)
(options, args) = parser.parse_args()

if len(args) != 2:
    parser.print_help()
    parser.error("Incorrect number of arguments")

masterfile = args[0]
ownerfile = args[1]

parseOne(masterfile, ownerfile)
