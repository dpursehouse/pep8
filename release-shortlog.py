#! /usr/bin/env python

from optparse import OptionParser
import glob
import os
import processes
import shutil
import subprocess
import sys
import tempfile
import urllib
import xml.dom.minidom

import debrevision
import deltapi
import dmsutil

DMS_TAG_SERVER = 'android-cm-web.sonyericsson.net'

# Handle the case that external_package_gits is not available since that
# is a scenario likely to occur on older branches
try:
    import external_package_gits
except:
    print >> sys.stderr, "*** Warning! The python module " \
        "external_package_gits is not available. No log for decoupled " \
        "applications will be created."


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
                      default="http://android-ci.sonyericsson.net/job/" \
                              "offbuild_edream1.0-int/api/xml",
                      help="An official build job URL on Hudson")
    parser.add_option("-n", "--not", dest="not_refs",
                      help="One or more refs (comma separated list) to exclude")
    parser.add_option("--no-count", action="store_false",
                      dest="count", default=True)
    parser.add_option("--no-dw", action="store_true",
                      dest="no_dw", default=False,
                      help="Don't use delivery web server for generating " \
                           "query file, use the DMS Tag Server instead")
    parser.add_option("-l", "--log", dest="logfile",
                      help="Save the list of integrated DMS issues in the " \
                           "`logfile` file")
    parser.add_option("--server", dest="server",
                      default=DMS_TAG_SERVER,
                      help="Name of the DMS Tag Server [default: %default]")
    parser.add_option("--git-cmd", dest="gitCommand",
                      default="git shortlog --no-merges",
                      help="Add arbitrary git command [default: %default]")

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

    dg = DiffGenerator(count=options.count,
                       gitcmd=options.gitCommand,
                       tag_server=options.server,
                       no_dw=options.no_dw)

    dg.generateDiff(oldManifestUrl, newManifestUrl, notFilter)
    if "external_package_gits" in sys.modules:
        dg.diffDecoupledApps(oldManifestUrl, newManifestUrl, notFilter)
    dg.printRevertLog()
    dg.printCommitCount()
    if options.logfile:
        dg.saveDMSList(options.logfile)
    if not options.no_dw:
        dg.dmsqueryQry()


class GitError(Exception):
    """Occurs when executing a git command."""


class DiffGenerator(object):

    def __init__(self, count=True, gitcmd="git shortlog --no-merges",
                 tag_server=DMS_TAG_SERVER, no_dw=True):
        self.all_issues = []
        self.count = count
        self.query = 'DMSquery.qry'
        self.no_dw = no_dw
        self.gitcmd = gitcmd
        self.concatLog = ""
        self.commitCountFiltered = 0
        self.commitCount = 0
        self.revert_logs = ""
        self.tag_server = dmsutil.DMSTagServer(tag_server)

    def generateDiff(self, oldManifestUri, newManifestUri, notFilter=None):
        print "Old manifest: %s" % oldManifestUri
        print "New manifest: %s" % newManifestUri
        oldManifest = miniparse(oldManifestUri)
        newManifest = miniparse(newManifestUri)

        newgits = []
        self.dmslist = []

        for newProject in newManifest.getElementsByTagName("project"):
            matchFound = False
            for oldProject in oldManifest.getElementsByTagName("project"):
                if newProject.getAttribute("name") != \
                        oldProject.getAttribute("name"):
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
                    newProjPath = newProject.getAttribute("path")
                    if not newProjPath:
                        newProjPath = newProject.getAttribute("name")
                    print "** %s **" % newProjPath
                    print "\n".join(self.runGitlog(newProjPath,
                                                   newrev,
                                                   oldrev))

                    log = "\n".join(self.runLog(newProjPath,
                                           newrev,
                                           oldrev))

                    self.dmslist.extend(self.dmsqueryShow(log))

                    self.revert_logs += self.get_revert_info(newProjPath,
                                                             newrev,
                                                             oldrev)

                    self.revert_dms = self.dmsqueryShow(self.revert_logs)

                    if notFilter != None:
                        filteredLog = "\n".join(self.runLog(
                                                newProjPath,
                                                newrev,
                                                oldrev,
                                                notFilter))

                        self.concatLog = self.concatLog + filteredLog

                        self.commitCountFiltered += \
                            self.countCommits(newProjPath,
                                              newrev,
                                              oldrev,
                                              notFilter)

                        self.commitCount += self.countCommits(newProjPath,
                                                              newrev,
                                                              oldrev)
                    else:
                        self.concatLog = self.concatLog + log

                        self.commitCountFiltered += \
                            self.countCommits(newProjPath, newrev, oldrev)
                        self.commitCount += \
                            self.countCommits(newProjPath, newrev, oldrev)

            # if the project does not exist in the old manifest it must have
            # been added since then.
            if not matchFound:
                newgits.append(newProject)

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

        if self.dmslist:
            print "DMS issues found:"
            if self.no_dw:
                dmstitle = self.dmsqueryShowTitle(self.dmslist)
                for issue in dmstitle:
                    print issue
            else:
                # Already in the required format with title, just print it
                for issue in self.dmslist:
                    print issue

    def getPathAndRev(self, manifest, projectName):
        """Search for a project tag with name=projectName in the manifest
        minidom
        Return the contents of the path and revision attributes"""
        for project in manifest.getElementsByTagName("project"):
            if project.getAttribute("name") == projectName:
                path = project.getAttribute("path")
                rev = project.getAttribute("revision")
                break
        # TODO: Improve this with exception handling instead of sys.exit
        if (path == ""):
            print >> sys.stderr, \
                "Cannot find the path to %s in the manifest" \
                % (projectName)
            sys.exit(1)
        if (rev == ""):
            print >> sys.stderr, \
                "Cannot find the revision of %s in the manifest" \
                % (projectName)
            sys.exit(1)
        return (path, rev)

    def getPackageListGits(self, manifestUrl, manifest, semcsystemPath,
                           semcsystemRev, packageFilesFileName, checkoutDir):
        """Clones the gits that are hit by the patterns in the file
        semcsystemPath/packageFilesFileName and checks out the version that is
        stated in the manifest.
        Returns a list of the cloned gits"""
        clonedGits = []
        configFile = os.path.join(semcsystemPath, packageFilesFileName)
        basePath = os.path.join(checkoutDir, semcsystemPath)
        baseGitUrl = "git://review.sonyericsson.net/"

        manifestData = external_package_gits.get_manifest_data(manifestUrl)
        for gitName in \
            external_package_gits.get_gits_from_config(manifestData,
                                                       configFile,
                                                       semcsystemPath):
            (gitPath, gitRev) = self.getPathAndRev(manifest, gitName)
            # Checkout the git in the checkoutDir structure
            gitDir = os.path.join(checkoutDir, gitPath)
            os.makedirs(gitDir)
            gitUrl = os.path.join(baseGitUrl, gitName)
            cmd = "git clone %s %s" % (gitUrl, gitDir)
            (ret, res) = command(cmd)
            if ret != 0:
                raise GitError("Couldn't clone %s" % gitUrl)
            try:
                orgcwd = os.getcwd()
                os.chdir(gitDir)
                cmd = "git checkout %s" % gitRev
                (ret, res) = command(cmd)
                if ret != 0:
                    raise GitError("Couldn't checkout %s in %s" % (gitRev,
                                                                   gitUrl))
                clonedGits.append(gitDir)
            except OSError:
                raise GitError("Couldn't enter the cloned git %s" % gitDir)
            finally:
                os.chdir(orgcwd)

        return clonedGits

    def getPackageDict(self, semcsystemPath, semcsystemRev,
                       packageFilesFileName, packageFileGits, tdir):
        """Reads the lists of xml files that lists delivered debian packages,
        referring to the version semcsystemRev, then calls the debrevision
        package to get a list of debian packages with their revisions.
        Returns a dict with debian package names as keys and version as values
        """
        packageDict = {}

        # Move to the semcsystem git, save the current dir
        try:
            orgdir = os.getcwd()
            os.chdir(semcsystemPath)
        except:
            raise
        # Checkout and get the path to the gits containing the package
        # listings
        # Read the file that lists the patterns for the package files
        blobRef = "%s:%s" % (semcsystemRev, packageFilesFileName)
        cmd = "git cat-file blob %s" % blobRef
        (ret, packageFilePatternsList) = command(cmd)
        # Read the package file matching each pattern
        for pattern in packageFilePatternsList:
            tempPattern = os.path.normpath(os.path.join(tdir,
                                                        semcsystemPath,
                                                        pattern))
            packageFiles = glob.glob(tempPattern)
            for packageFile in packageFiles:
                # Store the revision for each package
                for package in debrevision.parse_xml_package(packageFile):
                    # If the package is already in the dict but with a
                    # different revision, we have inconsistency
                    if package["name"] in packageDict.keys():
                        if packageDict[package["name"]] != package["revision"]:
                            # We have found a package with a name that is
                            # already in the dict but with a different revision
                            print >> sys.stderr, \
                                "Package %s used in multiple revisions" \
                                % package["name"]
                            sys.exit(1)
                    else:
                        # This is the first time we encounter package
                        packageDict[package["name"]] = package["revision"]
        # Move back to the original dir
        try:
            os.chdir(orgdir)
        except:
            raise
        return packageDict

    def createShortLog(self, logList):
        """Converts a log in list format to shortlog format
        Returns a shortlog string"""
        shortlogDict = {}
        shortlog = ""
        for logEntry in logList:
            shortDescr = logEntry['body'].split("\n")[0]
            author = logEntry['author_name']
            if author in shortlogDict.keys():
                shortlogDict[author].append(shortDescr)
            else:
                shortlogDict[author] = [shortDescr]
        # Compose the shortlog from the dict
        for author in sorted(shortlogDict.keys()):
            noOfEntries = len(shortlogDict[author])
            loglines = "\n      ".join(shortlogDict[author])
            shortlog += "%s (%d):\n      %s\n\n" % (author, noOfEntries,
                                                    loglines)
        return shortlog

    def createGitLog(self, logList):
        """Converts a log in list format to normal git log format
        Returns a log string"""
        logDict = {}
        logStr = ""
        for logEntry in logList:
            logStr += "commit %s\nAuthor: %s %s\nDate:   %s\n\n%s\n" \
            % (logEntry['revision'], logEntry['author_name'],
               logEntry['author_email'], logEntry['author_date'],
               logEntry['body'])
        return logStr

    def getDmsInfo(self, logList):
        """Calls the dmsquery script to get DMS info for commits in the logList
        Returns the number of commits with at least one DMS tag and a list
        of DMS id's"""

        dmsList = []
        noOfCommits = 0
        for logEntry in logList:
            gitLog = "commit %s\nAuthor: %s %s\nDate:   %s\n%s" % \
                (logEntry['revision'],
                 logEntry['author_name'],
                 logEntry['author_email'],
                 logEntry['author_date'],
                 logEntry['body'])
            dmsInfo = self.dmsqueryShow(gitLog)
            if dmsInfo:
                noOfCommits += 1
            dmsList.extend(dmsInfo)
        return (noOfCommits, sorted(dmsList))

    def diffDecoupledApps(self, oldManifestUrl, newManifestUrl,
                          notFilter=None):
        """Looks up the xml files describing the binary delivered packages and
        generates the shortlog for those"""

        packageFilesFileName = "external-package-files.txt"
        oldManifest = miniparse(oldManifestUrl)
        newManifest = miniparse(newManifestUrl)
        olddir = tempfile.mkdtemp()
        newdir = tempfile.mkdtemp()

        # Find semcsystem in the old manifest and get the path and sha-1
        (oldSemcsystemPath, oldSemcsystemRev) = \
            self.getPathAndRev(oldManifest, "semctools/semcsystem")
        try:
            oldPackageFileGits = self.getPackageListGits(oldManifestUrl,
                                                         oldManifest,
                                                         oldSemcsystemPath,
                                                         oldSemcsystemRev,
                                                         packageFilesFileName,
                                                         olddir)
        except GitError, e:
            print >> sys.stderr, "*** Error when looking for the xml files " \
                "listing the debian packages: %s" % (e.value)
            sys.exit(1)
        oldPackageDict = self.getPackageDict(oldSemcsystemPath,
                                             oldSemcsystemRev,
                                             packageFilesFileName,
                                             oldPackageFileGits,
                                             olddir)

        # Find semcsystem in the new manifest and get the path and sha-1
        (newSemcsystemPath, newSemcsystemRev) = \
            self.getPathAndRev(newManifest, "semctools/semcsystem")
        try:
            newPackageFileGits = self.getPackageListGits(newManifestUrl,
                                                         newManifest,
                                                         newSemcsystemPath,
                                                         newSemcsystemRev,
                                                         packageFilesFileName,
                                                         newdir)
        except GitError, e:
            print >> sys.stderr, "*** Error when looking for the xml files " \
                "listing the debian packages: %s" % (e.value)
            sys.exit(1)
        newPackageDict = self.getPackageDict(newSemcsystemPath,
                                             newSemcsystemRev,
                                             packageFilesFileName,
                                             newPackageFileGits,
                                             newdir)

        # Check new and updated packages
        for packName in newPackageDict.keys():
            newRev = newPackageDict.pop(packName)
            oldRev = oldPackageDict.pop(packName, "")
            if newRev != oldRev:
                try:
                    logList = deltapi.packagelog(packName, newRev, oldRev)
                    if logList:
                        # Generate the shortlog output format and add log text
                        # to self.concatLog
                        shortLog = self.createShortLog(logList)
                        self.concatLog += self.createGitLog(logList)
                        # Get DMS info
                        (noOfCorrCommits, dmsList) = self.getDmsInfo(logList)
                        # Make the printout
                        print "\n** %s **" % packName
                        print shortLog
                        if dmsList:
                            print "DMS issues found:"
                            if self.no_dw:
                                dmsTitle = self.dmsqueryShowTitle(dmsList)
                                for issue in dmsTitle:
                                    print issue
                            else:
                                # Already in the required format with title,
                                # just print it
                                for issue in dmsList:
                                    print issue
                        self.commitCount += len(logList)
                        self.commitCountFiltered += len(logList)
                except KeyError:
                    print >> sys.stderr, "No log for %s" % packName
                except deltapi.gitrevision.GitExecutionError:
                    print >> sys.stderr, "No log for %s due to an error " \
                        "when running git clone" % packName
                except deltapi.gitrevision.GitReadError:
                    print >> sys.stderr, "No log for %s due to an error " \
                        "when running git log" % packName
                except deltapi.debrevision.processes.ChildRuntimeError:
                    print >> sys.stderr, "No log for %s due to an error " \
                        "when extracting the debian package" % packName
        # Check removed packages
        for packName in oldPackageDict.keys():
            oldRev = oldPackageDict.pop(packName)
            print "Package %s has been removed. Last revision was %s." \
                % (packName, oldRev)

        # Remove temp dirs, never mind if it fails
        shutil.rmtree(olddir, ignore_errors=True)
        shutil.rmtree(newdir, ignore_errors=True)

    def countCommits(self, path=None, newrev=None, oldrev=None,
                     notFilter=None):
        if not self.count:
            return 0

        rootdir = os.getcwd()
        try:
            os.chdir(path)
        except OSError:
            print >> sys.stderr, "Could not change directory to %s" % path
            sys.exit(2)

        cmd = "git log --no-merges --pretty=oneline %s..%s" % (oldrev, newrev)

        if notFilter != None:
            for notItem in notFilter:
                if isRef(notItem):
                    filterStr = " ^%s" % notItem
                    cmd = cmd + filterStr
        (ret, res) = command(cmd)
        os.chdir(rootdir)

        return len(res)

    def get_revert_info(self, path, newrev, oldrev):
        """look up the reverted commits between newrev and oldrev """
        revert_log = ""
        commit_id = ""
        cmdargs = ["git", "rev-list", "--no-merges",
                   "--pretty=oneline", "%s..%s" % (oldrev, newrev)]
        try:
            (code, out, err) = processes.run_cmd(cmdargs, path=path)
            for line in out.split('\n'):
                commit_id = line.split(" ")[0]
                commit_subject = line.split(" ", 1)[-1]
                if commit_subject.startswith("Revert \""):
                    try:
                        cmdargs = ["git", "rev-list", "--no-walk",
                                   "--pretty=medium", commit_id]
                        (code, out, err) = processes.run_cmd(cmdargs, path=path)
                        revert_log += out + '\n'
                    except (processes.ChildExecutionError, IndexError,
                            ValueError), err:
                        raise deltapi.gitrevision.GitExecutionError(
                                              "Tried to execute: %s\n" \
                                              "Result was: %s" % (cmdargs, err))
        except (processes.ChildExecutionError, IndexError, ValueError), err:
            raise deltapi.gitrevision.GitExecutionError("Tried to execute: " \
                                                        "%s\nResult was: %s" %
                                                        (cmdargs, err))
        return revert_log

    def runGitlog(self, path=None, newrev=None, oldrev=None):
        rootdir = os.getcwd()
        try:
            os.chdir(path)
        except OSError:
            print >> sys.stderr, "Could not change directory to %s" % path
            sys.exit(2)
        cmd = "%s %s..%s" % (self.gitcmd, oldrev, newrev)
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

    def printCommitCount(self):
        """Prints the number of commits counted by self.commitCount and
        self.commitCountFiltered"""
        if self.count == True:
            print "\nCommits introduced: %d" % self.commitCount
            print "Commits used for DMS query: %d" % self.commitCountFiltered

    def printRevertLog(self):
        """Prints the reverted commits log by self.revert_logs and list
        reverted commits DMS by self.revert_dms
        Showing the commits that revert other commits"""
        if self.revert_logs:
            print "\nShowing the commits that revert " \
                  "other commits:\n%s" % self.revert_logs
            if self.revert_dms:
                if self.no_dw:
                    dms_with_title = self.dmsqueryShowTitle(self.revert_dms)
                    print "\nReverted DMS:\n%s" % '\n'.join(dms_with_title)
                else:
                    # Already in the required format with title, just print it
                    print "\nReverted DMS:\n%s" % '\n'.join(self.revert_dms)

    def dmsqueryQry(self):
        cmd = "dmsquery -qry %s" % self.query

        dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        dmsquery.communicate(input=self.concatLog)
        dmsquery.stdin.close()

    def dmsqueryShow(self, gitlog):
        """Extracts the list of DMS issue IDs from the git log output."""
        if self.no_dw:
            cmd = "dmsquery --show"
        else:
            cmd = "dmsquery --show-t"

        dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        output = dmsquery.communicate(input=gitlog)[0]
        dmslist = []
        for line in output.splitlines():
            dmslist.append(line.strip())
        return dmslist

    def dmsqueryShowTitle(self, dmslist):
        """Contacts the DMS Tag Server and gets the title for a given list
        of DMS IDs.
        Returns a list of lines with the DMS IDs followed by the title."""
        dmstitle = []
        if dmslist:
            try:
                dmstitle = self.tag_server.dms_with_title(dmslist)
            except:
                # If we can't retrieve the title information, just print error
                # and return the `dmslist` back.
                print >> sys.stderr, "Error retrieving DMS title."
        return dmstitle if dmstitle else dmslist

    def saveDMSList(self, filename):
        """Saves the list of DMS issues in a text file, `filename`."""
        if self.dmslist:
            try:
                open(filename, 'wb').write('\n'.join(self.dmslist))
            except (OSError, IOError), err:
                print >> sys.stderr, "Could not write dmslist to %s\n%s" % \
                                     (filename, err)
                sys.exit(2)


def isRef(candidate, gitpath=None):
    cmd = "git show-ref %s" % candidate
    (ret, res) = command(cmd)
    if ret == 0:
        return True
    return False


def command(command):
    gitCmd = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    result = gitCmd.communicate()[0].splitlines()
    retval = gitCmd.returncode
    return (retval, result)


def urljoin(first, *rest):
    return "/".join([first.rstrip('/'),
           "/".join([part.lstrip('/') for part in rest])])

if __name__ == "__main__":
    main(sys.argv)
