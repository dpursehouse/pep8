#!/usr/bin/env python

import os.path
import os
import wikitools
import urlparse
import urllib


class SemcWikiError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class WikiOperation():
    def __init__(self, f):
        self.f = f

    def __call__(self, *args):
        try:
            return self.f(*args)
        except wikitools.api.APIError, e:
            raise SemcWikiError("The wiki returned an error:\n" + str(e))
        except wikitools.wiki.WikiError, e:
            raise SemcWikiError("The wiki returned an error:\n" + str(e))


def read_netrc_cred(wikiserver):
    try:
        netrc = file(os.path.join(os.environ["HOME"], ".netrc"))
    except IOError, e:
        raise SemcWikiError("Failed to open $HOME/.netrc: " + str(e))

    for line in netrc:
        parts = line.split()
        if len(parts) == 6:
            if parts[1] == wikiserver:
                return parts[3], parts[5]
    raise SemcWikiError("Could not find %s in $HOME/.netrc" % (wikiserver))


def get_page_rss(wiki, pagename):
    url = wiki.apibase
    url = url.replace("api.php", "index.php")
    encpage = urllib.quote(pagename)
    url += "?title=%s&action=feed" % (encpage)
    return url


@WikiOperation
def get_wiki(url):
    urlp = urlparse.urlparse(url)
    cred = read_netrc_cred(urlp.netloc)
    wiki = wikitools.wiki.Wiki(url, cred)
    return wiki


@WikiOperation
def add_item_to_feed(wiki, page, title, text):
    # Add convenience link to the rss-feed
    fulltext = "[%s RSS feed for this page]\n\n" % (get_page_rss(wiki, page))
    # A TOC would just be a duplicate of the page itself
    fulltext += "__NOTOC__\n"
    # This must be added every time, otherwise it gets overwritten
    fulltext += "<startFeed/>\n\n"
    # Add the item
    fulltext += "= %s =\n\n%s" % (title, text)

    p = wikitools.page.Page(wiki, page)

    # Setup the feed if there wasn't a feed before
    if not p.exists or not "<endFeed/>" in p.getWikiText():
        fulltext += "\n\n<endFeed/>"
        section = "new"
    else:
        section = "0"

    result = p.edit(section=section, text=fulltext)
    editedpage = result["edit"]["title"]
    return editedpage


@WikiOperation
def add_section_to_page(wiki, page, title, text, prepend=False):
    p = wikitools.page.Page(wiki, page)
    if prepend:
        text = "== %s ==\n\n%s" % (title, text)
        result = p.edit(section=0, text=text)
        editedpage = result["edit"]["title"]
    else:
        result = p.edit(section="new", summary=title, text=text)
        editedpage = result["edit"]["title"]
    return editedpage


@WikiOperation
def write_page(wiki, page, text):
    p = wikitools.page.Page(wiki, page)
    result = p.edit(text=text)
    editedpage = result["edit"]["title"]
    return editedpage


@WikiOperation
def get_sections(wiki, page):
    p = wikitools.page.Page(wiki, page)
    r = wikitools.api.APIRequest(wiki, {"action": "parse",
                                        "text": p.getWikiText(),
                                        "prop": "sections"})
    result = r.query()
    return [x["line"] for x in result["parse"]["sections"]]


@WikiOperation
def upload_file_to_wiki(wiki, page, filepath):
    p = wikitools.wikifile.File(wiki, page)
    f = file(filepath)
    # ignorewarnings allows us to upload files with same contents as
    # previously uploaded files.
    result = p.upload(f, ignorewarnings=True)
    return result
