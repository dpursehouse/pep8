#!/usr/bin/env python

import sys
import os
import optparse

# Make sure that we can import wikitools before we load semcwikitools
cm_tools = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
sys.path.append(os.path.join(cm_tools, "external-modules"))
import wikitools

import semcwikitools

def main():
    usage = "usage: %prog [options] FILEPATH"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-w", "--wiki", dest="wiki",
            default="https://wiki.sonyericsson.net/wiki_androiki/api.php",
            help="Api script of the wiki to use. [default: %default]")
    parser.add_option("-p", "--page", dest="page",
            help="Add a section to this page with a link to the file")
    parser.add_option("-n", "--name", dest="name",
            help="Give the file this name on wiki. Make sure you include" + \
            " a file extension that the wiki allows.")
    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.print_help()
        parser.error("Incorrect number of arguments")

    filepath = args[0]
    if options.name:
        filename = options.name
    else:
        filename = os.path.basename(filepath)

    try:
        w = semcwikitools.get_wiki(options.wiki)
        semcwikitools.upload_file_to_wiki(w, filename, filepath)
        if options.page:
            linktext = "[[File:%s]]" % (filename)
            semcwikitools.add_section_to_page(w, options.page, filename,
                    linktext)
    except semcwikitools.SemcWikiError, e:
        print >> sys.stderr, "Error updating the wiki:", e
        sys.exit(1)

if __name__ == "__main__":
    main()

