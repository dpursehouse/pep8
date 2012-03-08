#!/usr/bin/env python

import json
import optparse
import os
import os.path
import re
from string import rstrip
import sys
import urllib2

import gerrit
import manifest
import processes
import semcutil


class CherrypickError(Exception):
    '''CherrypickError is raised when the cherry pick
    fails for some reason.
    '''


class GerritCherrypickLatest(object):
    '''Class to cherry pick the latest patch set from a given
    change number.
    '''

    def __init__(self, server, manifest_projects, workspace):
        '''Initializes the class with the Gerrit server, list of
        manifest projects and workspace.
        '''
        self.server = server
        self.manifest_projects = manifest_projects
        self.workspace = workspace

    def get_latest_patchset(self, changenr):
        '''Gets the latest patch set information for `changenr`.
        Returns: tuple of project name and refspec
        '''
        cmdargs = ["query", "change:%s" % (changenr), "--format", "JSON",
            "--current-patch-set"]
        try:
            o, e = self.server.run_gerrit_command(cmdargs)
            for line in o.splitlines():
                try:
                    data = json.loads(line)
                    if "currentPatchSet" in data:
                        return data["project"], data["currentPatchSet"]["ref"]
                except ValueError, e:
                    raise CherrypickError("Invalid JSON data: " + str(e))
                except KeyError, e:
                    raise CherrypickError("Missing JSON key: " + str(e))
        except processes.ChildExecutionError, err:
            raise CherrypickError("Error executing Gerrit query: %s" % (err))

    def gerrit_cherrypick_latest(self, changenr):
        '''Queries Gerrit to find the information for the change specified
        by `changenr` and then attempts to cherry pick the latest patch set.
        The change must be on a project that is listed in the repo manifest.
        '''
        try:
            proj, ref = self.get_latest_patchset(changenr)
        except TypeError:
            raise CherrypickError("Failed to find change %s on %s" % \
                (changenr, self.server.hostname))
        except CherrypickError, err:
            raise CherrypickError("Error finding change %s on %s: %s" % \
                (changenr, self.server.hostname, err))

        if not proj in self.manifest_projects:
            raise CherrypickError("Couldn't find project %s in manifest"
                % (proj))

        path = self.workspace + "/" + self.manifest_projects[proj]["path"]
        fullpath = os.path.abspath(path)
        gitstart = ["git", "--git-dir=%s/.git" % (fullpath),
            "--work-tree=%s" % (fullpath)]

        try:
            cmd = gitstart + ["fetch", "git://%s/%s" %
                    (self.server.hostname, proj), ref]
            processes.run_cmd(cmd)
            cmd = gitstart + ["cherry-pick", "FETCH_HEAD"]
            processes.run_cmd(cmd)
        except processes.ChildExecutionError, e:
            # A lot of the information about errors from Git comes on stdout
            raise CherrypickError(e.result[1].strip() + "\n" +
                    e.result[2].strip())
        print "Change %s in %s cherry-picked OK (ref:%s)" % (change, path, ref)

if __name__ == "__main__":
    usage = "usage: %prog [options] changes..."
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-w", "--workspace", dest="workspace",
        default=os.getcwd(), help="Path to the workspace")
    parser.add_option("-u", "--username", dest="username",
        help="Name to use when logging in at review.sonyericsson.net.")
    (options, args) = parser.parse_args()
    options.workspace = rstrip(options.workspace, "/")

    try:
        if options.username:
            server = gerrit.GerritSshConnection("review.sonyericsson.net", \
                    options.username)
        else:
            server = gerrit.GerritSshConnection("review.sonyericsson.net")
        manifestdata = open(options.workspace + "/.repo/manifest.xml").read()
        mfest = manifest.RepoXmlManifest(manifestdata)
        cherry_picker = GerritCherrypickLatest(server, mfest.projects,
            options.workspace)
        failcount = 0
        for change in args:
            try:
                # The change must be a decimal number
                change_nr = int(change, 10)
            except:
                print >> sys.stderr, "Change %s failed: Invalid change ID" % \
                    (change)
                failcount += 1
                continue
            try:
                cherry_picker.gerrit_cherrypick_latest(change)
            except CherrypickError, err:
                print >> sys.stderr, "Change %s failed:" % (change), err
                failcount += 1
        sys.exit(failcount)
    except gerrit.GerritSshConfigError, e:
        semcutil.fatal(1, "Gerrit SSH config error: %s" % (str(e)))
    except manifest.ManifestParseError, e:
        semcutil.fatal(1, "Manifest error: %s" % (str(e)))
    except EnvironmentError, e:
        semcutil.fatal(1, "Environment error: %s" % (str(e)))
