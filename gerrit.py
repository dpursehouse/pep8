"""The gerrit module contains classes and functions to interact with
the Gerrit Code Review software.
"""

import sys
import urllib

import processes

GERRIT_SSH_INFO_URL_TEMPLATE = "http://%s/ssh_info"


class GerritSshConfigError(Exception):
    """GerritSshConfigError exceptions indicate that the SSH
    configuration of the Gerrit server couldn't be determined. This
    can happen if the HTTP resource Gerrit uses to announce the
    configuration is unavailable for whatever reason, or if the
    response string didn't match what was expected.
    """


class GerritSshConnection():
    """The GerritSshConnection class gives access to the SSH interface
    of Gerrit Code Review, making it easy to e.g. review changes.
    """

    def __init__(self, hostname, username=None):
        """Initializes a GerritSshConnection object to the server
        identified by `hostname`. The actual hostname and port used
        for the connection will be picked up from the configuration
        URL.

        Will logon to the server as the user specified by
        `username`. If `username` is None, the localpart of the user's
        email address according to the Git configuration (user.email
        variable) will be used as default. If the contents of the
        user.email variable can't be obtained or if the variable's
        value is obviously malformed, no username will be specified
        when logging on to the Gerrit server with SSH. In this case
        SSH will default to $LOGNAME or use the username specified in
        the SSH client configuration (~/.ssh/config etc).

        May throw a GerritSshConfigError exception if the SSH
        configuration of the target Gerrit server can't be determined.
        """

        self.hostname = hostname
        if username:
            self.username = username
        else:
            self.username = None
            try:
                exitcode, out, err = processes.run_cmd("git", "config",
                                                       "user.email")
                # Extract localpart and domain from the first line of the
                # stdout stream. This will fail if the stream is empty or
                # isn't a reasonably-looking email address. "git config"
                # will strip leading and trailing whitespace for us.
                localpart, domain = out.splitlines()[0].split("@")
                if len(localpart):
                    self.username = localpart
            except (processes.ChildExecutionError, IndexError, ValueError):
                # Ignore and default to self.username = None
                pass

        # Fetch the Gerrit configuration URL to obtain the hostname
        # and port to use for SSH connections.
        config_url = GERRIT_SSH_INFO_URL_TEMPLATE % self.hostname
        try:
            sshinfo_response = urllib.urlopen(config_url)
            if sshinfo_response.getcode() == 200:
                host, port = sshinfo_response.readline().split(" ", 1)
                self.ssh_hostname = host
                self.ssh_port = int(port)
            else:
                raise GerritSshConfigError("Request to fetch '%s' returned "
                                           "status code %d." %
                                           (config_url,
                                            sshinfo_response.getcode()))
        except IOError, err:
            raise GerritSshConfigError("Error occured when fetching '%s' "
                                       "to determine the Gerrit "
                                       "configuration: %s" %
                                       (config_url, err.strerror))
        except ValueError, err:
            raise GerritSshConfigError("Gerrit's configuration URL '%s' "
                                       "contained unexpected data." %
                                       config_url)

    def escape_string(self, string):
        """Adds necessary escapes and surrounding double quotes to a
        string so that it can be passed to any of the Gerrit commands
        that require double-quoted strings.
        """

        result = string
        result = result.replace('\\', '\\\\')
        result = result.replace('"', '\\"')
        return '"' + result + '"'

    def get_patchset_id(self, commit_sha1=None, change_nr=None,
                        patchset=None):
        """Returns a string ID describing a particular patch set of a
        Gerrit change. Such a string can be passed to Gerrit commands
        that require patch set identifiers.

        Gerrit supports identification of a patch set to e.g. comment
        or score either by the SHA-1 of the commit or by its (change
        number, patch set number) tuple. This function will use the
        three arguments passed and return a suitable string ID based
        on them. Either `commit_sha1` or `change_nr` and `patchset`
        must be set, the latter two to integers. If the information
        passed isn't enough to unambiguously compute a patch set ID,
        a ValueError exception will be thrown.
        """

        if commit_sha1 and not change_nr and not patchset:
            return commit_sha1
        elif not commit_sha1 and change_nr and patchset:
            return "%d,%d" % (change_nr, patchset)
        else:
            raise ValueError("%s.%s(): Either commit_sha1 or change_nr "
                             "and patchset must be supplied." %
                             (self.__class__.__name__,
                              sys._getframe().f_code.co_name))

    def review_patchset(self, commit_sha1=None, change_nr=None,
                        patchset=None, message=None, codereview=None,
                        verified=None):
        """Reviews a given Gerrit patch set by adding notes and/or
        scoring the patch set.

           commit_sha1 - The commit SHA-1 of the change to be reviewed.
                         Mutually exclusive with change_nr and patchset.
           change_nr   - The integer change number of the change to be
                         reviewed. Mutually exclusive with commit_sha1.
           patchset    - The integer patch set number to review. This
                         argument is only valid if the commit_id is a
                         change number. If it's a SHA-1 the patch set
                         number is given implicitly.
           message     - A text to attach to the review as a note.
           codereview  - The score to give in the Code Review category,
                         or None if that category shouldn't be scored by
                         this call.
           verified    - The score to give in the Verified category,
                         or None if that category shouldn't be scored by
                         this call.

        The patchset to comment on must be identified by setting
        either `commit_sha1` or `change_nr` and `patchset`. Failure
        to do this will result in a ValueError exception being thrown.

        If the command execution fails, a ChildExecutionError
        exception (or a subclass thereof) will be thrown.

        Returns a tuple containing the stdout and stderr output
        streams as strings, although Gerrit at the moment doesn't
        return any output for reviewing patch sets in this manner.
        """

        args = ["review", self.get_patchset_id(commit_sha1=commit_sha1,
                                               change_nr=change_nr,
                                               patchset=patchset)]

        if message is not None:
            args += ["--message", self.escape_string(message)]

        if codereview is not None:
            args += ["--code-review", str(codereview)]

        if verified is not None:
            args += ["--verified", str(verified)]

        return self.run_gerrit_command(args)

    def run_gerrit_command(self, args):
        """Connects to the Gerrit server and runs the command whose
        arguments are found in the `args` list of strings. The initial
        "gerrit" command is implied, i.e. the first element of `args`
        should be the first argument to pass to Gerrit. Returns a
        tuple containing the stdout and stderr streams as strings.

        If the command execution fails, a ChildExecutionError
        exception (or a subclass thereof) will be thrown.
        """

        command = ["ssh", "-p", str(self.ssh_port)]
        if self.username:
            command += ["-l", self.username]
        command += [self.ssh_hostname, "gerrit"]
        command += args
        exitcode, out, err = processes.run_cmd(command)
        return out, err
