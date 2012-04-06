#!/usr/bin/env python

""" For given list of manifest branches, generate a list of components
used on the manifest(s) and their revisions, and write to a given wiki
page.
"""

from optparse import OptionParser
import os
import re
import sys

from git import is_sha1, is_tag
from include_exclude_matcher import IncludeExcludeMatcher
import manifest
import processes
from wiki import semcwikitools

# Prefixes to use when finding manifest refs
_STRIPPED_PREFIXES = [r'^refs/(?:heads|tags)/(.*)',
                      r'^refs/remotes/[^/]+/(.*)']


def get_manifests(refname, manifestpath):
    """Matches the ref name in `refname` against the refs found in the
    manifest from the local `manifestpath` directory and returns a
    list containing one or more tuples for each ref matched. If no
    refs matched an empty list is returned.

    Each returned tuple contains the fully-qualified name of the ref,
    the "pretty" name of the ref, and a dictionary with information
    from the manifest. The latter dictionary is really the `projects`
    member of a `RepoXmlManifest` object and is keyed by the git
    name. Each value is another dictionary with the keys `path`,
    `name`, and `revision`, corresponding to the identically named
    attributes of the <project> element of the XML manifest.

    The ref matching is done by using `git show-ref`, i.e. matches are
    made from the end of the string. For example, `master` could
    result in both refs/heads/master, refs/remotes/origin/master, and
    refs/remotes/origin/oss/master being returned. To force it to
    return a particular branch the input ref must specify a unique ref
    name suffix.

    The "pretty" name of the ref found in the second member of the
    tuple is the bare name of the ref without any refs/heads,
    refs/remotes/foo, or refs/tags prefix. This string is probably
    what should be shown to the user.

    If a Git operation fails, a processes.ChildExecutionError exception
    (or any subclass thereof) will be thrown. If the manifest XML data
    found in the default.xml file on the branch being inspected can't
    be parsed, a manifest.ManifestParseError exception will be
    thrown."""

    refs = []
    branches = []
    manifests = []

    # Ask `git show-ref` to list all branches that match the ref
    # given in `refname`. That command returns two-column lines
    # containing (SHA-1, refname).
    _code, out, _err = processes.run_cmd("git", "show-ref", refname,
                                         path=manifestpath)
    for sha1, ref in [s.split() for s in str(out).splitlines()]:
        # For each (SHA-1, ref) pair, get a list of files
        # and check if default.xml is included.
        _code, tree, _err = processes.run_cmd("git", "ls-tree", sha1,
                                              path=manifestpath)

        # If default.xml is not found, we can skip this ref.
        if "default.xml" not in tree:
            continue

        # Get the manifest data
        _code, manifestdata, _err = processes.run_cmd("git", "show",
                                                      "%s:default.xml" % (ref),
                                                      path=manifestpath)
        manifestdata = str(manifestdata).strip()

        # If a ref matches one of the elements in `_STRIPPED_PREFIXES`,
        # set `prettyname` to the first captured group.
        prettyname = ref
        for prefix in _STRIPPED_PREFIXES:
            match = re.search(prefix, ref)
            if match:
                prettyname = match.group(1)
                break
        refs.append(ref)
        branches.append(prettyname)
        manifests.append(manifest.RepoXmlManifest(manifestdata).projects)
    return zip(refs, branches, manifests)


def find_projects(branches):
    """Returns a set of all the projects found in the manifests.
    Input is the tuple-list structure returned by get_manifests."""
    projects = set()
    for _ref, _branch, mfest in branches:
        projects.update(mfest)
    return projects


def is_static(ref):
    """Tries to guess if `ref` points to a static version or not.
    Returns None if not.
    Returns a string with a short form of the static version otherwise."""
    if is_sha1(ref):
        return ref[:6]
    elif is_tag(ref):
        return ref.replace("refs/tags", "")


def get_branches_html(branches, pattern_matcher):
    """Builds a big html table with all the branches of all components in the
    given manifests.
    Input:
        Tuple-list structure returned by get_manifests
        Function used to filter the gits.
    """
    projects = find_projects(branches)

    data = """<h1>Red: The same component branch is used on another of these
 manifest branch(es)</h1>\n\n<h1>Bold+Italic: The branch of the component has
 a different name than the manifest branch</h1>\n\n<h1>Green: The component is
 not included in the manifest.</h1>\n\n"""

    data += '<table style="padding: 10px;"><tr><th></th>'
    for _ref, branch, mfest in branches:
        data += "<th>%s</th>" % branch
    data += "</tr>\n"

    projects = filter(pattern_matcher, projects)

    for project in sorted(projects):
        data += "<tr><td>%s</td>" % (project)
        branchcount = {}
        for _ref, branch, mfest in branches:
            if project in mfest:
                rev = mfest[project]["revision"]
                if rev not in branchcount:
                    branchcount[rev] = 0
                branchcount[rev] += 1

        for _ref, branch, mfest in branches:
            if project in mfest:
                rev = mfest[project]["revision"]
                style = ""
                static = is_static(rev)
                if static:
                    style = ' style="background-color:#CCCCCC;"'
                    rev = static
                elif rev != branch and branchcount[rev] > 1:
                    # If the component branch differs from the manifest branch
                    # and other manifests use this branch, set red background
                    # and change the font style.
                    style = ' style="background-color:#FF8888; font-weight:' \
                                'bold; font-style:italic;"'
                elif rev != branch:
                    # If the component branch differs from the manifest branch,
                    # change the font style.
                    style = ' style="font-weight:bold; font-style:italic;"'
                elif branchcount[rev] > 1:
                    # If other manifests use this branch, set red background
                    style = ' style="background-color:#FF8888;"'
                cell = "<td%s>&nbsp;%s&nbsp;</td>" % (style, rev)
            else:
                # If the project is not used in this manifest at all,
                # set green background.
                cell = '<td style="background-color:#88FF88;"></td>'
            data += cell
        data += "</tr>\n"
    data += "</table>\n"

    return data


def _main():
    usage = "usage: %prog [options] origin/branch1 [origin/branch2 ...]"
    parser = OptionParser(usage=usage)
    parser.add_option("-p", "--page", dest="page",
                        help="Name of the page on the wiki to write.")
    parser.add_option("-w", "--wiki", dest="wiki",
                        default="https://wiki.sonyericsson.net/" +
                                    "wiki_androiki/api.php",
                        help="Api script of the wiki to use. " +
                                "[default: %default]")
    parser.add_option("-m", "--manifest", dest="manifestpath",
                        default="manifest",
                        help="Path to the manifest-git. [default: %default]")
    parser.add_option("-i", "--include-git", dest="include_git",
                        action="append", default=None,
                        help="Regex pattern of gits to include. Multiple "\
                        "patterns can be passed as arguments [-i <pattern> -i"\
                        " <pattern>]")
    parser.add_option("-x", "--exclude-git", dest="exclude_git",
                        action="append", default=None,
                        help="Regex pattern of gits to exclude. Multiple "\
                        "patterns can be passed as arguments [-x <pattern> -x"\
                        " <pattern>]. Has precedence over the --include-git "\
                        "option")

    (options, branchnames) = parser.parse_args()
    if len(branchnames) < 1:
        parser.print_help()
        parser.error("Incorrect number of arguments")
    if not options.page:
        parser.error("You have to supply a name for the wikipage.")

    options.manifestpath = os.path.abspath(options.manifestpath)
    if not os.path.isdir(options.manifestpath):
        parser.error("Manifest path %s does not exist" % options.manifestpath)

    if not options.include_git:
        options.include_git = [r"^"]

    pattern_matcher = IncludeExcludeMatcher(options.include_git,
                                            options.exclude_git)

    branches = []
    errors = []
    for branch in branchnames:
        try:
            branches += get_manifests(branch, options.manifestpath)
        except (processes.ChildExecutionError, manifest.ManifestParseError), e:
            error = "Error getting data for branch %s" % (branch)
            errors.append(error)
            print >> sys.stderr, "%s: %s" % (error, e)

    data = ""
    for error in errors:
        data += "<strong>%s</strong><br />" % error
    data += get_branches_html(branches, pattern_matcher.match)

    wiki = semcwikitools.get_wiki(options.wiki)
    semcwikitools.write_page(wiki, options.page, data)

if __name__ == "__main__":
    _main()
