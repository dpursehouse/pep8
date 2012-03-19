""" The repo module contains classes and functions to interact with
repository.
"""
import os
from shutil import copy

import processes

#Gerrit server URL
GERRIT_URL = "review.sonyericsson.net"
ASW_MANIFEST = "platform/manifest"
MANIFEST_PATH = ".repo/manifests"


class RepoError(Exception):
    """Class to handle exceptions in 'Repo' functionalities"""


class Repo(object):
    """Repo class to support 'repo init' and 'repo sync'"""
    def __init__(self, branch=None, project=ASW_MANIFEST, path=".",
                 static_manifest=None):
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
            static_manifest: local path of static manifest file.
                Static manifest will be copied to '.repo/manifests'
                directory and repo will be initialized w.r.t the
                static manifest.

        Exception raised: RepoError
        Exception cases:
            Specified `path` does not exists.
            If .repo doesn't exists and branch name not provided.
            Failed to initialize repository.
            Invalid static manifest path.
            Unable to copy static manifest to .repo/manifests directory.

        """
        path = os.path.abspath(path)
        if not os.path.exists(path):
            raise RepoError("Specified path '%s' does not exist" % path)
        self.workspace = path

        self._check_inside_repo()

        if not branch:
            raise RepoError("Specify the manifest branch name")

        rev_path = "git://%s/%s" % (GERRIT_URL, project)
        command = ["repo", "init", "-u", rev_path, "-b", branch]

        if os.getenv("REPO_MIRROR"):
            command += ["--reference=$REPO_MIRROR"]

        try:
            processes.run_cmd(command, path=path)
        except processes.ChildExecutionError, err:
            raise RepoError("Failed to initialize repository for branch "
                            "%s: %s" % (branch, err))

        if static_manifest:
            static_manifest = os.path.abspath(static_manifest)
            file_name = os.path.basename(static_manifest)
            file_path = os.path.join(self.workspace, MANIFEST_PATH,
                                     file_name)
            try:
                copy(static_manifest, file_path)
            except IOError, err:
                raise RepoError(err)

            try:
                processes.run_cmd("repo", "init", "-m", file_name,
                                  path=path)
            except processes.ChildExecutionError, err:
                raise RepoError("Failed to initialize static manifest "
                                "%s: %s" % (static_manifest, err))

    def _check_inside_repo(self):
        """Raises an exception if the workspace is inside a previous
        repo workspace.

        """
        checkdir = self.workspace
        while checkdir != os.path.dirname(checkdir):
            checkdir = os.path.dirname(checkdir)
            repodir = os.path.join(checkdir, ".repo")
            if os.path.exists(repodir):
                raise RepoError("'repo init' already done in a parent "
                                "directory: %s" % repodir)

    def sync(self, project=None, jobs=None):
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
        command = ["repo", "sync"]
        if isinstance(project, list):
            command += project
        elif project:
            command += [project]
        if jobs:
            command += ["-j%d" % jobs]

        try:
            processes.run_cmd(command, path=self.workspace)
        except processes.ChildExecutionError, err:
            raise RepoError("Failed to sync project %s: %s" % (project, err))
