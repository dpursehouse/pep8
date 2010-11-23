#!/usr/bin/env python

import sys
import os
import os.path
import getmanifest
import semcutil
from xml.dom.minidom import parse
import tempfile
import optparse

OK_MESSAGE = "OK"
MISSING_MESSAGE = "Path doesn't exist in workspace"
OFFICIALTAG_MESSAGE = "Won't delete official tags"

class DictList(dict):
    def add(self, key, value):
        if key not in self:
            self[key] = []
        self[key].append(value)

class CheckRunCmd():
    def __init__(self, f):
        self.f = f

    def __call__(self, *args):
        try:
            return self.f(*args)
        except semcutil.ChildRuntimeError, e:
            return e.result[2].strip()
        except semcutil.ChildExecutionError, e:
            # Unknown error occurred!
            return str(e)

@CheckRunCmd
def apply_tag(path, name, revision):
    cmd = ["git", "tag", name, revision]
    r = semcutil.run_cmd(cmd, path=path)
    return OK_MESSAGE

@CheckRunCmd
def delete_tag(path, name):
    # Check tag type
    cmd = ["git", "cat-file", "-t", name]
    r = semcutil.run_cmd(cmd, path=path)
    tagtype = r[1].strip()

    if tagtype != "commit":
        return OFFICIALTAG_MESSAGE

    # Delete it
    cmd = ["git", "tag", "-d", name]
    r = semcutil.run_cmd(cmd, path=path)
    return OK_MESSAGE

def tag_official_release(manifestdata, label, delete=False, verbose=False):
    manifestinfo = semcutil.RepoXmlManifest(manifestdata)
    statuslist = DictList()
    for proj, info in manifestinfo.projects.items():
        if verbose:
            print "Examining %s..." % (proj)

        if os.path.exists(info["path"]):
            if delete:
                message = delete_tag(info["path"], label)
            else:
                message = apply_tag(info["path"], label, info["revision"])

            statuslist.add(message, info["path"])
        else:
            statuslist.add(MISSING_MESSAGE, info["path"])
    return statuslist

def _handle_status(statuslist, label, options):
    okcount = 0
    missingcount = 0
    failcount = 0
    for status, pathlist in statuslist.items():
        if status == OK_MESSAGE:
            okcount += len(pathlist)
        else:
            if status == MISSING_MESSAGE:
                missingcount += len(pathlist)
            else:
                failcount += len(pathlist)

            print status
            for path in sorted(pathlist):
                print "   ", path

    if options.delete:
        operation = "Delete tag"
    else:
        operation = "Tag"
    print "For label %s:" % (label)
    print "%s ok: %i" % (operation, okcount)
    print "%s fail: %i" % (operation, failcount)
    print "Missing path: %i" % (missingcount)

    if failcount > 0 or (options.strict and missingcount > 0):
        return ["%s failed on label %s." % (operation, label)]
    else:
        return []

def _main(argv):
    usage = "usage: %prog [options] LABEL1 [LABEL2...]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-v", "--verbose", dest="verbose", action="store_true",
                        help="Print commands and results")
    parser.add_option("-d", "--delete", dest="delete", action="store_true",
                        help="Delete the tag instead of creating it")
    parser.add_option("-s", "--strict", dest="strict", action="store_true",
                        help="Fail if any command failed")
    parser.add_option("-t", "--type", dest="repo_name",
                        help="Override default repository type, options: "
                        "protected")
    parser.add_option("-r", "--repo_url", dest="repo_url",
                        help="Override default repository url.")
    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.print_help()
        parser.error("You must pass at least one label to this script")

    if options.repo_name and options.repo_url:
        parser.error("You can't supply repo_name and repo_url at the same time.")

    fatal_errors = []

    for label in args:
        manifestpath = tempfile.mkstemp()[1]
        try:
            try:
                if options.verbose:
                    print "Downloading manifest for %s from C2D..." % (label)
                getmanifest.get_manifest(label, manifestpath,
                                         repo_name=options.repo_name,
                                         repo_url=options.repo_url)
                manifestdata = open(manifestpath).read()
            except getmanifest.GetManifestError, e:
                semcutil.fatal(1, "Failed to download manifest: " + str(e))
            except EnvironmentError, e:
                semcutil.fatal(1, "Failed to read manifest: " + str(e))

            try:
                statuslist = tag_official_release(manifestdata, label,
                                               options.delete, options.verbose)
            except semcutil.ManifestParseError, e:
                semcutil.fatal(1, "Failed to parse manifest: " + str(e))

            fatal_errors.extend(_handle_status(statuslist, label, options))
        finally:
            try:
                os.remove(manifestpath)
            except EnvironmentError:
                # Ignore errors when deleting temporary file
                pass

    if len(fatal_errors) > 0:
        for error in fatal_errors:
            print >> sys.stderr, error
        semcutil.fatal(1, "Fatal errors occurred")

if __name__ == "__main__":
    _main(list(sys.argv))
