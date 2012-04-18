#!/usr/bin/env python

"""Check the availability of debian packages for given package type on c2d
server. If the package is unavailable in specified c2d, it will be
recorded in a file specified with -f option, the default one will be
unavailable_debs.txt.
"""

import logging
from optparse import OptionParser
import os
import threading
import urlparse
from xml.dom import minidom, Node

from debrevision import check_external_debs
import processes
from semcutil import fatal

C2D_MAP = {"CNBJ": "http://androidswrepo-cnbj.sonyericsson.net/",
           "JPTO": "http://androidswrepo-jpto.sonyericsson.net/",
           "SELD": "http://androidswrepo.sonyericsson.net/",
           "USSV": "http://androidswrepo-ussv.sonyericsson.net/"
          }

C2D_PATH = "pool/semc/"
DEFAULT_PACKAGE_TYPE_LIST = ["external-packages", "pld-packages",
                             "decoupled-apps", "installable-apps",
                             "tools-packages", "verification-packages"]
RECORD_FILE = "unavailable_debs.txt"

logging.basicConfig(format="%(message)s", level=logging.INFO)


def get_local_c2d_url():
    c2d_properties = open(os.path.join(os.getenv('HOME'),
                          ".c2d/site.properties")).read()
    import re
    local_site = re.search('.*Site=(.*)', c2d_properties).group(1)
    return C2D_MAP[local_site]


class PackageSyncer(threading.Thread):
    def __init__(self, pkg_name, pkg_version, pkgs_dir, local_c2d_url,
                 remote_c2d_url):
        threading.Thread.__init__(self)
        self.pkg_name = pkg_name
        self.pkg_version = pkg_version
        self._load_cmd = ["repository", "getpackage", "-o", pkgs_dir,
                          self.pkg_name, self.pkg_version, "-ru",
                          remote_c2d_url]
        self._upload_cmd = ["repository", "addpackage", "-ru", local_c2d_url,
                            os.path.join(pkgs_dir, "%s_%s_all.deb" % \
                                (self.pkg_name, self.pkg_version))]

    def run(self):
        try:
            logging.info("Download %s %s", self.pkg_name, self.pkg_version)
            processes.run_cmd(self._load_cmd)
            logging.info("Upload %s %s", self.pkg_name, self.pkg_version)
            processes.run_cmd(self._upload_cmd)
        except processes.ChildRuntimeError, error:
            fatal(1, error)


def sync(deb_list, local_c2d_url, remote_c2d_url, jobs, keep=False):
    import tempfile
    pkgs_dir = tempfile.mkdtemp(prefix="sync_pkgs", dir=os.getcwd())
    threads = []
    jobs = int(jobs)
    for deb in deb_list:
        sync_pkg = PackageSyncer(deb[0], deb[1], pkgs_dir,
                                 local_c2d_url, remote_c2d_url)
        threads.append(sync_pkg)
    for i in range(len(threads)):
        threads[i].start()
        if not i % jobs and i != 0:
            for j in range((i / jobs - 1) * jobs, i):
                threads[j].join()
    for item in threads:
        item.join()
    if not keep:
        import shutil
        shutil.rmtree(pkgs_dir)


def _main():
    # The package types mentioned below are like external-packages pld-packages
    usage = "usage: %prog [options] [package_types]"
    parser = OptionParser(usage=usage)
    parser.add_option("-w", "--workspace", dest="workspace",
                        default=os.getcwd(),
                        help="Set the workspace for checking!")
    parser.add_option("-u", "--local_c2d_url", dest="local_c2d_url",
                        default=get_local_c2d_url(),
                        help="Set the local c2d url")
    parser.add_option("-r", "--remote_c2d", dest="remote_c2d",
                        default="SELD",
                        help=("Set the remote c2d url/site which is the source "
                              "for getting the missed packages"))
    parser.add_option("-f", "--file", dest="file",
                        default=RECORD_FILE,
                        help="Specify the file name for the check result")
    parser.add_option("-s", "--sync", dest="sync", action="store_true",
                        default=False,
                        help="Specify the option to do sync")
    parser.add_option("-j", "--jobs", dest="jobs", default=40,
                        help="Specify the number of sync threads in parallel")
    parser.add_option("-k", "--keep", dest="keep", action="store_true",
                        default=False,
                        help="Specify the option to keep the tmp dir for sync")
    (options, args) = parser.parse_args()
    try:
        if not os.path.isdir(os.path.join(options.workspace, ".repo")):
            fatal(1, "Repo is not installed in %s" % options.workspace)
    except OSError, error:
        fatal(1, error)
    package_type_list = DEFAULT_PACKAGE_TYPE_LIST
    if args:
        package_type_list.extend(args[0:])
    if os.path.exists(options.file):
        try:
            os.remove(options.file)
        except OSError, error:
            fatal(1, "Original record file %s can't be removed: %s" \
                     (record_file, error))
    sync_debs_list = []
    for pkg_type in package_type_list:
        logging.info("=== Begin to check %s ===", pkg_type)
        pkg_path = os.path.join(options.workspace,
                                "vendor/semc/build/",
                                pkg_type, "package-files")
        try:
            xml_files = os.listdir(pkg_path)
        except OSError:
            logging.warning("%s is not available in current workspace!",
                            pkg_type)
            continue
        with open(options.file, "a") as unavailable_debs:
            for xml in xml_files:
                if os.path.splitext(xml)[1] != '.xml':
                    continue
                else:
                    logging.info("** %s **", xml)
                    try:
                        if not options.local_c2d_url.endswith("/"):
                            options.local_c2d_url += "/"
                        unavailable_deb_list = check_external_debs(
                            urlparse.urljoin(options.local_c2d_url, C2D_PATH),
                            os.path.join(pkg_path, xml))
                        sync_debs_list.extend(unavailable_deb_list)
                        if not unavailable_deb_list:
                            logging.info("Pass Check!")
                            continue
                        for deb in unavailable_deb_list:
                            logging.info("%s %s", deb[0], deb[1])
                            unavailable_debs.write("%s %s\n" % (deb[0], deb[1]))
                    except (IOError, processes.ChildRuntimeError), err:
                        fatal(1, err)
    if options.sync and len(sync_debs_list):
        remote_c2d_url = ""
        if options.remote_c2d in C2D_MAP:
            remote_c2d_url = C2D_MAP[options.remote_c2d]
        else:
            remote_c2d_url = options.remote_c2d_url
        logging.info("\nBegin to sync missing packages:")
        sync(sync_debs_list, options.local_c2d_url, remote_c2d_url,
             options.jobs, options.keep)
        logging.info("\nPackages sync done!")
    elif not len(sync_debs_list):
        logging.info("There's no package needed to sync.")
if __name__ == "__main__":
    _main()
