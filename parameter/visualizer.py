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


# ----------------------------------------------------------------------
##


def getText(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)


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
                           value.getAttribute("index"),
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
# Create HTML page with all parameters
#


def createWikiCode(parameters, owners, filename):

    rawfile = "%s.xml" % filename
    with open(rawfile, 'w') as r:
        r.write("<NV>")

    newfile = "%s.txt" % filename
    with open(newfile, 'a') as f:

        f.write("* ''(default)'' = %s\n" % defaultresponsible)
        f.write("* <strike>Striked through</strike> = overwritten values\n")
        f.write("* State 'X' = involved in overwritten values\n")
        f.write("{| class='wikitable sortable' border='1'\n")
        f.write("|- \n")
        f.write("! ID !! class='unsortable'|Index !! Owner !! Source ")
        f.write("!! class='unsortable'|")
        f.write("Name !! class='unsortable'|Value !! State\n")

        params = sorted(parameters)
        for i in xrange(len(params)):
            pretext = ""
            afttext = ""
            statetext = ""

            if i + 1 < len(params):
                if (params[i][0] == params[i + 1][0] and
                    params[i][1] == params[i + 1][1]):
                    pretext += "<strike>"
                    afttext = "</strike>"
                    statetext = "X(%s/%s)" % (str(params[i][0]),
                                              str(params[i][1]))
            if i > 0:
                if (params[i][0] == params[i - 1][0] and
                    params[i][1] == params[i - 1][1]):
                    statetext = "X(%s/%s)" % (str(params[i][0]),
                                              str(params[i][1]))

            f.write("|- \n")
            f.write("| %s%s%s |" % (pretext, str(params[i][0]), afttext))
            f.write("| %s%s%s |" % (pretext, params[i][1], afttext))

            foundowner = 0
            ownertext = "(default)"
            for owner in owners:
                if (params[i][0] == owner[0]):
                    ownertext = str(owner[1])
                    break

            f.write("| %s%s%s |" % (pretext, ownertext, afttext))
            f.write("| %s%s%s |" % (pretext, str(params[i][3]).lstrip(),
                                    afttext))
            f.write("| %s%s%s |" % (pretext, str(params[i][4]).lstrip(),
                                    afttext))
            f.write("| %s%s%s \n" % (pretext, makeSpace(params[i][5]),
                                     afttext))
            f.write("| %s \n" % (statetext))

            with open(rawfile, 'a') as r:
                r.write("<item id=\"%s\" index=\"%s\" sg=\"%s\"" %
                        (params[i][0], params[i][1], ownertext))
                r.write(" source=\"%s\" name=\"%s\" value=\"%s\"/>\n" %
                        (str(params[i][3]).lstrip(),
                         str(params[i][4]).lstrip(),
                         makeSpace(params[i][5])))

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
