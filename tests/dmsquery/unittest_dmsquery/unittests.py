#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import unittest

import processes
from commit_message import CommitMessage


class TestDmsQuery(unittest.TestCase):
    """Test that the dmsquery script behaves correctly.
    """

    def execute_dmsquery(self, inputfile, opts=None):
        """ Call dmsquery with `opts` using the commit message found
        in the file specified by `inputfile`.
        """
        data = open(os.path.join(os.environ["TESTDIR"], inputfile))
        c = CommitMessage(data.read())

        params = ["./dmsquery", "--show"]
        if opts:
            params += opts

        return processes.run_cmd(params, input=c.message)

    def test_no_dms(self):
        """Tests that when calling dmsquery on a commit message with no DMS,
        without specifying quiet mode, it returns an error message.
        """
        errcode, rawlist, err = self.execute_dmsquery(
            inputfile="commit_message_no_dms.txt")
        m = re.search("No DMS Issues found", err)
        self.assertEqual(m.group(0), "No DMS Issues found")

    def test_no_dms_quiet_mode(self):
        """Tests that when calling dmsquery on a commit message with no DMS,
        while specifying quiet mode, it does not return an error message.
        """
        errcode, rawlist, err = self.execute_dmsquery(
            inputfile="commit_message_no_dms.txt",
            opts=["--quiet"])
        issuelist = [s.strip() for s in rawlist.splitlines()]
        self.assertEqual(issuelist, [])
        self.assertEqual(err, "")

    def test_multiple_valid_dms(self):
        """Tests that when calling dmsquery on a commit message that
        includes multiple valid DMS, it returns a list of all the valid
        DMS and no error code or message.
        """
        errcode, rawlist, err = self.execute_dmsquery(
            inputfile="commit_message_with_dms.txt")
        issuelist = [s.strip() for s in rawlist.splitlines()]
        self.assertEqual(issuelist, ["DMS00111111", "DMS00222222",
                                     "DMS00333333"])
        self.assertEqual(err, "")
        self.assertEqual(errcode, 0)

if __name__ == '__main__':
    unittest.main()
