#!/usr/bin/env python
'''This script is used for generating decoupled application release notes
'''

import os
import re
import sys

cm_tools = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if cm_tools not in sys.path:
    sys.path.insert(0, cm_tools)

import debrevision
from dmsutil import DMSTagServer, DMSTagServerError
from gerrit import GerritSshConfigError, GerritSshConnection, GerritQueryError
from git import GitRepository
import map_tag_branch
from processes import ChildExecutionError


class DataGenerationError(Exception):
    def __init__(self, tag, error):
        super(DataGenerationError, self).__init__(tag, error)
        self.error = error
        self.tag = tag

    def __str__(self):
        return ("Can't generate data for release notes of %s.\n%s" %
                                             (self.tag, self.error))


class DecoupledApp:
    '''This class is used to generate data struct for release output.
    It may raise ChildExecutionError when git command execution failed.
    '''

    def __init__(self, git_path, dms_server, gerrit_server, tag, pre_tag=None):
        self.git_path = git_path
        self.dms_server = dms_server
        self.gerrit_server = gerrit_server
        self.tag = tag
        self.pre_tag = pre_tag
        self.git = GitRepository(git_path)
        tag_info = self.git.run_cmd(["cat-file", "-p", self.tag])[1]
        pattern = re.compile("tagger .*> (.*)")
        self.tag_time = pattern.search(tag_info).group(1)
        self.tag_message = tag_info[tag_info.find('\n\n') + 2:]

        if pre_tag:
            revision = "%s..%s" % (pre_tag, tag)
        else:
            revision = self.tag
        self.full_log = self.git.run_cmd(["log", "--no-merges", revision])[1]

    def get_dms_info(self):
        '''Get the dms information.
        It may raise DMSTagServerError if getting dms with title via dms server
        failed.
        '''
        dms_list = []
        log_lines = self.full_log.split("\n")
        dms_server = DMSTagServer(self.dms_server)
        for line in log_lines:
            if re.match(r'^\s*?FIX\s*=\s*DMS[0-9]+', line):
                dms_list.append(line.split("=")[1].strip())
        return dms_server.dms_with_title(dms_list)

    def get_base_branch(self, gerrit_conn):
        '''Get the base branch name to which the tagged issue is delivered.
        It may raise ChildExcutionError or GerritQueryError if get_branch
        failed
        '''
        return map_tag_branch.get_branch(gerrit_conn, self.git.working_dir,
                                         self.tag)

    def generate_data(self):
        '''Store the release information into a dictionary.
        It may raise ChildExecutionError if get_base_branch failed, and may
        raise GerritQueryError if getting gerrit connection failed.
        '''
        data_dict = {}
        data_dict['Tag'] = self.tag
        data_dict['Pre_Tag'] = self.pre_tag
        data_dict['Summary'] = self.tag_message
        data_dict['Tag time'] = self.tag_time
        try:
            conn_obj = GerritSshConnection(self.gerrit_server)
            data_dict['Base Branch'] = self.get_base_branch(conn_obj)
            data_dict['Integrated Issues'] = self.get_dms_info()
        except (ChildExecutionError, GerritQueryError, GerritSshConfigError,
            DMSTagServerError), error:
            raise DataGenerationError(self.tag, error)
        data_dict['Official Releases Delivered in'] = ''
        data_dict['Release Details'] = self.full_log
        return data_dict


class ReleaseNotesOutput(object):
    '''This class is a base class used to generate output in a specified format.
    output_data is a dictionary containing the release information
    '''
    def __init__(self, output_data):
        self.output_data = output_data

    def output(self):
        print self.output_data
