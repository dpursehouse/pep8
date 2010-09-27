#!/usr/bin/env python

import sys
import semcutil
import os
import tempfile
import shutil

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

def get_package_version(label, package):
    returncode, stdout, stderr = run_or_fail(["repository", "list", label],
        "Failed to list label")
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

def get_and_extract_package(label, package, outdir):
    pversion = get_package_version(label, package)
    returncode, stdout, stderr = run_or_fail(["repository", "getpackage", "-o", outdir, package, pversion],
        "Downloading %s from %s failed:" % (package, pversion))

    debpath = stdout.strip()

    run_or_fail(["dpkg-deb", "-x", debpath, outdir],
        "Failed to extract package %s to %s:" % (package, outdir))

def get_file_from_package(label, package, topath, frompath):
    tempdir = tempfile.mkdtemp()
    try:
        get_and_extract_package(label, package, tempdir)
        try:
            shutil.copyfile(os.path.join(tempdir, frompath), topath)
        except IOError, e:
            raise GetManifestError("Failed to move manifest to %s" % (topath), e)
    finally:
        shutil.rmtree(tempdir)

def get_manifest(label, topath = "manifest_static.xml", frompath = "manifest_static.xml"):
    get_file_from_package(label, "build-metadata", topath, frompath )

def _usage():
    myname = os.path.basename(sys.argv[0])
    usagestr = """%s LABEL [ SAVEPATH ] [ FROMPATH ]
    Downloads a manifest from a specific LABEL and stores it at
    SAVEPATH.
    FROMPATH default is "manifest_static.xml"
    (NOTE! Doesn't support protected repository until
    SWD Tools supports "repository list" with that.)""" % (myname)
    print >> sys.stderr, usagestr

def _main(argv):
    if len(argv) < 2 or len(argv) > 4:
        _usage()
        sys.exit(1)
    try:
        get_manifest(*argv[1:])
    except GetManifestError, e:
        print >> sys.stderr, str(e)
        sys.exit(1)

if __name__ == "__main__":
    _main(list(sys.argv))
