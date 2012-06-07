#!/usr/bin/env python

from snapshot import Snapshot

import glob
from optparse import OptionParser
import os
import sys


def report(oldSnap, newSnap):
    """Prints a report of changes made to the package list
    """
    (added, removed, replaced) = newSnap.diff(oldSnap)
    print("Added packages:")
    for pName in added.keys():
        print "  %s:\t%s" % (pName, added[pName])
    print("Updated packages:")
    for pName in replaced.keys():
        print "  %s:\t%s\t%s" % (pName, replaced[pName][0], replaced[pName][1])
    print("Removed packages:")
    for pName in removed.keys():
        print "  %s:\t%s" % (pName, removed[pName])


def main(argv=None):
    if argv is None:
        argv = sys.argv

    parser = OptionParser()
    parser.add_option("-c", "--copy", dest="copy", help="Snapshot to copy")
    parser.add_option("-n", "--name", dest="name", help="New snapshot name")
    parser.add_option("-a", "--add", action="append", dest="add_packages",
                      help="Packages to add. Enter with <name>:<revision>")
    parser.add_option("-d", "--dir", action="append", dest='package_dir',
                        help="Directories containing package files")
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
    orgSnap = Snapshot()
    addedPacks = {}
    updatedPacks = {}
    removedPacks = {}

    if options.server:
        snap.server = options.server
        orgSnap.server = options.server

    if options.copy:
        try:
            snap.copy_snapshot(options.copy)
            orgSnap.copy_snapshot(options.copy)
        except processes.ChildExecutionError, e:
            print >> sys.stderr, "Could not get packages\
                                  for snapshot %s: %s" % (options.copy, e)
            return(1)

    if options.name:
        snap.name = options.name

    if options.package_dir:
        for package_dir in options.package_dir:
            for package_file in glob.glob(os.path.join(
                package_dir, '*.xml')):
                snap.add_from_file(package_file)

    if options.add_packages:
        for item in options.add_packages:
            if item.endswith(".xml") and os.path.exists(item):
                snap.add_from_file(item)

            else:
                snap.add_package(item.split(':'))

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
        report(orgSnap, snap)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
