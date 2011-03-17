#!/usr/bin/env python

import semcutil
import sys
import os
from optparse import OptionParser

cm_tools = os.path.dirname(os.path.abspath(sys.argv[0]))
sys.path.append(os.path.join(cm_tools, "external-modules"))
sys.path.append(os.path.join(cm_tools, "semcwikitools"))
import wikitools
import semcwikitools

def get_manifests(branchlist, manifestpath):
    """Returns a list of tuples containing:
    1) The name of the branch
    2) A RepoXmlManifest object representing the manifest
    for all branches in branchlist."""
    manifests = []
    branches = []
    for branch in branchlist:
        code, out, err = semcutil.run_cmd("git", "show", "%s:default.xml" % \
                (branch), path=manifestpath)
        manifestdata = out.strip()
        branches.append(branch.replace("origin/",""))
        manifests.append(semcutil.RepoXmlManifest(manifestdata).projects)
    return zip(branches, manifests)

def find_projects(branches):
    """Returns a set of all the projects found in the manifests.
    Input is the tuple-list structure returned by get_manifests."""
    projects = set()
    for branch, manifest in branches:
        projects.update(manifest)
    return projects

def isstatic(s):
    """Tries to guess if a ref points to a static version or not.
    Returns None if not.
    Returns a string with a short form of the static version otherwise."""
    if len(s) == 40 and s.isalnum():
        return s[:6]
    elif s.startswith("refs/tags"):
        return s.replace("refs/tags","")

def get_branches_html(branches):
    """Builds a big html table with all the branches of all components in the
    given manifests.
    Input is the tuple-list structure returned by get_manifests."""
    projects = find_projects(branches)

    data = """<h1>Red: The same component branch is used on another _of these_
 manifest branch(es)</h1>\n\n<h1>Bold+Italic: The branch of the component has
 a different name than the manifest branch</h1>\n\n"""

    data += '<table style="padding: 10px;"><tr><th></th>'
    for branch, manifest in branches:
        data += "<th>%s</th>" % branch
    data += "</tr>\n"

    for project in sorted(projects):
        data += "<tr><td>%s</td>" % (project)
        branchcount = {}
        for branch, manifest in branches:
            if project in manifest:
                rev = manifest[project]["revision"]
                if rev not in branchcount:
                    branchcount[rev] = 0
                branchcount[rev] += 1

        for branch, manifest in branches:
            if project in manifest:
                rev = manifest[project]["revision"]
                style = ""
                static = isstatic(rev)
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
                        default="https://wiki.sonyericsson.net/wiki_androiki/api.php",
                        help="Api script of the wiki to use. [default: %default]")
    parser.add_option("-m", "--manifest", dest="manifestpath",
                        default="manifest",
                        help="Path to the manifest-git. [default: %default]")

    (options, branchnames) = parser.parse_args()
    if len(branchnames) < 1:
        parser.print_help()
        parser.error("Incorrect number of arguments")
    if not options.page:
        parser.error("You have to supply a name for the wikipage.")

    branches = get_manifests(branchnames, options.manifestpath)
    data = get_branches_html(branches)

    w = semcwikitools.get_wiki(options.wiki)
    semcwikitools.write_page(w, options.page, data)

if __name__ == "__main__":
    _main()
