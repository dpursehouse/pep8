import subprocess
import sys
import os
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError

class ChildExecutionError(Exception):
    """Superclass for the various types of errors that can occur when
    running child processes.
    """

    def __init__(self, command):
        if isinstance(command, list):
            self.command = " ".join(command)
        else:
            self.command = command

class ChildRuntimeError(ChildExecutionError):
    """Raised when a child process has died with a non-zero exit
    status, and this case is considered exceptional.
    """

    def __init__(self, command, result):
        super(ChildRuntimeError, self).__init__(command)
        self.result = result

    def __str__(self):
        return 'Command exited with status %d: %s\nError message: %s' \
                % (self.result[0], self.command, self.result[2])

class ChildSignalledError(ChildExecutionError):
    """Raised when a child process dies of a signal.
    """

    def __init__(self, command, result):
        super(ChildSignalledError, self).__init__(command)
        self.result = result

    def __str__(self):
        return 'Command killed by signal %d: %s' % (-self.result[0],
                                                    self.command)

class ChildStartupError(ChildExecutionError):
    """Raised when a child process couldn't be started at all,
    typically because the process fork failed or because the
    program executable couldn't be found.
    """

    def __init__(self, command, enverror):
        super(ChildStartupError, self).__init__(command)
        self.enverror = enverror

    def __str__(self):
        return 'Error running command (%s): %s' % (self.enverror.strerror,
                                                   self.command)

def run_cmd(*cmdandargs, **kwargs):
    """Runs a command, returns result.

    This function can be used in the following ways:

    run_cmd(list) -> Runs the command (with arguments) in list.
    run_cmd(cmd, arg1, arg2, ...) -> Runs cmd with the specified arguments.
    run_cmd(list, path=dir) -> Runs the command (with arguments) in list at
        the given path.
    run_cmd(cmd, arg1, arg2, ..., path=dir) -> Runs cmd with the specified
        arguments at the given path.

    Returns a tuple with: the exit status, a string containing stdout
    and a string containing stderr. Throws some version of
    ChildExecutionError if it encountered an error.
    """

    if isinstance(cmdandargs[0], list):
        cmdandargs = cmdandargs[0]
    cmddesc = ' '.join(cmdandargs)

    popenkwargs = {"stdout": subprocess.PIPE,
                   "stderr": subprocess.PIPE}

    if "path" in kwargs:
        popenkwargs["cwd"] = kwargs["path"]
        cmddesc += " (In directory: %s)" % kwargs["path"]

    try:
        p = subprocess.Popen(cmdandargs, **popenkwargs)
        stdout, stderr = p.communicate()
        result = (p.returncode, stdout, stderr)
        if p.returncode == 0:
            return result
        elif p.returncode < 0:
            raise ChildSignalledError(cmddesc, result)
        else:
            raise ChildRuntimeError(cmddesc, result)
    except EnvironmentError, e:
        raise ChildStartupError(cmddesc, e)

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
                raise ManifestParseError("Project without name attribute found.")

            if proj.hasAttribute("path"):
                data["path"] = proj.attributes["path"].nodeValue
            else:
                data["path"] = name

            if proj.hasAttribute("revision"):
                data["revision"] = proj.attributes["revision"].nodeValue
            else:
                data["revision"] = self.default_rev
            self.projects[name] = data
