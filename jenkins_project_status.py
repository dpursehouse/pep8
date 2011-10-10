#!/usr/bin/python

#----------------------------------------------------
# jenkins_project_status.py
#
# The purpose of this script is to be able to keep
# track of build status for several Jenkins projects
# on a single wikipage.
#
# Input: Line break separated Jenkins project URLs.
# Output: Wiki formated text.
#----------------------------------------------------

import datetime
import optparse
import re
import socket
import sys
import xml.dom.minidom

import semcutil

ROW_MAX = 50
ROW_MIN = 1
ROW_DEFAULT = 5


def read_data_from_socket(s):
    data = ""
    s.settimeout(2)

    while 1:
        line = ""
        try:
            line = s.recv(1024)
        except socket.timeout:
            break

        if line == "":
            break
        else:
            data += line

    return repr(data)


def make_request(host, port, uri):
    request = "GET %s HTTP/1.1\nHost: %s\n\n" % (uri, host)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.send(request)
    response = read_data_from_socket(s)
    s.close()

    return response


def get_text(nodelist):
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)

    return ''.join(rc)


def trim_xml(xmlinput):
    xmlout = xmlinput[xmlinput.find("<"):xmlinput.rfind(">") + 1]

    # Remove junk-characters from server
    xmlout = re.sub(r"\\r\\n[a-f0-9]+\\r\\n", "", xmlout)

    # Parse xml
    dom = xml.dom.minidom.parseString(xmlout)
    return dom


def get_job_urls(dom, rows):
    urllist = []
    build = dom.getElementsByTagName("build")
    for node in build:
        if(len(urllist) >= rows):
            break
        url = node.getElementsByTagName("url")[0]
        urllist.append(get_text(url.childNodes))

    return urllist


def get_job_status(dom):
    res = {"description": "", "result": "", "number": "", "timestamp": ""}

    subnodes = dom.getElementsByTagName("freeStyleBuild")
    for sub in subnodes:
        res["description"] = get_text((sub.getElementsByTagName
                             ("description")[0]).childNodes)
        res["result"] = get_text((sub.getElementsByTagName
                             ("result")[0]).childNodes)
        res["number"] = get_text((sub.getElementsByTagName
                             ("number")[0]).childNodes)
        res["timestamp"] = get_text((sub.getElementsByTagName
                             ("timestamp")[0]).childNodes)
    return res


def get_result(uri, host):
    resp = make_request(host, 80, uri)
    domtree = trim_xml(resp)
    return get_job_status(domtree)


def produce_wiki_table(host, prj, rows):
    uri = "/view/CM/job/" + prj + "/api/xml"
    response = make_request(host, 80, uri)
    domtree = trim_xml(response)

    print "=" + prj + "="
    print "{| class='wikitable' border='1'"
    print "|-"
    print "! Build nbr !! Timestamp !! Description !! Result"

    for url in get_job_urls(domtree, rows):
        uri = url.replace("http://" + host, "") + "/api/xml"
        res = get_result(uri, host)
        color = "<span style=\"color:#DD0000\">"
        if(res["result"] == "SUCCESS"):
            color = "<span style=\"color:#00DD00\">"
        if(res["result"] == "ABORTED"):
            color = "<span style=\"color:#0000DD\">"
        if(res["result"] == ""):
            color = "<span style=\"color:#FFFFFF\">"
            res["result"] = "-"
        print "|-"

        sys.stdout.write("|[http://%s/view/CM/job/" % host)
        sys.stdout.write("%s/%s/ #%s]\n" % (prj, res["number"], res["number"]))

        timestamp = datetime.datetime.fromtimestamp(
        float(res["timestamp"]) / 1000)

        print "|" + timestamp.ctime()
        print "|" + res["description"]
        print "|" + color + "'''" + res["result"] + "'''" + "</span>"

    print "|}"


def main():
    usage = "usage: %prog [options] < INPUTFILE\n\n" + \
            "Pipe Jenkins project URLs, separated by line breaks, " + \
            "to this script."
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-n", dest="numrows",
            default=ROW_DEFAULT, help="Number of rows to return " \
                "for each project. Range " + str(ROW_MIN) + " - " + \
                str(ROW_MAX) + ". [default: %default]")
    (options, args) = parser.parse_args()

    # Get user preferred number of rows.
    # Default to ROW_DEFAULT silently, we don't want
    # error messages in the wiki output
    try:
        if (int(options.numrows) >= ROW_MIN) \
        and (int(options.numrows) <= ROW_MAX):
            numrows = int(options.numrows)
        else:
            numrows = int(ROW_DEFAULT)
    except:
        numrows = int(ROW_DEFAULT)

    try:
        data = sys.stdin.read()
        string = data.rstrip('\n')
        lines = re.split('\n', string)
        for url in lines:
            host = url[url.find("//") + 2:url.find("/", url.find("//") + 2)]
            project = url[url.rfind("job/") + 4:url.rfind("/")]
            produce_wiki_table(host, project, numrows)
    except socket.error as detail:
        semcutil.fatal(1, "Socket error:" + detail)
    except:
        semcutil.fatal(1, "Unexpected error: " + str(sys.exc_info()[0]))


if __name__ == "__main__":
    main()
