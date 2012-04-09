#!/usr/bin/env python

"""Check the availability of debian packages for given package type on c2d
server. If the package is unavailable in specified c2d, it will be
recorded in a file specified with -f option, the default one will be
unavailable_debs.txt.
"""

import logging
from optparse import OptionParser
import os
import urlparse
from xml.dom import minidom, Node

from debrevision import check_external_debs, OpenC2DPageError
import processes
from semcutil import fatal

C2D_URL = "http://androidswrepo-cnbj.sonyericsson.net/"
C2D_PATH = "pool/semc/"
DEFAULT_PACKAGE_TYPE_LIST = ["external-packages", "pld-packages",
                             "decoupled-apps", "installable-apps",
                             "tools-packages", "verification-packages"]
RECORD_FILE = "unavailable_debs.txt"


def _main():
    # The package types mentioned below are like external-packages pld-packages
    usage = "usage: %prog [options] [package_types]"
    parser = OptionParser(usage=usage)
    parser.add_option("-w", "--workspace", dest="workspace",
                        default=os.getcwd(),
                        help="Set the workspace for checking!")
    parser.add_option("-u", "--c2d_url", dest="c2d_url",
                        default=C2D_URL,
                        help="Set the local c2d url")
    parser.add_option("-f", "--file", dest="file",
                        default=RECORD_FILE,
                        help="Specify the file name for the check result")
    (options, args) = parser.parse_args()
    try:
        if not os.path.isdir(os.path.join(options.workspace, ".repo")):
            fatal(1, "Repo is not installed in %s" % options.workspace)
    except OSError, error:
        fatal(1, error)
    c2d_url = urlparse.urljoin(options.c2d_url, C2D_PATH)
    package_type_list = DEFAULT_PACKAGE_TYPE_LIST
    logging.basicConfig(format="%(message)s", level=logging.INFO)
    if args:
        package_type_list.extend(args[0:])
    if os.path.exists(options.file):
        try:
            os.remove(options.file)
        except OSError, error:
            fatal(1, "Original record file %s can't be removed: %s" \
                     (record_file, error))
    for pkg_type in package_type_list:
        logging.info("=== Begin to check %s ===", pkg_type)
        pkg_path = os.path.join(options.workspace,
                                "vendor/semc/build/",
                                pkg_type, "package-files")
        try:
            xml_files = os.listdir(pkg_path)
        except OSError:
            logging.warning("%s is not available in current platform!",
                            pkg_type)
            continue
        with open(options.file, "a") as unavailable_debs:
            for xml in xml_files:
                if os.path.splitext(xml)[1] != '.xml':
                    continue
                else:
                    logging.info("** %s **", xml)
                    try:
                        unavailable_deb_list = check_external_debs(c2d_url,
                            os.path.join(pkg_path, xml))
                        if not unavailable_deb_list:
                            logging.info("Pass Check!")
                            continue
                        for deb in unavailable_deb_list:
                            logging.info(deb)
                            unavailable_debs.write("%s\n" % deb)
                    except (IOError, OpenC2DPageError), err:
                        fatal(1, err)

if __name__ == "__main__":
    _main()
