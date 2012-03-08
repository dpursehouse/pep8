""" Classes and helper methods for interacting with a git repository.
"""

from hashlib import sha224
import os
import shutil
import urlparse

import processes

#Commit SHA1 string length
SHA1_STR_LEN = 40


def is_sha1(revision):
    ''' Checks if `revision` is a valid commit SHA1.
    A character string is considered to be a commit SHA1 if it has exactly
    the expected length and is a base 16 represented integer.
    Returns True or False.
    '''
    if (len(revision) == SHA1_STR_LEN):
        try:
            # Convert from base 16 to base 10 to ensure it's a valid base 16
            # integer
            int(revision, 16)
            return True
        except ValueError:
            pass
    return False


def is_tag(revision):
    ''' Checks if `revision` is a tag, i.e. is of the format "refs/tags/xxxx".
    Returns True or False.
    '''
    return revision.startswith("refs/tags/")


def is_sha1_or_tag(revision):
    ''' Checks if `revision` is a commit SHA1 or a tag.
    Returns True or False.
    '''
    return (is_sha1(revision) or is_tag(revision))


class GitError(Exception):
    ''' GitError is raised if a git command fails for some reason.
    '''


class GitRepository(object):
    ''' Encapsulation of a git repository.
    '''

    def __init__(self, working_dir, url=None, clone=False):
        ''' Initilialize the git referred to by `url`, using `working_dir`
        as the root folder in which the git is locally cached.

        `url`, if specified, is expected to be the full URL to the git on the
        repository server, for example "git://url.to.server/path/to/git".

        If `url` is specified, `working_directory` is expected to be the root
        path of the local cache folder, and the git name will be parsed from
        the url will be appended to it, i.e. if `working_dir` is "/cache", and
        the url is "git://url.to.server/path/to/git", the git folder will be
        "/cache/path/to/git/.git".

        If `url` is not specified, `working_directory` is expected to be the
        path in which an existing git resides and the git folder will be
        "working_dir/.git".

        In both cases, `working_dir` will be converted to an absolute path.

        If the git does not exist in the `working_dir`, and `clone` is
        False, an empty git will be intialized.  If `clone` is True, the git
        will be cloned from the repository specified in `url`.

        Raises GitError if `clone` is True but `url` is not specified.
        '''
        if clone and not url:
            raise GitError("Cannot clone git without URL")

        self.url = url
        if self.url:
            # The path part of the URL will for sure contain a leading
            # slash. It might also contain a trailing slash.
            # Normalize the git name by removing both.
            # pylint: disable-msg=E1101
            # (disable "'ParseResult' has no 'path' member" error)
            self.git_name = urlparse.urlparse(self.url).path.strip("/")
            # pylint: enable-msg=E1101

            # Append the git name onto the working directory name, to get
            # the absolute path of the git in the local filesystem.
            self.working_dir = os.path.abspath(os.path.join(working_dir,
                                                            self.git_name))
        else:
            self.git_name = os.path.basename(working_dir)
            self.working_dir = os.path.abspath(working_dir)

        # The git's control files reside in the .git folder within
        # the directory.
        self.git_path = os.path.join(self.working_dir, ".git")

        # If the .git folder does not exist, initialize or clone it
        if not os.path.exists(self.git_path):
            try:
                cmd = ["git"]
                if clone:
                    cmd += ["clone", self.url, self.working_dir]
                else:
                    cmd += ["init", self.working_dir]
                processes.run_cmd(cmd)
            except Exception:
                # We must take care to remove all traces of the directory
                # if anything fails, otherwise we risk leaving an only
                # partially initialized git directory in the cache.
                shutil.rmtree(self.git_path, ignore_errors=True)
                raise

        self.gitstart = ["git", "--git-dir=" + self.git_path,
                         "--work-tree=" + self.working_dir]

    def run_cmd(self, args):
        '''Run the git command specified in `args`. The "git" command
        is not required as it is already set in the member `gitstart`.
        Return a tuple with status, output from stdout, output from stderr.
        Raise some form of ChildExecutionError if any error occurs.
        '''
        if isinstance(args, list):
            cmd = self.gitstart + args
        else:
            cmd = self.gitstart + [args]
        return processes.run_cmd(cmd)

    def diff_commits(self, from_rev, to_rev):
        ''' Get the commits that are in `from_rev` but not `to_rev`.
        Return the merge base and a dict of sha1: commit message.
        '''
        merge_base = ""
        results = {}

        # Unique hash is added in the log output so we can
        # easily separate the commits later.
        unique_hash = sha224(self.git_name + from_rev + to_rev).hexdigest()

        # Find merge base between the target and source revisions
        cmd = ["merge-base", from_rev, to_rev]
        merge_base = self.run_cmd(cmd)[1].strip()

        if merge_base:
            cmd = ["log", "--no-merges",
                   "--format=" + unique_hash + "%n%H%n%s%n%b",
                   to_rev + '..' + from_rev]
            log = self.run_cmd(cmd)[1].strip()
            if log:
                start = log.find(unique_hash)
                commit_length = 0
                done = False
                while not done:
                    # Get the commit
                    start += commit_length + len(unique_hash)
                    commit_length = log[start:].find(unique_hash)
                    if commit_length == -1:
                        done = True
                        commit = log[start:]
                    else:
                        commit = log[start:start + commit_length]
                    commit = commit.strip()
                    sha1_and_commit = commit.split('\n', 1)
                    results[sha1_and_commit[0]] = sha1_and_commit[1]

        return merge_base, results

    def fetch(self, url=None, refspec=None):
        ''' Fetch the `refspec` from `url`.
        Return a tuple with status, output from stdout, output from stderr.
        Raise some form of ChildExecutionError if any error occurs.
        '''
        cmd = ["fetch"]
        if url:
            cmd += [url]
        elif self.url:
            cmd += [self.url]
        if refspec:
            cmd += [refspec]
        return self.run_cmd(cmd)
