import os
import shutil
import urlparse

from processes import run_cmd


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
