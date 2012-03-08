#!/usr/bin/env python

import processes
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET


class Snapshot(object):

    def __init__(self, from_snapshot=None, from_file=None, name=None):
        self.packages = {}
        # key = package name, value = (old version, new version) tuple.
        self.server = None
        self.tempDir = tempfile.mkdtemp()

        if from_snapshot:
            self.copy_snapshot(snapshot)
        if from_file:
            self.add_from_file(from_file)
        self.name = name

    def __del__(self):
        """Destructor. Removes the temporary directory created in the
           constructor
        """
        shutil.rmtree(self.tempDir, ignore_errors=True)

    def copy_snapshot(self, snap):
        """Runs repository list <snap> and puts the
           packages/version pairs as key/value pairs
           into a packages dictionary instance variable"""

        cmd = self._repository_cmd()
        cmd.extend(['list', snap])

        (retval, stdout, stderr) = processes.run_cmd(cmd)
        for line in stdout.split("\n"):
            try:
                (name, version) = line.split(None, 1)
            except ValueError, e:
                continue
            name = name.strip()
            version = version.strip()
            self.packages[name] = version

    def add_package(self, package, replace=True):
        """Takes a package name/version tuple and adds to
           the packages dictionary instance variable.
           Returns one dict with all new packages and one with all
           replaced packages
        """
        # TODO: Add version control to see whether the package exists and so,
        #       we are trying to set an older version than the current one. If
        #       so, print a warning in the log
        replaced = {}
        newp = {}
        cmd = self._repository_cmd()
        cmd.extend(['getpackage', package[0], package[1],
                    "--out=%s" % self.tempDir])
        try:
            (res, ret, err) = processes.run_cmd(cmd)
            if res == 0:
                if package[0] in self.packages:
                    if self.packages[package[0]] != package[1]:
                        replaced[package[0]] = (self.packages[package[0]],
                                                 package[1])
                else:
                    newp[package[0]] = package[1]
                self.packages[package[0]] = package[1]
            else:
                print >> sys.stderr, err
        except processes.ChildExecutionError, e:
            print >> sys.stderr, "Could not find package %s, rev %s in the " \
            "repository: %s " % (package[0], package[1], e)
        return (newp, replaced)

    def remove_package(self, packageName):
        """ Deletes the package from the package dict if it is present.
            Returns a dict with all removed packages
        """
        removed = {}
        try:
            removed[packageName] = self.packages.pop(packageName)
        except KeyError:
            pass
        return removed

    def create_label(self, name=None):
        """Emits a package list (xml) and uses this to promote the packages
           to the snapshot with name <name>.
        """
        if name == None:
            name = self.name
        cmd = self._repository_cmd()
        cmd.extend(['createlabel', name])
        (res, ret, err) = processes.run_cmd(cmd)

    def add_from_file(self, package_file):
        """Takes a package list xml file as imput and
           adds the listed packages to the package list
           Returns one dict with the new packages and one with the updated ones
        """
        newPacks = {}
        replacedPacks = {}
        tags = ET.parse(package_file)
        for package in tags.findall("package"):
            (newp, replp) = self.add_package([package.attrib["name"],
                                              package.attrib["revision"]])
            newPacks.update(newp)
            replacedPacks.update(replp)
        for packageGroup in tags.findall("package-group"):
            for package in packageGroup.findall("package"):
                if "revision" in package.attrib:
                    (newp, replp) = \
                    self.add_package([package.attrib["name"],
                                      package.attrib["revision"]])
                    newPacks.update(newp)
                    replacedPacks.update(replp)
                else:
                    (newp, replp) = \
                    self.add_package([package.attrib["name"],
                                      packageGroup.attrib["revision"]])
                    newPacks.update(newp)
                    replacedPacks.update(replp)
        return(newPacks, replacedPacks)

    def remove_from_file(self, package_file):
        """Takes a package list xml file as input and removes
           the listed packages from the package list.
           Returns a dict of the removed packages
        """
        rmPacks = {}
        tags = ET.parse(package_file)
        for package in tags.findall("package"):
            rmPacks.update(self.remove_package(package.attrib("name")))
        return rmPacks

    def filter_packages(self, package_filter):
        filter_exp = re.compile(package_filter)
        for package in self.packages.keys():
            if filter_exp.match(package):
                self.remove_package(package)

    def set_name(self, name):
        """Sets the snapshot name
        """
        self.name = name

    def emit_package_file(self, path=None):
        """Emits a package file to <path> stream or stdout
        """
        if path == None:
            path = sys.stdout

        print >> path, "<packages>"
        for (name, version) in self.packages.iteritems():
            print >> path, "\t<package name=\"%s\" revision=\"%s\" />" % \
                            (name, version)
        print >> path, "</packages>"

    def promote_from_file(self, name=None, path=None):
        """Promotes packages from package list in path to label named <name>
        """
        if name == None:
            name = self.name
        if path == None:
            path = tempfile.NamedTemporaryFile(suffix='.xml', delete=False)
            self.emit_package_file(path)
            path.close()
        cmd = self._repository_cmd()
        cmd.extend(['promotefromfile', path.name, "--label=%s" % name])
        (res, ret, err) = processes.run_cmd(cmd)

    def diff(self, otherSnapshot):
        """Compares this snapshot with oldSnapshot.
           Returns one dict with new packages, one with removed packages and
           one with updated packages"""
        inCurrent = {}
        inBoth = {}
        inOther = {}

        curKeys = set(self.packages.keys())
        otherKeys = set(otherSnapshot.packages.keys())

        for packName in curKeys.intersection(otherKeys):
            if self.packages[packName] != otherSnapshot.packages[packName]:
                inBoth[packName] = [otherSnapshot.packages[packName],
                                      self.packages[packName]]
        for packName in curKeys.difference(otherKeys):
            inCurrent[packName] = self.packages[packName]
        for packName in otherKeys.difference(curKeys):
            inOther[packName] = otherSnapshot.packages[packName]

        return(inCurrent, inOther, inBoth)

    def _repository_cmd(self):
        if self.server == None:
            return ['repository']
        else:
            return ['repository', '-ru', self.server]


def main(argv=None):
    pass

if __name__ == "__main__":
    sys.exit(main(sys.argv))
