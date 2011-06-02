import os
import sys
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError


def fatal(exitcode, message):
    """Prints an error message and does sys.exit with exitcode.

    Small helper method to correctly print an error message
    and exit the program with an exitcode.
    """
    print >> sys.stderr, "%s: %s" % (os.path.basename(sys.argv[0]), message)
    # Shouldn't really be necessary as the stderr stream should be unbuffered.
    sys.stderr.flush()
    sys.exit(exitcode)


class ManifestParseError(Exception):
    """Raised when there is a problem opening, parsing or
    extracting info from a repo manifest.
    """
    def __init__(self, problem):
        self.problem = problem

    def __str__(self):
        return "Failed to parse manifest: %s" % (self.problem)


class RepoXmlManifest():
    """Returns an object with the info from a repo manifest.

    Takes the path to a manifest as input. The object returned contains:

    projects: a dict with project name as key and another dict
    with info for each project. This dict always contains the keys "path",
    "revision" and "name".
    default_rev: the default revision as specified in the manifest.
    Throws ManifestParseError on all kinds of errors.
    """
    def __init__(self, manifestdata):
        self.manifestdata = manifestdata
        self.projects = {}
        self.default_rev = None

        self._parse_manifest()

    def _parse_manifest(self):
        try:
            domtree = parseString(self.manifestdata)
        except ExpatError, e:
            raise ManifestParseError(str(e))

        default = domtree.getElementsByTagName("default")
        if default and len(default) == 1:
            if default[0].hasAttribute("revision"):
                self.default_rev = default[0].attributes["revision"].nodeValue
            else:
                raise ManifestParseError("Missing revision attribute on the "
                        "default tag.")
        elif len(default) > 1:
            raise ManifestParseError("Many default tags not allowed.")
        else:
            raise ManifestParseError("Missing default tag.")

        for proj in domtree.getElementsByTagName("project"):
            data = {}
            if proj.hasAttribute("name"):
                name = proj.attributes["name"].nodeValue
                data["name"] = name
            else:
                raise ManifestParseError("Project without name attribute "
                        "found.")

            if proj.hasAttribute("path"):
                data["path"] = proj.attributes["path"].nodeValue
            else:
                data["path"] = name

            if proj.hasAttribute("revision"):
                data["revision"] = proj.attributes["revision"].nodeValue
            else:
                data["revision"] = self.default_rev
            self.projects[name] = data
