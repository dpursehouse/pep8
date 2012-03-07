#!/usr/bin/env python

import sys
import os
import optparse

import semcwikitools


def main():
    usage = "usage: %prog [options] PAGE SECTION < INPUTFILE\n\n" + \
            "Pipe the contents of the section to this script"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-n", "--noformat", dest="noformat",
            action="store_true", help="Don't interpret text as wiki markup, "
                "display it with formatting as is.")
    parser.add_option("-p", "--prepend", dest="prepend", default=False,
            action="store_true", help="Add new section on the top of the page")
    parser.add_option("-w", "--wiki", dest="wiki",
            default="https://wiki.sonyericsson.net/wiki_androiki/api.php",
            help="Api script of the wiki to use. [default: %default]")
    (options, args) = parser.parse_args()
    if len(args) != 2:
        parser.print_help()
        parser.error("Incorrect number of arguments")

    page = args[0]
    section = args[1]

    if options.noformat:
        data = ""
        for line in sys.stdin:
            data += " " + line
    else:
        data = sys.stdin.read()

    try:
        w = semcwikitools.get_wiki(options.wiki)
        semcwikitools.add_section_to_page(w, page, section,
                                          data, options.prepend)
    except semcwikitools.SemcWikiError, e:
        print >> sys.stderr, "Error updating the wiki:", e
        sys.exit(1)

if __name__ == "__main__":
    main()
