#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""This script can be used to modify manifest files to put static references on
a list of projects.
Pseudo-XML example:

INPUT:

    -- source --
    A normal default.xml file from the branch you're starting from.

    project1 revision=branch
    project2 revision=branch
    project3 revision=branch
    project4 revision=branch
    project5 revision=branch
    project6 revision=branch

    -- selected-projects --
    A manifest, but the only thing that's read from this is which projects it
    contains. Those projects will be given SHA1s.

    project3 ???
    project5 ???

    -- static-manifest --
    A manifest_static.xml from the freeze you want to use.

    project1 revision=0c01eb
    project2 revision=ce36a6
    project3 revision=cd508c
    project4 revision=df980d
    project5 revision=879585
    project6 revision=842a26

OUTPUT:

    -- output --
    project3 and 5 gets a SHA1.

    project1 revision=branch
    project2 revision=branch
    project3 revision=cd508c
    project4 revision=branch
    project5 revision=879585
    project6 revision=branch

    -- branchlist --
    This is a modified "selected-projects" with the SHA1s inserted.

    project3 revision=cd508c
    project5 revision=879585
"""

import logging
from optparse import OptionParser
import sys
from xml.dom.minidom import parse
from xml.parsers.expat import ExpatError


class ModmanError(Exception):
    pass


def tryparse(filepath):
    """Helper function that can construct an error message with the
    pathname of the file if there's problems with parsing.

    """

    try:
        return parse(filepath)
    except ExpatError, e:
        raise ModmanError("Failed to parse %s: %s" % (filepath, e))


def xmlmerge(sourcefile, replacefile, matchfile=None,
             tag="project", mattribute="name", rattribute="revision"):
    """Returns merge,match of xmlfiles: sourcefile, replacefile, matchfile.

    Merges values from "replacefile", to "sourcefile", matching "matchfile"
    where "tag" exists in "matchfile" and "sourcefile" and
    all "rattribute" values will be replaced if "mattribute" matches.
    Raises ModmanError on fatal errors.

    """

    sourcetree = tryparse(sourcefile)
    replacetree = tryparse(replacefile)
    if matchfile:
        matchtree = tryparse(matchfile)
    else:
        matchtree = tryparse(sourcefile)

    replacements = {}
    for element in replacetree.getElementsByTagName(tag):
        attribute = \
            element.attributes[mattribute].nodeValue.encode('utf-8')
        replacements[attribute] = \
            element.attributes[rattribute].nodeValue.encode('utf-8')

    nodes = {}
    for element in sourcetree.getElementsByTagName(tag):
        attribute = \
            element.attributes[mattribute].nodeValue.encode('utf-8')
        nodes[attribute] = element

    for element in matchtree.getElementsByTagName(tag):
        attribute = \
            element.attributes[mattribute].nodeValue.encode('utf-8')
        try:
            nodes[attribute].setAttribute(rattribute, replacements[attribute])
            element.setAttribute(rattribute, replacements[attribute])
        except KeyError:
            logging.error("Value revision missing for %s in %s" % (attribute,
                          replacefile))
    return sourcetree, matchtree


def _main(inargs):
    usage = """usage: %prog [OPTIONS] [OUTPUT-FILE] [BRANCHLIST-FILE]
    Modifies manifest files to put static references to a list of
    projects.
    Example:
    %prog -i default.xml -s static.xml -p projects.xml output.xml
    %prog takes at least 2 arguments
     * static-manifest sha-1 revision manifest.
     * input source-manifest as source of projectnames.
     * selected-projects manifest with project names (optional).
    """
    parser = OptionParser(usage=usage)
    parser.add_option("-s", "--static", dest="static",
                      help="File containing static manifest with sha-1 "\
                      "references. (For all projects mentioned in editlist)")
    parser.add_option("-i", "--input-source", dest="source",
                      help="File containing the manifest you want to modify.")
    parser.add_option("-p", "--projects", dest="project",
                      help="File containing manifest of projects to modify.")

    logging.basicConfig(format='%(message)s', level=logging.INFO)

    (options, argv) = parser.parse_args(inargs)
    if not any([options.static, options.source]):
        parser.error("You did not give any arguments")
    if not options.static:
        parser.print_help()
        parser.error("You must specify a static sha1 file.")
    if not options.source:
        parser.print_help()
        parser.error("You must specify a target file.")

    try:
        mergeresult, branchresult = xmlmerge(options.source,
                                             options.static,
                                             options.project,
                                             "project", "name", "revision")
    except EnvironmentError, e:
        logging.error("Failed to read input: %s" % e)
        return 1
    except ModmanError, e:
        logging.error(e)
        return 1

    if len(argv) == 0:
        outputfile = "output.xml"
        branchlistfile = "branchlist.xml"
    elif len(argv) == 1:
        outputfile = argv[0]
        branchlistfile = "branchlist.xml"
    elif len(argv) >= 2:
        outputfile = argv[0]
        branchlistfile = argv[1]

    try:
        with file(outputfile, "w") as mergeoutput:
            mergeresult.writexml(mergeoutput, encoding="UTF-8")

        with file(branchlistfile, "w") as branchoutput:
            branchresult.writexml(branchoutput, encoding="UTF-8")
    except EnvironmentError, e:
        logging.error("Failed to write output: %s" % e)
        return 1

    logging.info("Done writing to %s and %s" % (outputfile, branchlistfile))
    return 0

if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
