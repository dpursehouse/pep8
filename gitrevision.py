#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Module for executing git commands.
Depends on processes."""

import errno
import os
import warnings

import processes

GIT_EXITCODE_ENV_ERROR = 128
GIT_EXITCODE_NETWORK_ERROR = 22


class GitError(Exception):
    """Superclass of gitrevision that occurs when executing a git command."""

    def __init__(self, value):
        if isinstance(value, list):
            self.value = " ".join(value)
        else:
            self.value = value


class GitPermissionError(GitError):
    """Indicate that the git server responded Permission Denied."""

    def __init__(self, value):
        super(GitPermissionError, self).__init__(value)
        self.value = value
        return None

    def __str__(self):
        consequence = ("Git server replied Permission Denied: %s" %
                                                        (self.value))
        return consequence


class GitUrlError(GitError):
    """Indicate that the server responded with an unexpected
    Error on that URL.
    """

    def __init__(self, value):
        super(GitUrlError, self).__init__(value)
        self.value = value
        return None

    def __str__(self):
        consequence = ("Git server reply unexpected: %s" % (self.value))
        return consequence


class GitReadError(GitError):
    """Indicate that the output of git could not be understood."""

    def __init__(self, value):
        super(GitReadError, self).__init__(value)
        self.value = value
        return None

    def __str__(self):
        consequence = ("Could not understand git output: %s" % (self.value))
        return consequence


class GitExecutionError(GitError):
    """Indicates that git did not execute properly. (syntax errors)"""

    def __init__(self, value):
        super(GitExecutionError, self).__init__(value)
        self.value = value
        return None

    def __str__(self):
        consequence = ("git command execution failed: %s" % (self.value))
        return consequence


class GitWorkspace(object):
    """Class to set up and perform git actions in a workspace
    self.giturl store url of server
    self.gitpath store git path on remote host (part of the url)
    self.workpath store GIT_DIR
    self.revision store git version of current HEAD
    self.repopath store GIT_WORK_TREE
    """

    def __init__(self, giturl, gitpath, workpath):
        """Take `giturl`, `gitpath` and `workpath`,
        store workspace data and allow for clone and log operations.

        Design principle is to let git do as much work as possible,
        and avoid looping over revisions.

        Example::

            mygit = GitWorkspace("url", "sha-1", "/tmp/mygit/")
            mygit.clone(revision)
            mygit.log(revision)

        Raise IOError if file system fails to store git repo.
        Raise GitPermissionError if git denies access to repo.
        Raise GitUrlError if git fails to find repo on server.
        Raise GitReadError if git execution output can't be understood.
        Raise GitExecutionError if git execution fails.
        Raise NotImplementedError if an unfinished method is called.
        """
        self.giturl = giturl
        self.gitpath = gitpath
        self.workpath = workpath
        self.revision = str()
        self.repopath = os.path.join(self.workpath,
                                     self.gitpath.lstrip("/"))

    def __str__(self):
        """Overload __str__ with path of git repo."""
        afterclone = os.path.join(self.repopath, self.revision)
        if os.path.isdir(afterclone):
            return afterclone
        else:
            path = self.repopath
            return path

    def clone(self, revision):
        """Execute git clone on `giturl`.
        Clone and store cloned workspace in `workpath`/`revision`.
        Return path if git already exists.

        Raise GitPermissionError if git denies access to repo.
        Raise GitUrlError if git fails to find repo on server.
        Raise GitReadError if git execution output cant be understood.
        Raise GitExecutionError if git execution fails.
        """
        giturl = self.giturl

        repopath = str(self.repopath)
        try:
            os.makedirs(repopath)
        except EnvironmentError, err:
            if err.errno == errno.EEXIST:
                # EEXIST == 17 == File Exists (this git exists)
                #TODO Use git to check quality of repo if there is one already
                return repopath
            else:
                raise GitPermissionError("Could not create dir in: %s %s" %
                                                  (err.filename, err.strerror))
        #Add --bare to avoid master problem
        cmdargs = ["git", "clone", "-n", giturl, revision]
        try:
            exitcode, out, err = processes.run_cmd(cmdargs, path=repopath)
        except (processes.ChildExecutionError), errmsg:
            exitcode, out, err = errmsg.result
            if exitcode == GIT_EXITCODE_ENV_ERROR:
                raise GitExecutionError(out)
            elif exitcode == GIT_EXITCODE_NETWORK_ERROR:
                raise GitUrlError(out)
            elif exitcode != 0:
                raise GitExecutionError(out)
        except (IndexError, ValueError):
            raise GitExecutionError(cmdargs)

        self.revision = revision
        return out

    def log(self, untilrev, sincerev=""):
        """Collect git log of repository (from `sincerev`) to `untilrev`.

        Raise GitExecutionError if git execution fail.
        Raise GitReadError if git log parsing fails.
        """
        fhash = '%H'
        fauthorname = '%an'
        fauthordate = '%ai'
        fauthoremail = '%ae'
        fcommitname = '%cn'
        fcommitdate = '%ci'
        fcommitemail = '%ce'
        fsubject = '%s'
        fbody = '%B'
        fdelimiter = '%x01'
        flineterminator = '%x02'
        delimiter = '\x01'
        lineterminator = '\x02'

        if sincerev != "":
            revision = ("%s..%s" % (sincerev, untilrev))
        else:
            revision = untilrev

        self.revision = untilrev  # Set revision to HEAD.
        path = self.__str__()

        logfields = ["revision",
                     "author_name",
                     "author_date",
                     "author_email",
                     "commit_name",
                     "commit_date",
                     "commit_email",
                     "subject",
                     "body"]
        warnings.simplefilter("always", UserWarning)

        formatstring = str().join([fhash, fdelimiter,
                                   fauthorname, fdelimiter,
                                   fauthordate, fdelimiter,
                                   fauthoremail, fdelimiter,
                                   fcommitname, fdelimiter,
                                   fcommitdate, fdelimiter,
                                   fcommitemail, fdelimiter,
                                   fsubject, fdelimiter,
                                   fbody, flineterminator])

        self.run_checkout(untilrev, path)
        csv_messages = self.run_log(revision, formatstring, \
                                    path, "--encoding=utf-8")
        try:
            logmessages = parse_csv(csv_messages,
                                    delimiter,
                                    lineterminator,
                                    logfields)
        except IndexError:
            raise GitReadError("Executed git log"
                          "\nFormat string used: %s"
                          "\nFields expected: %s"
                          "\nDelimiter expected: %s"
                          "\nLine terminator expected: %s" %
                                              (formatstring,
                                               logfields,
                                               delimiter,
                                               lineterminator))

        formatstring = str().join([flineterminator,
                                   fhash, fdelimiter])
        filenamefields = ["revision", "filenames"]
        csv_filenames = self.run_log(revision, formatstring, \
                                     path, "--numstat", "--encoding=utf-8")
        try:
            logfilenames = parse_csv(csv_filenames,
                                     delimiter,
                                     lineterminator,
                                     filenamefields)
        except IndexError:
            raise GitReadError("Executed git log"
                          "\nFormat string used: %s"
                          "\nFields expected: %s"
                          "\nDelimiter expected: %s"
                          "\nLine terminator expected: %s" %
                                          (formatstring,
                                           filenamefields,
                                           delimiter,
                                           lineterminator))

        #TODO Make helper function for dict merging etc. (lowprio)
        revfileslist = list()
        for revision in logfilenames:
            revfilesdict = dict()
            try:
                if len(str(revision["revision"])) != 40:
                    continue
                elif len(str(revision["filenames"]).strip("\r\n")) == 0:
                    continue
                revfilesdict["revision"] = revision["revision"]
            except KeyError:
                continue
            try:
                revfilesdict["filenames"] = parse_csv(
                                           revision["filenames"],
                                           '\t',
                                           '\n',
                                           ["add", "del", "filename"])
            except IndexError:
                #Field is unexpectedly ugly lets throw it out.
                continue
            revfileslist.append(revfilesdict)
        logmessages = trim_dict_list(logmessages)
        logmessages = append_key(logmessages,
                                       revfileslist,
                                       "revision",
                                       "filenames")
        logmessages = inherit_key(logmessages, "parent", "revision")
        return logmessages

    def run_checkout(self, revision, path):
        """Check out `revision` in `path`"""
        checkoutargs = ["git", "checkout", revision]
        try:
            processes.run_cmd(checkoutargs, path=path)
        except (processes.ChildExecutionError, IndexError, ValueError):
            try:
                checkoutargs = ["git", "checkout", "-b", revision]
                processes.run_cmd(checkoutargs, path=path)
            except (processes.ChildExecutionError), err:
                pass
            except (IndexError, ValueError):
                pass
        self.revision = revision

    def run_log(self, revision, formatstring, path, *args):
        """Execute git log with `formatstring` in `path` and `args` list,
        Return string of result"""

        cmdargs = ["git", "log", revision, \
                   "--pretty=format:" + formatstring + ""]
        cmdargs.extend(args)
        try:
            exitcode, out, err = processes.run_cmd(cmdargs, path=path)
        except (processes.ChildExecutionError, IndexError, ValueError), err:
            raise GitExecutionError("Tried to execute: %s\nResult was: %s" %
                                                           (cmdargs, err))
        return out


def append_key(log, append, matchkey, attribute):
    """Add key to each dict in list.
    Match key `matchkey` in `log` and `append` `attribute` to dict.
    Return appended list of dicts"""
    newlog = list()
    for logentry in log:
        for appendentry in append:
            try:
                if logentry[matchkey] == appendentry[matchkey]:
                    logentry[attribute] = appendentry[attribute]
            except KeyError:
                break
        newlog.append(logentry)
    return newlog


def inherit_key(heirs, newkey, parentkey):
    """Take dictlist `heirs` iterate its content and add `newkey`
    to all dicts with the value of `parentkey` from previous dict in list.
    Return dict with parent heritage.

    Example::
        heirs = [{'name': 'child'}, {'name': 'papa', 'economy': 'lots'}]
        inheritance = inherit_key(heirs, 'inheritance', 'economy')
        inheritance == [{'name': 'child', 'inheritance': 'lots'},
                        {'name': 'papa', 'economy': 'lots'}]

    Copy previous inheritance value if heir parent value is missing.

    Raise TypeError if `heirs` is not a list containing dicts.
    """
    heritage = list()
    inheritance = str()
    if heirs == [{}]:
        return heirs
    for onedict in reversed(heirs):
        try:
            onedict[newkey] = inheritance
            heritage.append(onedict)
            inheritance = onedict[parentkey]
        except KeyError:
            pass
    return list(reversed(heritage))


def trim_dict_list(dirty):
    """Clean newlines and space from `dirty` list of dict values
    Take a list of dicts, remove all trailing newlines
    and spaces in values of dirty list of dicts.
    Return trimmed list of dicts.

    Raise AttributeError if `dirty` is not a list containing dicts.
    """
    clean = list()
    for onedict in dirty:
        for field in onedict.keys():
            try:
                onedict[field] = onedict[field].strip('\n\r ')
            except KeyError:
                pass
        clean.append(onedict)
    return clean


def parse_csv(csvstring, delimiter, lineterminator, fields):
    """Parse `csvstring` for the list of `fields`,
    `delimiter` divides `fields` and `lineterminator` divides rows.
    Return list of dict containing fields.

    Raise IndexError if delimiters or line terminators are missing.
    """
    results = list()
    oneresult = dict()
    if csvstring == "":
        results = [{}]
        return results
    if not delimiter in csvstring or not lineterminator in csvstring:
        raise IndexError("No delimiter or line terminator in csv string.")
    for row in csvstring.split(lineterminator):
        if len(row) == 0:
            #Lets not use empty rows.
            continue
        csvfields = iter(fields)
        for field in row.split(delimiter):
            try:
                oneresult[csvfields.next()] = field
            except StopIteration:
                warnings.warn("Too many input fields in csv string.")
                continue
        results.append(oneresult)
        oneresult = dict()
    return results


def list_git_files(workpath, url, revision, filetype, gitpath, findpaths):
    """Function to fetch a git repo and list content in findpaths.
    Return list of `filetype` files.

    Raise TypeError if findpaths is not a list.
    Raise GitExecutionError if git clone fails.
    Raise OSError if workspace could not be created or listed.
    """
    if type(findpaths) is not list:
        # Typechecking is LBYL not EAFP but it has to be done here.
        raise TypeError("Argument findpaths must be list.")

    workspace = GitWorkspace(url,
                             gitpath,
                             workpath)
    workspace.clone(revision)
    path = workspace.__str__()
    workspace.run_checkout(revision, path)

    for findpath in findpaths:
        filedir = os.path.join(workspace.__str__(), findpath)
        allfiles = os.listdir(filedir)
        filelist = list()
        for onefile in allfiles:
            onefilepath = os.path.join(filedir, onefile)
            if (onefile.endswith(filetype) and os.path.isfile(onefilepath)):
                filelist.append(onefilepath)
    return filelist
