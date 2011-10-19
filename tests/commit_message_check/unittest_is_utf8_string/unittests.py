#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message import CommitMessage, CommitMessageError
from commit_message_check import CommitMessageChecker


_TEST_FILE = "commit_message_valid.txt"


class TestIsUtf8String(unittest.TestCase):
    """Test that the is_utf8_string() method behaves correctly.
    """

    def get_checker(self):
        """Open the test commit message and use its content to create
        a CommitMessage object, which is in turn used to create a
        CommitMessageChecker object.
        Return the CommitMessageChecker object.
        """
        data = open(os.path.join(os.environ["TESTDIR"], _TEST_FILE))
        commit_message = CommitMessage(data.read())
        return CommitMessageChecker(commit_message)

    def test_non_utf8_string(self):
        """Tests that the method behaves correctly for a string that
        is not UTF-8 encoded.
        """
        non_utf8 = "This string is not UTF-8".encode('utf-16')
        self.assertFalse(self.get_checker().is_utf8_string(non_utf8))

    def test_utf8_string(self):
        """Tests that the method behaves correctly for a string that
        is UTF-8 encoded.
        """
        utf8 = unicode("This string is UTF-8")
        self.assertTrue(self.get_checker().is_utf8_string(utf8))


if __name__ == '__main__':
    unittest.main()
