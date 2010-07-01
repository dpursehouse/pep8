#! /usr/bin/env python

import subprocess
import sys
import os
import xml.dom.minidom
import urllib

def miniparse(url):
    return xml.dom.minidom.parse(urllib.urlopen(url))

def getTextOfFirstTagByName(element, name):
    rc = ""
    childElements = element.getElementsByTagName(name)
    if len(childElements) > 0:
        for node in childElements[0].childNodes:
            if node.nodeType == node.TEXT_NODE:
                rc = rc + node.data
    return rc.strip()

def main(argv):

    oldBuildId = argv[1]
    newBuildId = argv[2]

    oldManifestUrl = ""
    newManifestUrl = ""

    if os.path.isfile(oldBuildId) or oldBuildId.startswith('http://'):
        oldManifestUrl = oldBuildId
        oldJobUrl = "skip"
    else:
        oldJobUrl = "do"
    if os.path.isfile(newBuildId) or newBuildId.startswith('http://'):
        newManifestUrl = newBuildId
        newJobUrl = "skip"
    else:
        newJobUrl = "do"

    if len(argv) > 3:
        mainJobUrl = argv[3]
    else:
        mainJobUrl = "http://android-ci.sonyericsson.net/job/offbuild_edream1.0-int/api/xml"

    if oldJobUrl == "do" or newJobUrl == "do":
        mainJobXml = miniparse(mainJobUrl)
        for build in mainJobXml.getElementsByTagName("build"):
            buildJobUrl = getTextOfFirstTagByName(build, "url")
            buildJobXml = miniparse(urljoin(buildJobUrl, "api", "xml"))
            try:
                text = getTextOfFirstTagByName(buildJobXml, "description")
                if oldJobUrl == "do":
                    if text.find(oldBuildId) != -1:
                        oldJobUrl = buildJobUrl
                        print "Found build job url: %s" % buildJobUrl
                if newJobUrl == "do":
                    if text.find(newBuildId) != -1:
                        newJobUrl = buildJobUrl
                        print "Found build job url: %s" % buildJobUrl
            except AttributeError:
                continue
            if oldJobUrl != "do" and newJobUrl != "do":
                break

    if oldManifestUrl == "" and oldJobUrl != "do":
        oldManifestUrl = urljoin(oldJobUrl,
                             "artifact", "result-dir/manifest_static.xml")

    if newManifestUrl == "" and newJobUrl != "do":
        newManifestUrl = urljoin(newJobUrl,
                             "artifact", "result-dir/manifest_static.xml")

    if newManifestUrl == "":
        print >> sys.stderr, "Could not find new manifest"

    if oldManifestUrl == "":
        print >> sys.stderr, "Could not find old manifest"

    generateDiff(oldManifestUrl, newManifestUrl)

def urljoin(first, *rest):
    return "/".join([first.rstrip('/'),
           "/".join([part.lstrip('/') for part in rest])])

def generateDiff(oldManifestUri, newManifestUri):
    print "Old manifest: %s" % oldManifestUri
    print "New manifest: %s" % newManifestUri
    oldManifest = miniparse(oldManifestUri)
    newManifest = miniparse(newManifestUri)

    newgits = []
    dmslist = []
    for newProject in newManifest.getElementsByTagName("project"):
        matchFound = False
        for oldProject in oldManifest.getElementsByTagName("project"):
            if newProject.getAttribute("name") != oldProject.getAttribute("name"):
                continue
            matchFound = True
            try:
                newrev = newProject.getAttribute("revision")
            except AttributeError:
                print >> sys.stderr, "Missing new revision for %s" % (
                                    newProject.getAttribute("name"))
                continue
            try:
                oldrev = oldProject.getAttribute("revision")
            except AttributeError:
                print >> sys.stderr, "Missing old revision for %s" % (
                                     oldProject.getAttribute("name"))
                continue

            if newrev == oldrev:
                continue
            else:
                print "** %s **" % newProject.getAttribute("path")
                print "\n".join(runShortlog(newProject.getAttribute("path"), newrev, oldrev))
                log = "\n".join(runLog(newProject.getAttribute("path"), newrev, oldrev))
                dmslist.extend(dmsqueryShow(log))
                dmsqueryQry(log)

        # if the project does not exist in the old manifest it must have
        # been added since then.
        if not matchFound:
            newgits.append(newProject)

    if len(newgits) > 0:
        print "New gits added:"
        for proj in newgits:
            print "name=\"%s\" path=\"%s\"" % (proj.getAttribute("name"), proj.getAttribute("path"))

    # project name is non-volatile so it can be used as key to find the
    # the same projects in two manifests.
    newset = set([proj.getAttribute("name") for proj in newManifest.getElementsByTagName("project")])
    oldset = set([proj.getAttribute("name") for proj in oldManifest.getElementsByTagName("project")])

    # projects in the old manifest that can't be found in the new, must have
    # been removed.
    removed = oldset - newset
    if len(removed) > 0:
        print "Removed gits:"
        print "\n".join(removed)

    print "DMS issues found:"
    for issue in dmslist:
        print issue

def runShortlog(path=None, newrev=None, oldrev=None):
    rootdir = os.getcwd()
    try:
        os.chdir(path)
    except OSError:
        print >> sys.stderr, "Could not change directory to %s" % path
    cmd = "git shortlog --no-merges %s..%s" % (oldrev, newrev)
    (ret, res) = command(cmd)
    os.chdir(rootdir)
    return res

def runLog(path=None, newrev=None, oldrev=None):
    rootdir = os.getcwd()
    try:
        os.chdir(path)
    except OSError:
        print >> sys.stderr, "Could not change direcotory to %s" % path
    cmd = "git log %s..%s" % (oldrev, newrev)
    (ret, res) = command(cmd)
    os.chdir(rootdir)
    return res

def dmsqueryQry(gitlog):
    cmd = "dmsquery -qry DMSquery.qry"
    dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dmsquery.communicate(input=gitlog)[0]

def dmsqueryShow(gitlog):
    cmd = "dmsquery --show-t"
    dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dmslist = dmsquery.communicate(input=gitlog)[0]
    return dmslist.splitlines()

def command(command):

    gitCmd = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    result = gitCmd.communicate()[0].split('\n')
    retval = gitCmd.returncode
    return (retval, result)

if __name__ == "__main__":
    main(sys.argv)
