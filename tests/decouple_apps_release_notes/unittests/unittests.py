#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
from processes import run_cmd, ChildExecutionError, ChildRuntimeError
import unittest

from decoupled.decoupled_apps_release_notes import DecoupledApp
from gerrit import GerritSshConnection

TEMP_DIR = "/tmp/decoupled_unittest"
GIT_PATH = "git://review.sonyericsson.net/platform/vendor/semc/packages/" + \
    "apps/conversations"
DMS_SERVER = "android-cm-web.sonyericsson.net"
GERRIT_SERVER = "review.sonyericsson.net"
_SUMMARY = '''ics-fuji-r2 bring up.

1. Add white theme, and set it as default.
2. Adapt AT&T requirement in the generic apk.
3. Adjust theme.
4. Fix monkey crash in ConversationActivity.java
5. Set theme for location editor activity.
6. Fix save draft issues for AT&T CDF.
Rebase done.

FIX=DMS01168051
'''
_DMS = '''DMS01168051 UI and function should update when Holo Theme delivered
'''
TAG = "6.0.A.1.9"
PRE_TAG = "6.0.A.1.8"


class TestDecoupledApp(unittest.TestCase):
    """ Test that the DecoupledApp data class behaves correctly
    """

    def setUp(self):
        if os.path.isdir(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        command = ['git', 'clone', GIT_PATH, TEMP_DIR]
        run_cmd(command)

    def test_initialize_data(self):
        decoupled = DecoupledApp(TEMP_DIR, DMS_SERVER, GERRIT_SERVER, TAG,
                                 PRE_TAG)
        self.assertEqual(decoupled.tag_time,
                         "Thu Mar 1 09:09:22 2012 +0800")
        self.assertEqual(decoupled.tag_message, _SUMMARY)

    def test_get_base_branch(self):
        decoupled = DecoupledApp(TEMP_DIR, DMS_SERVER, GERRIT_SERVER, TAG,
                                 PRE_TAG)
        conn_obj = GerritSshConnection(GERRIT_SERVER)
        base_branch = decoupled.get_base_branch(conn_obj)
        self.assertEqual(base_branch, "master")

    def test_get_dms_info(self):
        decoupled = DecoupledApp(TEMP_DIR, DMS_SERVER, GERRIT_SERVER, TAG,
                                 PRE_TAG)
        self.assertEqual('\n'.join([dms.strip() \
            for dms in decoupled.get_dms_info()]),  _DMS.strip())

if __name__ == '__main__':
    unittest.main()
