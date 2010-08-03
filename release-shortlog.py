#! /usr/bin/env python

import subprocess
import sys
import os
import xml.dom.minidom
import urllib
from optparse import OptionParser

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

    parser = OptionParser()

    parser.add_option("-j", "--job", dest="job",
                        default="http://android-ci.sonyericsson.net/job/offbuild_edream1.0-int/api/xml",
                        help="An official build job URL on Hudson")
    parser.add_option("-n", "--not", dest="not_refs",
                        help="One or more refs (comma separated list) to exclude")
    parser.add_option("--no-count", action="store_false",
                      dest="count", default=True)
    parser.add_option("--qry", dest="queryFile", default="DMSquery.qry")

    (options, args) = parser.parse_args()


    oldBuildId = args[0]
    newBuildId = args[1]

    mainJobUrl = options.job

    if options.not_refs == None:
        notFilter = None
    else:
        notFilter = options.not_refs.split(',')

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

    if not (mainJobUrl.endswith('api/xml') or mainJobUrl.endswith('api/xml/')):
        mainJobUrl = urljoin(mainJobUrl, 'api', 'xml')

    if oldJobUrl == "do" or newJobUrl == "do":
        mainJobXml = miniparse(mainJobUrl)
        for build in mainJobXml.getElementsByTagName("build"):
            buildJobUrl = getTextOfFirstTagByName(build, "url")
            buildJobXml = miniparse(urljoin(buildJobUrl, "api", "xml"))
            try:
                text = getTextOfFirstTagByName(buildJobXml, "description")
                if oldJobUrl == "do":
                    if text.strip() == oldBuildId:
                        oldJobUrl = buildJobUrl
                        print "Found build job url: %s" % buildJobUrl
                if newJobUrl == "do":
                    if text.strip() == newBuildId:
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
        sys.exit(1)

    if oldManifestUrl == "":
        print >> sys.stderr, "Could not find old manifest"
        sys.exit(1)

    dg = DiffGenerator(count=options.count, query=options.queryFile)

    dg.generateDiff(oldManifestUrl, newManifestUrl, notFilter)

class DiffGenerator(object):

    def __init__(self, count=True, query="DMSQuery.qry"):
        self.count = count
        self.query = query

    def generateDiff(self, oldManifestUri, newManifestUri, notFilter=None):
        print "Old manifest: %s" % oldManifestUri
        print "New manifest: %s" % newManifestUri
        oldManifest = miniparse(oldManifestUri)
        newManifest = miniparse(newManifestUri)

        newgits = []
        dmslist = []
        concatLog = ""
        commitCountFiltered = 0
        commitCount = 0

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
                    print "\n".join(self.runShortlog(newProject.getAttribute("path"),
                                                newrev,
                                                oldrev))

                    log = "\n".join(self.runLog(newProject.getAttribute("path"),
                                           newrev,
                                           oldrev))

                    dmslist.extend(self.dmsqueryShow(log))

                    if notFilter != None:
                        filteredLog = "\n".join(self.runLog(
                                                newProject.getAttribute("path"),
                                                newrev,
                                                oldrev,
                                                notFilter))

                        concatLog = concatLog + filteredLog

                        commitCountFiltered += \
                            self.countCommits(newProject.getAttribute("path"),
                                         newrev,
                                         oldrev,
                                         notFilter)

                        commitCount += self.countCommits(newProject.getAttribute("path"),
                                                    newrev,
                                                    oldrev)
                    else:
                        concatLog = concatLog + log

                        commitCountFiltered += self.countCommits(
                                                    newProject.getAttribute("path"),
                                                    newrev,
                                                    oldrev)
                        commitCount += self.countCommits(
                                            newProject.getAttribute("path"),
                                            newrev, oldrev)

            # if the project does not exist in the old manifest it must have
            # been added since then.
            if not matchFound:
                newgits.append(newProject)
        self.dmsqueryQry(concatLog)

        if len(newgits) > 0:
            print "New gits added:"
            for proj in newgits:
                print "name=\"%s\" path=\"%s\"" % \
                    (proj.getAttribute("name"), proj.getAttribute("path"))

        # project name is non-volatile so it can be used as key to find the
        # the same projects in two manifests.
        newset = set([proj.getAttribute("name") \
                    for proj in newManifest.getElementsByTagName("project")])
        oldset = set([proj.getAttribute("name") \
                    for proj in oldManifest.getElementsByTagName("project")])

        # projects in the old manifest that can't be found in the new, must have
        # been removed.
        removed = oldset - newset
        if len(removed) > 0:
            print "Removed gits:"
            print "\n".join(removed)

        print "DMS issues found:"
        for issue in dmslist:
            print issue
        if self.count == True:
            print "\nCommits introduced: %d" % commitCount
            print "Commits used for DMS query: %d" % commitCountFiltered

    def countCommits(self, path=None, newrev=None, oldrev=None, notFilter=None):
        if not self.count:
            return 0

        rootdir = os.getcwd()
        try:
            os.chdir(path)
        except OSError:
            print >> sys.stderr, "Could not change direcotory to %s" % path
            sys.exit(2)

        cmd = "git log --pretty=oneline %s..%s" % (oldrev, newrev)

        if notFilter != None:
            for notItem in notFilter:
                if isRef(notItem):
                    filterStr = " ^%s" % notItem
                    cmd = cmd + filterStr
        (ret, res) = command(cmd)
        os.chdir(rootdir)

        return len(res)

    def runShortlog(self, path=None, newrev=None, oldrev=None):
        rootdir = os.getcwd()
        try:
            os.chdir(path)
        except OSError:
            print >> sys.stderr, "Could not change directory to %s" % path
            sys.exit(2)

        cmd = "git shortlog --no-merges %s..%s" % (oldrev, newrev)
        (ret, res) = command(cmd)
        os.chdir(rootdir)
        return res

    def runLog(self, path=None, newrev=None, oldrev=None, notFilter=None):
        rootdir = os.getcwd()
        try:
            os.chdir(path)
        except OSError:
            print >> sys.stderr, "Could not change direcotory to %s" % path
            sys.exit(2)

        cmd = "git log %s..%s" % (oldrev, newrev)

        if notFilter != None:
            for notItem in notFilter:
                if isRef(notItem):
                    filterStr = " ^%s" % notItem
                    cmd = cmd + filterStr

        (ret, res) = command(cmd)
        os.chdir(rootdir)
        return res

    def dmsqueryQry(self, gitlog):
        cmd = "dmsquery -qry %s" % self.query

        dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        dmsquery.communicate(input=gitlog)
        dmsquery.stdin.close()

    def dmsqueryShow(self, gitlog):
        cmd = "dmsquery --show-t"
        dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        dmslist = dmsquery.communicate(input=gitlog)[0]
        return dmslist.splitlines()

def isRef(candidate, gitpath=None):
    cmd = "git show-ref %s" % candidate
    (ret, res) = command(cmd)
    if ret == 0:
        return True
    return False

def command(command):

    gitCmd = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    result = gitCmd.communicate()[0].split('\n')
    retval = gitCmd.returncode
    return (retval, result)

def urljoin(first, *rest):
    return "/".join([first.rstrip('/'),
           "/".join([part.lstrip('/') for part in rest])])

if __name__ == "__main__":
    main(sys.argv)
