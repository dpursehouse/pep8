#!/usr/bin/env python

import sys
import os
import optparse

# Make sure that we can import wikitools before we load semcwikitools
cm_tools = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
sys.path.append(os.path.join(cm_tools, "wikitools-1.1.1"))
import wikitools

import semcwikitools

def main():
    usage = "usage: %prog [options] PAGE ITEM"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-s", "--namespace", dest="namespace",
            action="store", help="Add this to the path to the ITEM on the wiki")
    parser.add_option("-w", "--wiki", dest="wiki",
            default="https://wiki.sonyericsson.net/wiki_androiki/api.php",
            help="Api script of the wiki to use. [default: %default]")

    (options, args) = parser.parse_args()

    if len(args) != 2:
        parser.print_help()
        parser.error("Incorrect number of arguments")
    page = args[0]
    item = args[1]
    link = item
    if options.namespace:
        link = "/".join([options.namespace, item])

    try:
        w = semcwikitools.get_wiki(options.wiki)
        semcwikitools.add_item_to_feed(w, page, item, "[[%s]]" % (link))
    except semcwikitools.SemcWikiError, e:
        print >> sys.stderr, "Error updating the wiki:", e
        sys.exit(1)

if __name__ == "__main__":
    main()

