import os
import sys


def fatal(exitcode, message):
    """Prints an error message and does sys.exit with exitcode.

    Small helper method to correctly print an error message
    and exit the program with an exitcode.
    """
    print >> sys.stderr, "%s: %s" % (os.path.basename(sys.argv[0]), message)
    # Shouldn't really be necessary as the stderr stream should be unbuffered.
    sys.stderr.flush()
    sys.exit(exitcode)
