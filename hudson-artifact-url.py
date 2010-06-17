#!/usr/bin/env python

import urllib2
import xml.dom.minidom
import sys
import os.path

def urljoin(first, *rest):
    return "/".join([first.rstrip('/'),
           "/".join([part.lstrip('/') for part in rest])])

def usage(argv):
    print os.path.basename(argv[0]), "URL"
    print "\tURL: url to Hudson job, either with number or a link like lastSuccessful"
    print "\tPrints a list of all the artifact urls for that Hudson job"

def getText(nodelist):
    rc = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc = rc + node.data
    return rc

def getArtifactUrls(url):
    joinedUrl = urljoin(url, "api", "xml")
    try:
        urldata = urllib2.urlopen(joinedUrl)
    except urllib2.HTTPError:
        raise

    jobinfo = xml.dom.minidom.parseString( urldata.read() )
    urllist = []
    for artifact in jobinfo.getElementsByTagName("artifact"):
        for path in artifact.getElementsByTagName("relativePath"):
            urllist.append(urljoin(url, "artifact", getText(path.childNodes)))
    return urllist

def printUrls(url):
    try:
        urllist = getArtifactUrls(url)
    except urllib2.HTTPError, e:
        print e.args
        sys.exit(2)
    for artifact in urllist:
        print artifact

def main(argv=None):
    if argv==None:
        sys.exit(1)
    if len(argv) != 2:
        usage(argv)
        sys.exit(1)
    printUrls(argv[1])

if __name__ == "__main__":
    main(sys.argv)
