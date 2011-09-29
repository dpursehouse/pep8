#!/usr/bin/env python

#import label_info
#import semcutil
import sys
import os
#import xml.parsers.expat
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


def handleParameters(parameterlist, path, thisfile, level, parameters):
    xmlfiles.append(thisfile)
    paraIncludes = parameterlist.getElementsByTagName("xi:include")
    for value in paraIncludes:
        nextfilepath = str(value.getAttribute("href")).split('#')
        filename = os.path.basename(nextfilepath[0])
        filepath = os.path.abspath("%s/%s" % (path,
                                              os.path.dirname(nextfilepath[0]
                                                              )))
        dom_temp = parse("%s/%s" % (filepath, filename))
        parameters = handleParameters(dom_temp, filepath, filename,
                                      level + 1, parameters)
    paraValues = parameterlist.getElementsByTagName("NvItem")
    return handleParaValues(paraValues, thisfile, parameters, level)


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
    rawfile = "%s.xml" % filename
    with open(rawfile, 'w') as r:
        r.write("<NV>")

    with open(filename, 'a') as f:

        f.write("<br>''(default)'' = %s\n" % defaultresponsible)
        f.write("<br><strike>Striked through</strike> = overwritten values\n")
        f.write("<br><font style='background: lightpink'>Pink background")
        f.write("</font> = changed parameter from previous run\n")
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
                           str(params[i][4]).lstrip().rstrip())
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
                        (str(params[i][3]).lstrip(), str(params[i][4])))

        with open(rawfile, 'a') as r:
            r.write("</NV>")
        f.write("|}\n")

#
# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
#

htmlfilename = []
xmlfiles = []

##


def parseOne(masterfilepath, masterfile, ownerpath):
    owners = []
    parameters = []
    responsiblelist = ""

    name = masterfile.split('.')

    # Read the list of previous parameters
    if os.path.exists("wiki/%s.txt.xml.old" % name[0]):
        dom_oldlist = parse("wiki/%s.txt.xml.old" % name[0])
        readOld(dom_oldlist)

    # Read the owner list
    dom_owner = parse(ownerpath)
    handleOwners(dom_owner, owners)

    # Read the parameters
    dom_param = parse("%s/%s" % (masterfilepath, masterfile))
    handleParameters(dom_param, masterfilepath, masterfile, 1, parameters)

    # Match owners to parameters
    responsiblelist = matchOwners(parameters, owners)

    # Create WIKI page
    filename = "wiki/%s.txt" % name[0]
    htmltext = createWikiCode(parameters, owners, filename)

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

parseOne(masterfilepath, masterfile, ownerpath)
