#!/usr/bin/env python
'''This script is used for generating decoupled application release notes on
wiki page
'''
import logging
from optparse import OptionParser
import os
import re
import sys

cm_tools = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if cm_tools not in sys.path:
    sys.path.insert(0, cm_tools)

import decoupled_apps_release_notes as decp
from processes import ChildExecutionError
from semcutil import fatal
from wiki import semcwikitools

WIKI = "https://wiki.sonyericsson.net/wiki_androiki/api.php"
GERRIT_SERVER = "review.sonyericsson.net"
DMS_TAG_SERVER = 'android-cm-web.sonyericsson.net'

logging.basicConfig(filename="release_info.log",
                    format="%(message)s",
                    level=logging.INFO,
                    filemode="w")
console = logging.StreamHandler()
logging.getLogger('').addHandler(console)


def coding_conversion(string):
    if not isinstance(string, unicode):
        return unicode(string, "ascii", "ignore")
    else:
        return string


class WikiOutputError(Exception):
    def __init__(self, page, error):
        super(WikiOutputError, self).__init__(page, error)
        self.page = page
        self.error = error

    def __str__(self):
        return "Can't output to wiki %s.\n%s" % (self.page, self.error)


class WikiReleaseNotesOutput(decp.ReleaseNotesOutput):
    '''This class is used to output release notes on wiki.
    '''
    def __init__(self, output_data):
        super(WikiReleaseNotesOutput, self).__init__(output_data)
        self.output_data = output_data

    def output(self, wiki, page, dry_run=False):
        tag = self.output_data["Tag"]
        logging.info("==============%s===============" % tag)
        release_content = ["'''Summary'''<br>"]
        commit_log = ""
        release_content.append(re.sub("\n", "\n<br>",
                               coding_conversion(self.output_data["Summary"])))
        release_content.append("'''Base Branch'''<br>")
        release_content.append("* %s<br>" %
            coding_conversion(self.output_data["Base Branch"]))
        release_content.append("'''Integrated Issues'''<br>")
        dmss = coding_conversion(''.join(["* %s<br>\n" %
            dms for dms in self.output_data["Integrated Issues"]]))
        release_content.append(dmss)
        release_content.append("'''Official Releases Delivered in'''<br><br>")
        release_content.append("'''Release Details'''<br>")
        subpage = "%s/%s" % (page, tag)
        release_content.append("[[%s|%s Release Notes]] <br>" %
            (subpage, tag))
        commit_log = coding_conversion(self.output_data["Release Details"])
        content = coding_conversion('\n'.join(release_content))
        logging.info(content)
        logging.info(commit_log)
        logging.info("Begin to update wiki ...")
        if not dry_run:
            section = "%s(%s)" % (tag, self.output_data['Tag time'])
            try:
                w = semcwikitools.get_wiki(wiki)
                semcwikitools.add_section_to_page(w, page, section, content,
                                                  True)
            except semcwikitools.SemcWikiError, error:
                raise WikiOutputError(page, error)
            section = ("Log between [[%s/%s|%s]] and %s"
                        % (page, self.output_data['Pre_Tag'],
                           self.output_data['Pre_Tag'], tag))
            try:
                if len(commit_log):
                    semcwikitools.add_section_to_page(w, subpage, section,
                                                      commit_log)
                else:
                    semcwikitools.add_section_to_page(w, subpage, section,
                                                      "No changes")
            except semcwikitools.SemcWikiError, error:
                raise WikiOutputError(page, error)
        logging.info("Wiki update finished!")


def _main():
    usage = ("Usage: %prog <-a app_name> <-t tag> <-d git_path> "
             "[-g gerrit_server] [-u user_name] [-s dms_tag_server] "
             "[--dry-run] [-w wiki] [--name-space name_space]")
    parser = OptionParser(usage=usage)
    parser.add_option("-a", "--app", dest="app_name",
                         help=("Specify the decoupled application name, "
                               "this is the name of wiki page. such as Email."))
    parser.add_option("-t", "--tag", dest="tag",
                         help="Specify the tag for decoupled application")
    parser.add_option("-p", "--pre-tag", dest="pre_tag",
                         help="Specify the previous tag")
    parser.add_option("-d", "--git-path", dest="git_path",
                         help="Specify git path")
    parser.add_option("-g", "--gerrit-server", dest="gerrit_server",
                         default=GERRIT_SERVER,
                         help="Specify the gerrit server")
    parser.add_option("-u", "--user-name", dest="user_name",
                         help="Override the user name in gerrit module")
    parser.add_option("-s", "--dms-tag-server", dest="dms_server",
                         default=DMS_TAG_SERVER,
                         help="Specify the dms tag server")
    parser.add_option("--dry-run", dest="dry_run",
                         action="store_true", default=False,
                         help="Specify update wiki or not")
    parser.add_option("-w", "--wiki", dest="wiki",
                         default=WIKI,
                         help="Specify the wiki server")
    parser.add_option("--name-space", dest="name_space",
                         default="Release_Notes",
                         help=("Specify name_space of the wiki page. "
                               "It will be the first level page of a series "
                               "pages. Such as: https://wiki.sonyericsson.net/"
                               "androiki/Release_Notes"))
    (options, args) = parser.parse_args()
    app_name = options.app_name
    if not options.app_name or not options.tag or not options.git_path:
        parser.print_help()
        fatal(1, "Please specify application, tag and git_path!")
    try:
        decoupled_app = decp.DecoupledApp(options.git_path, options.dms_server,
                                          options.gerrit_server, options.tag,
                                          options.pre_tag)
        data_dict = decoupled_app.generate_data()
    except (ChildExecutionError, decp.DataGenerationError), error:
        fatal(1, error)
    wiki_output = WikiReleaseNotesOutput(data_dict)
    page = options.name_space + "/" + app_name
    try:
        wiki_output.output(options.wiki, page, options.dry_run)
    except WikiOutputError, error:
        fatal(1, error)

if __name__ == '__main__':
    _main()
