#!/usr/bin/env python

import sys
import semcutil
import os
import tempfile
import shutil
from optparse import OptionParser

class GetManifestError(Exception):
    def __init__(self, message, error):
        self.message = message
        self.error = error

    def __str__(self):
        return self.message + ":\n" + str(self.error)

def run_or_fail(command, message):
    try:
        r = semcutil.run_cmd(command)
    except semcutil.ChildExecutionError, e:
        raise GetManifestError(message, e)
    return r

def get_package_version(label, package, repo_name=None):
    args = ["repository", "list", label]
    if repo_name:
        if repo_name == "protected":
            args += ["-ru", "ssh://seldlnx045"]
        else:
            raise GetManifestError("Unsupported repository type",
                                   "Repository %s not found" % (repo_name))
    returncode, stdout, stderr = run_or_fail(args, "Failed to list label")
    version = None
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == package:
            version = parts[1]
    if version == None:
        raise GetManifestError("Failed to parse output of 'repository list %s'"
            % (label), "%s package not found" % (package))
    else:
        return version

def get_and_extract_package(label, package, outdir, repo_name=None):
    pversion = get_package_version(label, package, repo_name)
    args = ["repository", "getpackage", "-o", outdir, package, pversion]
    if repo_name:
        if repo_name == "protected":
            args += ["-ru", "ssh://seldlnx045:/srv/protected-repo"]
        else:
            raise GetManifestError("Unsupported repository type",
                                   "Repository %s not found" % (repo_name))
    returncode, stdout, stderr = run_or_fail(args, "Downloading %s from %s \
                                             failed:" % (package, pversion))
    debpath = stdout.strip()

    run_or_fail(["dpkg-deb", "-x", debpath, outdir],
        "Failed to extract package %s to %s:" % (package, outdir))

def get_file_from_package(label, package, outfile, frompath, repo_name=None):
    tempdir = tempfile.mkdtemp()
    try:
        get_and_extract_package(label, package, tempdir, repo_name)
        try:
            shutil.copyfile(os.path.join(tempdir, frompath), outfile)
        except IOError, e:
            raise GetManifestError("Failed to move manifest to %s" % (outfile), e)
    finally:
        shutil.rmtree(tempdir)

def get_manifest(label, outfile="manifest_static.xml",
                 frompath="manifest_static.xml", repo_name=None):
    get_file_from_package(label, "build-metadata", outfile, frompath, repo_name)

def _main(argv):

    usage = "usage: %prog [options] LABEL"
    parser = OptionParser(usage=usage)
    parser.add_option("-p", "--package", dest="package",
                        default="build-metadata",
                        help="A valid Debian package")
    parser.add_option("-o", "--outfile", dest="outfile", default="manifest_static.xml",
                        help="Stores the manifest to this path [default: %default]")
    parser.add_option("-f","--frompath", dest="frompath", default="manifest_static.xml",
                        help="Path where the manifest is found [default: %default]")
    parser.add_option("-t","--type", dest="repo_name",
                        help="Override default repository type. ")
    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        parser.error("Incorrect number of arguments")
    try:
        label = args[0]
        get_file_from_package(label, options.package, options.outfile,
                              options.frompath, options.repo_name)
    except GetManifestError, e:
        print >> sys.stderr, str(e)
        sys.exit(1)

if __name__ == "__main__":
    _main(list(sys.argv))
