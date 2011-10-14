#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message import CommitMessage, CommitMessageError


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
        data = \
            self.get_fixed_issues("commit_message_including_malformed_dms.txt")
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
