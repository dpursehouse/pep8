#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message import CommitMessage, _sanitise_string


class TestGetFixedIssues(unittest.TestCase):
    """Test that the get_fixed_issues() function behaves correctly.
    """

    def get_fixed_issues(self, filename):
        """Open the file specified by `filename` and use its content to create
        a CommitMessage object.  Return the list of issues in the commit
        message.
        """
        data = open(os.path.join(os.environ["TESTDIR"], filename))
        c = CommitMessage(data.read())
        return c.get_fixed_issues()

    def test_sanitize_string(self):
        """Tests that the _sanitise_string method correctly removes
        non-ascii characters from the given string.
        """
        s = _sanitise_string("test" + "ö" + "test")
        self.assertEquals(s, "testtest")
        s = _sanitise_string("test" + "test")
        self.assertEquals(s, "testtest")

    def test_changed_directory_in_tools_path(self):
        """Tests that the get_fixed_issues method works correctly when
        the caller has changed the current working directory, and the
        cm_tools directory is still in the path of the cwd.
        """
        cwd = os.getcwd()
        test_dir = os.environ["TESTDIR"]
        self.assertTrue(os.path.isdir(test_dir))
        os.chdir(test_dir)
        data = self.get_fixed_issues("commit_message_single_valid_dms.txt")
        self.assertEqual(data, ["DMS00123456"])
        os.chdir(cwd)

    def test_changed_directory_not_in_tools_path(self):
        """Tests that the get_fixed_issues method works correctly when
        the caller has changed the current working directory, and the
        cm_tools directory is not in the path of the cwd.
        """
        cwd = os.getcwd()
        os.chdir("/")
        data = self.get_fixed_issues("commit_message_single_valid_dms.txt")
        self.assertEqual(data, ["DMS00123456"])
        os.chdir(cwd)

    def test_no_dms(self):
        """Tests that attempting to get DMS from a commit message that
        does not contain any DMS returns an empty list.
        """
        data = self.get_fixed_issues("commit_message_no_dms.txt")
        self.assertEqual(data, [])

    def test_only_malformed_dms(self):
        """Tests that attempting to get DMS from a commit message that
        only contains malformed DMS returns an empty list.
        """
        data = self.get_fixed_issues("commit_message_only_malformed_dms.txt")
        self.assertEqual(data, [])

    def test_including_malformed_dms(self):
        """Tests that attempting to get DMS from a commit message that
        includes malformed DMS returns a list only containing the valid
        DMS.
        """
        data = self.get_fixed_issues(
            "commit_message_including_malformed_dms.txt")
        self.assertEqual(data, ["DMS00654321"])

    def test_single_valid_dms(self):
        """Tests that attempting to get DMS from a commit message that
        includes a single valid DMS returns a list only containing the valid
        DMS.
        """
        data = self.get_fixed_issues("commit_message_single_valid_dms.txt")
        self.assertEqual(data, ["DMS00123456"])

    def test_multiple_valid_dms(self):
        """Tests that attempting to get DMS from a commit message that
        includes multiple valid DMS returns a list of all the valid
        DMS.
        """
        data = self.get_fixed_issues("commit_message_multiple_valid_dms.txt")
        self.assertEqual(data, ["DMS00123456", "DMS00654321"])

    def test_repeated_valid_dms(self):
        """Tests that attempting to get DMS from a commit message that
        includes the same DMS multiple times returns a list containing
        only one instance of the valid DMS.
        """
        data = self.get_fixed_issues("commit_message_repeated_valid_dms.txt")
        self.assertEqual(data, ["DMS00123456"])

if __name__ == '__main__':
    unittest.main()
