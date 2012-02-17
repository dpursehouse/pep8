""" The repo module contains classes and functions to interact with
repository.
"""
import os

import processes

#Gerrit server URL
GERRIT_URL = "review.sonyericsson.net"
ASW_MANIFEST = "platform/manifest"


class RepoError(Exception):
    """Class to handle exceptions in 'Repo' functionalities"""


class Repo:
    """Repo class to support 'repo init' and 'repo sync'"""
    def __init__(self, branch=None, project=ASW_MANIFEST, path="."):
        """Initialize repository for the manifest branch specified.

        Initialize the 'project' for the specified `branch`.
        `project` can be either 'platform/manifest' for android or
        'platform/ammsmanifest' for amss. By default `project` is
        set to android manifest and `path` is set to current working
        directory.
        If '.repo' directory already exists then, just set `path`
        as workspace directory and return.

        Arguments:
            branch: name of manifest branch to be initialized.
            project: manifest git name.
            path: relative path where to initialize repository.

        Exception raised: RepoError
        Exception cases:
            Specified `path` does not exists.
            If .repo doesn't exists and branch name not provided.
            Failed to initialize repository.

        """
        if not os.path.exists(path):
            raise RepoError("Specified path '%s' does not exist" % path)
        self.workspace = os.path.abspath(path)

        if os.path.exists(os.path.join(self.workspace, ".repo")):
            return

        if not branch:
            raise RepoError("Specify the manifest branch name")

        rev_path = "git://%s/%s" % (GERRIT_URL, project)
        try:
            processes.run_cmd("repo", "init", "-u",
                              rev_path, "-b", branch,
                              path=path)
        except processes.ChildExecutionError, err:
            raise RepoError("Failed to initialize repository for branch "
                            "%s: %s" % (branch, err))

    def sync(self, project=None, jobs=None, path=None):
        """Sync the project.

        Repo sync,
            1) specified project. OR
            2) each project in the list OR
            3) for all projects in manifest if `project` is None.
        The project is synced with respect to the
        path and revision specified in the manifest file in '.repo'.

        Exception raised: RepoError
        Exception cases:
            Repo not initialized in the 'path' specified.
            Failed to sync project.

        """
        if not path:
            path = self.workspace
        command = ["repo", "sync"]
        if isinstance(project, str):
            command += [project]
        elif isinstance(project, list):
            command += project
        if jobs:
            command += ["-j%d" % jobs]
        print command
        try:
            processes.run_cmd(command, path=path)
        except processes.ChildExecutionError, err:
            raise RepoError("Failed to sync project %s: %s" % (project, err))
