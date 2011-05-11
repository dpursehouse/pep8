#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Fetch build (GIT) revisions of Debian packages.
Depends on gitrevision and processes"""
import collections
import os
import shutil
import sys
import tempfile
import urllib2
import xml.dom.minidom
import warnings

from debian_bundle import debfile
from debian_bundle import deb822

import gitrevision
import processes


class ParsePackageError(Exception):
    """Indicate that a Package file could not be parsed."""

    def __init__(self, value):
        super(ParsePackageError, self).__init__(value)
        self.value = value

    def __str__(self):
        consequence = ("An error occured when parsing controlfields:\n%s" %
                                                                (self.value))
        return consequence


class DebControl:
    """Class to extract and parse debian control fields.
    From debian package or repository.
    Read debian control file or files from `source`.
    The `source` can be either a url or a file path.

    If a http url is used as `source` it is assumed
    that a Packagefile is the source.

    If a filepath is used as `source` it is assumed
    that a debianfile is the source.

    Raise urllib2.HTTPError on unexpected server response.
    Raise IOError if there was a problem extracting Debian file.
    """

    SEMC_FIELDS = ['XB-SEMC-APK-Signature-Type',
                   'XB-SEMC-APK-Signature-Aliases',
                   'XB-SEMC-APK-Requires-Resigning',
                   'XB-SEMC-Component-Git-Version',
                   'XB-SEMC-Component-Git-Path',
                   'XB-SEMC-Component-Git-URL',
                   'XB-SEMC-Component-Version',
                   'XB-SEMC-Component-SDK-ID',
                   'XB-SEMC-Component-SDK-Version',
                   'XB-SEMC-Part-ID',
                   'XB-SEMC-Included-Part-ID']

    def __init__(self, source):
        """Filename or URL and control field resource.
        Raise urllib2.HTTPError on unexpected server response."""
        if source.startswith("http://") or source.startswith("https://"):
            self.url = source
            self.data = str()
            self.useragent = [('User-agent',
                               'debrevisions.py/AswCM')]
            try:
                self.fetch()
            except urllib2.HTTPError, err:
                # Try again
                self.fetch()

            self.controlfiles = self.parse_packages_file()
        else:
            self.filename = source
            self.controlfile = self.parse_control_field_deb()
            self.controlkeylist = self.controlfile.keys()

    def fetch(self):
        """Download HTTP url store self.data as file.
        Raise urllib2.HTTPError on unexpected server response"""
        opener = urllib2.build_opener()
        opener.addheaders = self.useragent
        self.data = opener.open(self.url)

    def parse_packages_file(self):
        """Parse debian dist Packages file"""
        packagelist = list()
        try:
            for pkg in deb822.Packages.iter_paragraphs(self.data):
                controldict = dict()
                for key in pkg.keys():
                    controldict[key] = pkg[key]
                packagelist.append(controldict)
                if not packagelist:
                    raise ParsePackageError("%s\n..." % (self.data[0:79:1]))
            return packagelist
        except (ValueError, EOFError), err:
            raise ParsePackageError("%s" % self.url)

    def parse_control_field_deb(self):
        """Control field parser,
        return dict with control field of filename."""
        try:
            deb = debfile.DebFile(self.filename)
            return deb.debcontrol()
        except (debfile.DebError), err:
            raise ParsePackageError("%s" % (self.filename))

    def __str__(self):
        """Store current control field"""
        return self.controlfile


class TempStore():
    """Class to create a temporary directory and keep track of its name.

    Raise IOError if there is a problem creating or removing
    the temporary directory.
    """

    def __init__(self):
        self.name = tempfile.mkdtemp()

    def destroy(self):
        """Removes temporary directory"""
        try:
            shutil.rmtree(self.name, ignore_errors=True)
        except EnvironmentError:
            # Temp file deletion error
            pass


def parse_xml_package(xmlfile,
                      tag="package",
                      attributes=["name", "revision"],
                      parentinheritancetag="package-group",
                      _whine="always"):
    """
    Read XML file from `xmlfile`.

    Search the DOM tree for all elements named `tag`.
    From each element found, extract the `attributes`
    listed in `attributes` list and put them in a dictionary.
    If `attributes` is not found, the parent tag attributes
    will be inherited if the tag name is `parentinheritancetag`.
    Return a (possibly empty) list of such dictionaries.

    Application::

        A "package list file" is an XML document containing
        elements with the attributes: name and revision.
        The hierarchy in the XML file can contain a parent tag
        named package-group having a general attribute for
        revision of a group of packages.

        An application of this function is to return and list
        these "package list files" in one structure.

    Example::

        xmlfile contents: <root><package name='pak1' revision='4.5'/>
                          <package name='pak2' revision='1.4' /></root>

        data = parse_xml_package(xmlfile)
        data == [{'name': 'pak1', 'revision': '4.5'},
                 {'name': 'pak2', 'revision': '1.4'}]

    Print UserWarning if attribute or value is not found in tag.
    """
    warnings.simplefilter(_whine, UserWarning)
    couples = list()
    couple = dict()
    packagedom = xml.dom.minidom.parse(xmlfile)
    for element in packagedom.getElementsByTagName(tag):
        for attribute in attributes:
            try:
                value = element.attributes[attribute].nodeValue \
                                                  .encode('utf-8')
            except KeyError:
                # Try to inherit an attribute from parent
                parent = element.parentNode
                if parent.tagName == parentinheritancetag:
                    try:
                        value = parent.getAttribute(attribute) \
                                                .encode('utf-8')
                    except KeyError:
                        couple.clear()
                        continue
                else:
                    couple.clear()
                    warnings.warn("Can't find attribute %s in %s" %
                            (attribute, element.toxml(encoding="utf-8")))
                    continue
            # Attribute exists but has no value.
            if not value:
                couple.clear()
                warnings.warn("The attribute %s has no value in %s" %
                            (attribute, element.toxml(encoding="utf-8")))
                continue

            couple[attribute] = value
        if couple:
            couples.append(couple)
        couple = dict()
    return couples


def fetch_package(label, packagename, path):
    """Fetch `packagename` by the version of `label`
    from repository to `path`.
    return deb filepath as a string.

    Raise processes.ChildRuntimeError if execution fails.
    """

    output = processes.run_cmd("repository",
                              "getpackage",
                              "-o", path,
                              packagename,
                              label)

    fullname = output[1].strip()
    return fullname


def run_repository_list(label):
    """Fetch all packages for `label`,
    return package names and versions as a dict.
    fetch_all("label") -> {"packagename": "version"}

    Raises processes.ChildRuntimeError if execution fails
    """
    args = ["repository", "list", label]
    output = processes.run_cmd(args)
    outputstring = output[1].strip()

    manifestdict = {}
    for row in outputstring.splitlines():
        fields = row.split()
        if len(fields) == 2:
            manifestdict[fields[0]] = fields[1]

    return manifestdict


def get_log(workdir, url, gitpath, version):
    """
    Clone a git into `workdir`/`gitpath`/`version` from `url`
    Return list of dicts with a git shortlog of workspace.

    Raise gitrevision.GitError if there was a problem fetching git.
    """
    mygit = gitrevision.GitWorkspace(url, version, gitpath, workdir)
    mygit.clone()
    return mygit.log()


def _test(tmp):
    """Testcases for debrevision
    The aim of this internal test case is to see that
    all functionality of debrevision works as intended.
    It does not handle: Negative test cases
                        User Input
                        Consistent work flow (from a...z).
    How ever it may serve as (an extended and ugly) example
    of how to use debrevision and gitrevision.
    """

    # TODO Create class to convert all output to XML
    # Other packagelist "/vendor/semc/build/composition-config/variant_specs/"

    release = "4.0.A.2.279"
    print "Running revision list for: ", release
    repodict = run_repository_list(release)

    print "Getting external packages git"
    url = "git://review.sonyericsson.net/semctools/external-packages"
    gitpath = "/platform/vendor/semc/build/external-packages"
    branchversion = "ginger-dev"
    extpackfilelist = gitrevision.list_git_files(tmp,
                                                 url,
                                                 branchversion,
                                                 ".xml",
                                                 gitpath,
                                                 ["package-files/"])
    extpacklist = list()
    for filepath in extpackfilelist:
        extpack = parse_xml_package(filepath)
        extpacklist.extend(extpack)

    extpackdict = dict()
    for namerev in extpacklist:
        extpackdict[namerev["name"]] = namerev["revision"]

    url = "http://androidswrepo.sonyericsson.net/dists/" \
          + release + "/semc/binary-arm/Packages"
    print "Getting repository package list for release"
    try:
        repocontrol = DebControl(url)
    except urllib2.HTTPError:
        repocontrol = str()
    gitkeys = ["XB-SEMC-Component-Git-URL",
               "XB-SEMC-Component-Git-Version",
               "XB-SEMC-Component-Git-Path"]

    #packages = extpackdict
    packages = repodict
    PackRev = collections.namedtuple('PackRev', 'package version')
    datastore = {PackRev(package="test", version="1000"): {
                    "release": "rel",
                    "since": "version",
                    "searchtime": "ctime",
                    "control": ["maintainter", "stuff"],
                    "log": ["oj", "mer"]
                    }
                }
    for package in packages.keys():
        revision = packages[package]
        packrev = PackRev(package=package, version=revision)

        datastore[packrev] = dict()

        pkgtmp = os.path.join(tmp, package)
        for control in repocontrol.controlfiles:
            if (package == control['Package'] and
                revision == control['Version']):
                datastore[packrev].update({"control": control})

        if not all(key in control.keys() for key in gitkeys):
            print "Getting deb", package, revision
            try:
                myfind = fetch_package(revision, package, pkgtmp)
                mydeb = DebControl(myfind)
                control = mydeb.controlfile
                datastore[packrev].update({"control": control})
            except processes.ChildRuntimeError:
                print "Failed to fetch: %s %s" % (package, revision)
                continue
            except IOError, err:
                print err
                continue
        try:
            if all(key in mydeb.controlfile.keys() for key in gitkeys):
                url = mydeb.controlfile["XB-SEMC-Component-Git-URL"]
                version = mydeb.controlfile["XB-SEMC-Component-Git-Version"]
                gitpath = mydeb.controlfile["XB-SEMC-Component-Git-Path"]
                log = get_log(pkgtmp, url, gitpath, version)
                datastore[packrev].update({"log": log})
                print datastore[packrev]
        except KeyError:
            pass

if len(sys.argv) > 1:
    if __name__ == "__main__":
        TMPSTORAGE = TempStore()
        TMPDIR = TMPSTORAGE.name
        try:
            print "Sources:", TMPDIR
            _test(TMPDIR)
        except KeyboardInterrupt:
            print " Quitting!"
        finally:
            TMPSTORAGE.destroy()
