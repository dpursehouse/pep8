import subprocess
import sys
import os

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
def run_cmd(*cmdandargs):
    """Runs a command, returns result.

    Takes either a list with arguments or any number of arguments.
    Returns a tuple with the exit status, a string containing stdout
    and a string containing stderr. Throws a some version of
    ChildExecutionError if it encountered an error."""
    if isinstance(cmdandargs[0], list):
        cmdandargs = cmdandargs[0]
    try:
        p = subprocess.Popen(cmdandargs, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        result = (p.returncode, stdout, stderr)
        if p.returncode == 0:
            return result
        elif p.returncode < 0:
            raise ChildSignalledError(' '.join(cmdandargs), result)
        else:
            raise ChildRuntimeError(' '.join(cmdandargs), result)
    except EnvironmentError, e:
        raise ChildStartupError(' '.join(cmdandargs), e)

def fatal(exitcode, message):
    print >> sys.stderr, "%s: %s" % (os.path.basename(sys.argv[0]), message)
    # Shouldn't really be necessary as the stderr stream should be unbuffered.
    sys.stderr.flush()
    sys.exit(exitcode)

