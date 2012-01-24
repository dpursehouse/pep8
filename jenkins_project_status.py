#!/usr/bin/python

#------------------------------------------------
# jenkins_project_status.py
#
# The purpose of this script is to create wiki
# formatted build history status from a Jenkins
# project.
#
# Input: URL to a Jenkins project.
# Output: Wiki table formatted text.
#------------------------------------------------

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
    try:
        response = make_request(host, 80, uri)
        domtree = trim_xml(response)
    except socket.error:
        semcutil.fatal(1, "Error connecting to URL")
    except:
        semcutil.fatal(1, "Incorrect URL or unparseable response")

    print "=" + prj + "="
    print "{| class='wikitable' border='1'"
    print "|-"
    print "! Build nbr !! Timestamp !! Description !! Result"

    for url in get_job_urls(domtree, rows):
        uri = url.replace("http://" + host, "") + "/api/xml"
        try:
            res = get_result(uri, host)
            timestamp = datetime.datetime.fromtimestamp(
            float(res["timestamp"]) / 1000)
        except socket.error:
            break
        except ValueError:
            break
        except IndexError:
            break

        color = "<span style=\"color:#DD0000\">"
        if(res["result"] == "SUCCESS"):
            color = "<span style=\"color:#00DD00\">"
        if(res["result"] == "ABORTED"):
            color = "<span style=\"color:#0000DD\">"
        if(res["result"] == ""):
            color = "<span style=\"color:#FFFFFF\">"
            res["result"] = "-"
        print "|-"

        print("|[" + url + " #" + res["number"] + "]")

        print "|" + timestamp.ctime()
        print "|" + res["description"]
        print "|" + color + "'''" + res["result"] + "'''" + "</span>"

    print "|}"


def main():
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-n",
                      dest="numrows",
                      default=ROW_DEFAULT,
                      help="number of rows to return " \
                           "for project. Range " + str(ROW_MIN) + " - " + \
                           str(ROW_MAX) + ". [default: %default]")
    parser.add_option("-u",
                      dest="url",
                      default=None, help="HTTP URL to Jenkins build ")
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
        if (not options.url):
            semcutil.fatal(1, "-u option is required")
        url = options.url
        if '\n' in url or ',' in url:
            semcutil.fatal(1, "Only one URL at the same time")
        host = url[url.index("//") + 2:url.index("/", url.index("//") + 2)]
        project = url[url.rindex("job/") + 4:url.rindex("/")]
    except ValueError:
        semcutil.fatal(1, "Incorrect URL")

    produce_wiki_table(host, project, numrows)


if __name__ == "__main__":
    main()
