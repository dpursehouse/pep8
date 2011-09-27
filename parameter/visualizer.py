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
    returnval=""
    for num in range(0,times):
        returnval += "%s" % what
    return returnval

def makeSpace(what):
    returnval=""
    for ch in what:
        if ch == ',':
            returnval += "%s " % ch
        else:
            returnval += "%s" % ch
    return returnval

#
# ----------------------------------------------------------------------
# Read the owner list
#

defaultresponsible=""

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

order=0

def handleParameters(parameterlist, path, thisfile, level, parameters):
#    print " - - - - - - - -"
#    print "path: %s" % path
#    print "thisfile: %s" % thisfile
#    print "level: %s" % level
    xmlfiles.append(thisfile)
    paraIncludes = parameterlist.getElementsByTagName("xi:include")
    for value in paraIncludes:
        nextfilepath = str(value.getAttribute("href")).split('#')
        filename = os.path.basename(nextfilepath[0])
        filepath = os.path.abspath("%s/%s" % (path, os.path.dirname(nextfilepath[0])))
        dom_temp = parse("%s/%s" % (filepath, filename))
        parameters = handleParameters(dom_temp, filepath, filename, level+1, parameters)
    paraValues = parameterlist.getElementsByTagName("NvItem")
    return handleParaValues(paraValues, thisfile, parameters, level)
    
def handleParaValues(values, thisfile, parameters, level):
    global order
    for value in values:
        order=order+1
#        if (str(value.getAttribute("encoding")) == "dec"):     # TODO: add encoding types
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
    reponsiblelist=""
    for param in sorted(parameters):
        for owner in owners :
            if (param[0] == owner[0]):
                reponsiblelist+="---\n"
                reponsiblelist+="%s\n" % str(param)
                reponsiblelist+="%s\n" % str(owner)
    return reponsiblelist

#
# ----------------------------------------------------------------------
# Check if this diff from latest run
#

def diff(param):
    #if param == 535:
    #    return True
    return False

#
# ----------------------------------------------------------------------
# Create HTML page with all parameters
#

def createWikiCode (parameters, owners, filename):
    with open(filename, 'a') as f:
     
        f.write("<br>''(default)'' = %s\n" % defaultresponsible)
        f.write("<br><strike>Striked through</strike> = overwritten values\n")
        f.write("<!-- <br><font style='background: lightgreen'>Green background</font> = value change or added parameter from last run -->\n")
        f.write("{| class='wikitable sortable' border='1'\n")
        f.write("|- \n")
        f.write("! ID !! Owner !! Source !! class='unsortable'|Name !! class='unsortable'|Value\n")
        
        previousparam = 0
        
        params = sorted(parameters)
        for i in xrange(len(params)):

            pretext=""
            afttext=""

            if i+1 < len(params):
                if params[i][0] == params[i+1][0]:
                    pretext+="<strike>"
                    afttext="</strike>"

            if diff(params[i][0]):
                pretext+="style='background: lightgreen' | "

            f.write("|- \n")
            f.write("| %s%s%s\n" % (pretext, str(params[i][0]), afttext))

            foundowner = 0
            for owner in owners :
                if (params[i][0] == owner[0]):
                    foundowner = 1
                    f.write("| %s%s%s\n" % (pretext, str(owner[1]), afttext))
            if foundowner == 0:
                f.write("| %s''(default)''%s\n" % (pretext, afttext))
            #f.write("| %s%s%s\n" % (pretext, params[i][5], afttext))
            f.write("| %s%s%s\n" % (pretext, str(params[i][2]).lstrip(), afttext))
            f.write("| %s%s%s\n" % (pretext, str(params[i][3]).lstrip(), afttext))
            f.write("| %s%s%s\n" % (pretext, makeSpace(str(params[i][4])).lstrip().rstrip(), afttext))
        
        f.write("|}\n")
    
#
# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
#

#xmlpath="/home/CORPUSERS/23052936/code2/blue-8960/modem_proc/modem/rfa/target/qcn/msm8960/na713_sv/etc"
#startfile="SEMC_ProductX_BandYZ_MASTERFILE.xml"
#ownerfile="owner.xml"
#masterfilexml="SEMC_MASTER.xml"

htmlfilename=[]
xmlfiles = []

##

def parseOne(masterfilepath, masterfile, ownerpath):
    owners = []
    parameters = []
    responsiblelist=""

    # Read the owner list
    dom_owner = parse(ownerpath)
    handleOwners(dom_owner, owners)
    
    # Read the parameters
    dom_param = parse("%s/%s" % (masterfilepath, masterfile))
    handleParameters(dom_param, masterfilepath, masterfile, 1, parameters)
    
    # Match owners to parameters
    responsiblelist = matchOwners(parameters, owners)
    
    # Create WIKI page
    name = masterfile.split('.')
    filename = "wiki/%s" % name[0]
    htmltext = createWikiCode (parameters, owners, filename)

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

#print "----------------------"
#print "masterfilepath: %s" % masterfilepath
#print "masterfile: %s" % masterfile
#print "ownerpath: %s" % ownerpath
parseOne(masterfilepath, masterfile, ownerpath)

