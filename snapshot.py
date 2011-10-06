import glob
from optparse import OptionParser
import os
import processes
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET


class Snapshot:

    def __init__(self, from_snapshot=None, from_file=None, name=None):
        self.packages = {}
        # key = package name, value = (old version, new version) tuple.
        self.replaced = {}
        self.removed = {}
        self.new = {}
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
        """
        # TODO: Add version control to see whether the package exists and so,
        #       we are trying to set an older version than the current one. If
        #       so, print a warning in the log
        cmd = self._repository_cmd()
        cmd.extend(['getpackage', package[0], package[1],
                    "--out=%s" % self.tempDir])
        try:
            (res, ret, err) = processes.run_cmd(cmd)
            if res == 0:
                if package[0] in self.packages:
                    self.replaced[package[0]] = (self.packages[package[0]],
                                                 package[1])
                else:
                    self.new[package[0]] = package[1]
                self.packages[package[0]] = package[1]
            else:
                print >> sys.stderr, err
        except processes.ChildExecutionError, e:
            print >> sys.stderr, "Could not find package %s, rev %s in the " \
            "repository: %s " % (package[0], package[1], e)

    def remove_package(self, packageName):
        """ Deletes the package from the package dict if it is present.
        """
        try:
            self.removed[packageName] = self.packages.pop(packageName)
        except KeyError:
            pass

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
        """
        tags = ET.parse(package_file)
        for package in tags.findall("package"):
            self.add_package([package.attrib["name"],
                              package.attrib["revision"]])
        for packageGroup in tags.findall("package-group"):
            for package in packageGroup.findall("package"):
                self.add_package([package.attrib["name"],
                                  packageGroup.attrib["revision"]])

    def remove_from_file(self, package_file):
        """Takes a package list xml file as input and removes
           the listed packages from the package list.
        """
        tags = ET.parse(package_file)
        for package in tags.findall("package"):
            self.remove_package(package.attrib("name"))

    def filter_packages(self, package_filter):
        filter_exp = re.compile(package_filter)
        for package in self.packages.keys():
            if filter_exp.match(package):
                self.remove_package(package)

    def set_name(self, name):
        """Sets the snapshot name
        """
        self.name = name

    def report(self):
        """Prints a report of changes made to the package list
        """
        print("Added packages:")
        print self.new
        print("Updated packages:")
        print self.replaced
        print("Removed packages:")
        print self.removed

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
        """Promotes packages from package list in path to label named <name
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

    def _repository_cmd(self):
        if self.server == None:
            return ['repository']
        else:
            return ['repository', '-ru', self.server]


def main(argv=None):
    if argv == None:
        argv = sys.argv

    parser = OptionParser()
    parser.add_option("-c", "--copy", dest="copy", help="Snapshot to copy")
    parser.add_option("-n", "--name", dest="name", help="New snapshot name")
    parser.add_option("-a", "--add", action="append", dest="add_packages",
                      help="Packages to add")
    parser.add_option("-d", "--dir", dest='package_dir',
                        help="A directory containing package files")
    parser.add_option("-r", "--remove", action="append",
                      dest="remove_packages", help="Packages to remove")
    parser.add_option("-s", "--server", help="Repository server")
    parser.add_option("-p", "--promote",
                        action="store_true",
                        default=False,
                        dest="promote",
                        help="Create snapshot and promote packages")
    parser.add_option("-q", "--quiet", action="store_true", default=False,
                        dest="quiet", help="Suppresses reporting")
    parser.add_option("-f", "--filter", action="append", dest='package_filter',
                        help="Filter package list using provided regexp")

    (options, args) = parser.parse_args()

    snap = Snapshot()

    if options.server:
        snap.server = options.server

    if options.copy:
        try:
            snap.copy_snapshot(options.copy)
        except processes.ChildExecutionError, e:
            print >> sys.stderr, "Could not get packages\
                                  for snapshot %s: %s" % (options.copy, e)
            return(1)

    if options.name:
        snap.name = options.name

    if options.add_packages:
        for item in options.add_packages:
            if item.endswith(".xml") and os.path.exists(item):
                snap.add_from_file(item)
            else:
                snap.add_package(item.split())
    if options.package_dir:
        for package_file in glob.glob(os.path.join(
            options.package_dir, '*.xml')):
            snap.add_from_file(package_file)
    if options.remove_packages:
        for item in options.remove_packages:
            if item.endswith(".xml") and os.path.exists(item):
                snap.remove_from_file(item)
            else:
                snap.remove_package(item)
    if options.package_filter:
        for f in options.package_filter:
            snap.filter_packages(f)
    if options.promote:
        snap.promote_from_file()
    else:
        snap.emit_package_file()
    if not options.quiet:
        snap.report()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
