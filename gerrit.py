"""The gerrit module contains classes and functions to interact with
the Gerrit Code Review software.
"""

import json
import sys
import urllib

import processes

GERRIT_SSH_INFO_URL_TEMPLATE = "http://%s/ssh_info"


def escape_string(string):
    """Adds necessary escapes and surrounding double quotes to a
    string so that it can be passed to any of the Gerrit commands
    that require double-quoted strings.
    """

    result = string
    result = result.replace('\\', '\\\\')
    result = result.replace('"', '\\"')
    return '"' + result + '"'


def get_patchset_id(commit_sha1=None, change_nr=None,
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
        raise ValueError("Either commit_sha1 or change_nr "
                         "and patchset must be supplied.")


def get_patchset_refspec(change_nr, patchset):
    """Returns a string representing the patchset refspec for
    the change identified by `change_nr` and `patchset`.
    """
    infix = change_nr % 100
    return "refs/changes/%02d/%d/%d" % (infix, change_nr, patchset)


class GerritQueryError(Exception):
    """GerritQueryError exceptions are raised when Gerrit returns an
    error for a posted query, typically indicating a syntax error in
    the query string.
    """


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
        self.username = username
        if not self.username:
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

    def query(self, querystring):
        """Sends the query `querystring` to Gerrit and returns the
        response as a (possibly empty) list of dictionaries. The keys
        and values of the dictionaries are defined by Gerrit. Throws a
        GerritQueryError exception if Gerrit rejects the query. If the
        command execution itself fails (e.g. because of an SSH-related
        error), a ChildExecutionError exception (or a subclass
        thereof) will be thrown.
        """

        args = ["query", "--current-patch-set", "--all-approvals",
                "--format", "JSON",
                escape_string(querystring)]
        response, err = self.run_gerrit_command(args)

        result = []
        json_decoder = json.JSONDecoder()
        for line in response.splitlines():
            # Gerrit's response to the query command contains one or more
            # lines of JSON-encoded strings.  The last one is a status
            # dictionary containing the key "type" whose value indicates
            # whether or not the operation was successful.
            # According to http://goo.gl/h13HD it should be safe to use the
            # presence of the "type" key to determine whether the dictionary
            # represents a change or if it's the query status indicator.
            data = json_decoder.decode(line)
            if "type" in data:
                if data["type"] == "error":
                    raise GerritQueryError(data["message"])
            else:
                result.append(data)
        return result

    def change_is_open(self, change):
        """ Checks if the change specified by `change` is open.  `change` is
        assumed to be a valid gerrit query string.
        Returns True or False, and the current patch set.
        Raises GerritQueryError if the change was not found, the Gerrit
        query raises more than one result, or the gerrit query fails for
        some other reason.
        """
        results = self.query(change)
        if not len(results):
            raise GerritQueryError("Change not found")
        elif len(results) > 1:
            raise GerritQueryError("Too many results")
        result = results[0]
        if not "status" in result:
            raise GerritQueryError("Status not in query result")
        if not "currentPatchSet" in result:
            raise GerritQueryError("Current patch set not in query result")
        is_open = (result["status"] == "NEW")
        current_patchset = int(result["currentPatchSet"]["number"])
        return is_open, current_patchset

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

        args = ["review", get_patchset_id(commit_sha1=commit_sha1,
                                          change_nr=change_nr,
                                          patchset=patchset)]

        if message is not None:
            args += ["--message", escape_string(message)]

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
