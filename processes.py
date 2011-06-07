import os
import subprocess
import sys


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

    if "input" in kwargs:
        popenkwargs["stdin"] = subprocess.PIPE

    try:
        p = subprocess.Popen(cmdandargs, **popenkwargs)
        if "input" in kwargs:
            stdout, stderr = p.communicate(input=kwargs["input"])
        else:
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
