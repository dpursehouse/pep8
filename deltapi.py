#! /usr/bin/env python
"""Api for determening delta between two
packages or snapshot releases."""
# Example:
# deltapi.delta("app-attaddressbook", "4.0.1.A.0.40", "4.0.1.A.0.241")
import debrevision
import gitrevision


class PackageDownloadError(Exception):
    """Indicate that fetching of package failed, does it exist?"""
    pass


class ControlFieldParseError(Exception):
    """Parsing Debian Control field failed or data was missing."""
    pass


class GitError(Exception):
    """Indicate that git execution failed."""
    pass


class PackageMissingError(Exception):
    """Indicate that the package was missing in a manifest."""
    pass


class RepositoryListError(Exception):
    """Indicate that repository list failed to run on snapshot."""
    pass


def list_manifests(snapshotto, snapshotfrom=""):
    """Collect two manifests
    return two lists of dicts
    Raise RepositoryListError if repository lsit fails.
    """

    # TODO: Don't run this more then once
    if snapshotfrom:
        try:
            manifestfrom = debrevision.run_repository_list(snapshotfrom)
        except debrevision.processes.ChildRuntimeError:
            raise RepositoryListError(snapshotfrom)

    try:
        manifestto = debrevision.run_repository_list(snapshotto)
    except debrevision.processes.ChildRuntimeError:
        raise RepositoryListError(snapshotto)

    if snapshotfrom:
        return(manifestto, manifestfrom)
    else:
        return(manifestto, {})


def packagelog(package, versionto, versionfrom=""):
    """Take packagename and one or more versions.
    Return shortlog of git package between versions.

    Raise ControlFieldParseError if the debian package:
        * Can't be extracted.
        * Can't be parsed.
        * Are missing required controlfields.
    Raise PackageDownloadError if the debian package can't be downloaded.
    Raise GitError if the git clone or git log operation failed.
    """
    tmp = debrevision.TempStore()

    controlgitrevision = "XB-SEMC-Component-Git-Version"
    controlgiturl = "XB-SEMC-Component-Git-URL"

    try:
        packageto = debrevision.fetch_package(versionto, package, tmp.name)
        debto = debrevision.DebControl(packageto)
        shato = debto.controlfile[controlgitrevision]

        if versionfrom:
            packagefrom = debrevision.fetch_package(versionfrom,
                                                    package,
                                                    tmp.name)
            debfrom = debrevision.DebControl(packagefrom)
            shafrom = debfrom.controlfile[controlgitrevision]

    except debrevision.processes.ChildRuntimeError:
        raise PackageDownloadError("Failed to download %s %s" % \
                                    (package, versionfrom))
    except debrevision.ParsePackageError:
        tmp.destroy()
        raise ControlFieldParseError("Failed to parse %s %s" % \
                                    (package, versionfrom))
    except KeyError:
        tmp.destroy()
        raise ControlFieldParseError("Could not find %s in %s %s" % \
                                    (controlgitrevision, package, versionfrom))
    log = [{}]

    try:
        if (shato == shafrom):
            tmp.destroy()
            return log
    except UnboundLocalError:
        pass

    try:
        url = debto.controlfile[controlgiturl]
    except KeyError:
        tmp.destroy()
        raise ControlFieldParseError("Failed to parse %s %s missing %s" % \
                                    (package, versionfrom, controlgiturl))
    try:
        mygit = gitrevision.GitWorkspace(url, shato, tmp.name)
        mygit.clone(shato)
        log = mygit.log(shato, shafrom)
    except UnboundLocalError:
        # shafrom is not defined (there was no fromsnapshot)
        log = mygit.log(shato)
    except gitrevision.GitExecutionError:
        tmp.destroy()
        raise GitError("Error cloning %s %s" % (url, shato))
    except gitrevision.GitReadError:
        tmp.destroy()
        raise GitError("Error understanding output from git log. %s %s..%s" % \
                                                        (url, shafrom, shato))
    tmp.destroy()
    return log


def delta(packagename, snapto, snapfrom=""):
    """Take `packagename`, `snapto` and optional `snapfrom`
    download package collect git revisions and return shortlog.

    Raise PackageMissingError and give the snapshot version where
    package is missing as text attribute if a package is not in snapshot.
    """
    manifestto = []
    manifestfrom = []

    (manifestto, manifestfrom) = list_manifests(snapto, snapfrom)
    try:
        packversionto = manifestto[packagename]
    except KeyError:
        # The snapshot snapto manifest is missing the `packagename`.
        raise PackageMissingError(snapto)

    try:
        packversionfrom = manifestfrom[packagename]
    except KeyError:
        packversionfrom = ""
        # The snapshot snapto manifest is missing the `packagename`.
        #raise PackageMissingError(snapto)

    log = packagelog(packagename, packversionto, packversionfrom)

    return log
