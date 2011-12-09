import os
import shutil
import urlparse

from processes import run_cmd

#Commit SHA1 string length
SHA1_STR_LEN = 40


def is_sha1(str):
    """ Checks if `str` is a valid commit SHA1.
    A character string is considered to be a commit SHA1 if it has exactly
    the expected length and is a base 16 represented integer.
    Returns True or False.
    """
    if (len(str) == SHA1_STR_LEN):
        try:
            # Convert from base 16 to base 10 to ensure it's a valid base 16
            # integer
            sha10 = int(str, 16)
            return True
        except:
            pass
    return False


def is_tag(str):
    """ Checks if `str` is a tag, i.e. is of the format "refs/tags/xxxx".
    Returns True or False.
    """
    return str.startswith("refs/tags/")


def is_sha1_or_tag(str):
    """ Checks if `str` is a commit SHA1 or a tag.
    Returns True or False.
    """
    return (is_sha1(str) or is_tag(str))


class CachedGitWorkspace():
    """ Encapsulation of a git workspace.
    """

    def __init__(self, url, cache_root):
        self.url = url
        self.cache_root = cache_root

        # The path part of the URL will for sure contain a leading
        # slash and it might contain a trailing slash. Let's normalize
        # the git name by removing both.
        self.git_name = urlparse.urlparse(self.url).path.strip("/")
        self.git_path = os.path.join(self.cache_root, self.git_name + ".git")

        try:
            if not os.path.exists(self.git_path):
                os.makedirs(self.git_path)
            run_cmd("git", "init", "--bare", path=self.git_path)
        except Exception, err:
            # We must take care to remove all traces of the directory
            # if anything fails. Otherwise we risk leaving an only
            # partially initialized git directory in the cache.
            shutil.rmtree(self.git_path, ignore_errors=True)
            raise err

    def fetch(self, refspec):
        """ Fetch the `refspec`.
        """
        run_cmd("git", "fetch", self.url, refspec, path=self.git_path)
