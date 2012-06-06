#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

import commit_message_check
from commit_message import CommitMessage


class TestCheck(unittest.TestCase):
    """Test that the check() method behaves correctly.
    """

    def _error_count(self, error, errors):
        count = 0
        for line, code in errors:
            if code is error:
                count += 1
        return count

    def get_checker(self, filename):
        """Open the file specified by `filename` and use its content to create
        a CommitMessage object, which is in turn used to create a
        CommitMessageChecker object.
        Return the CommitMessageChecker object.
        """
        data = open(os.path.join(os.environ["TESTDIR"], filename))
        c = CommitMessage(data.read())
        return commit_message_check.CommitMessageChecker(c)

    def test_no_commit_message(self):
        """Tests that the method works when there is no commit
        message.
        """
        c = commit_message_check.CommitMessageChecker()
        self.assertRaises(ValueError, c.check)

    def test_valid_commit_message(self):
        """Tests that the method works when there is a valid commit
        message.
        """
        c = self.get_checker("commit_message_valid.txt")
        errors = c.check()
        self.assertEquals(errors, [])

    def test_invalid_commit_message(self):
        """Tests that the method works when there is an invalid commit
        message.
        """
        c = self.get_checker("commit_message_invalid.txt")
        c.commit.message += "\nnot utf-8".encode('utf-16')
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.DMS_IN_TITLE, errors))
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT, errors))
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.SUBJECT_TOO_LONG, errors))
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.DMS_WITHOUT_FIX_TAG, errors))
        self.assertEquals(2, self._error_count(
            commit_message_check.ERROR_CODE.MULTIPLE_DMS_ON_LINE, errors))
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.INVALID_TAG_FORMAT, errors))
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.LINE_TOO_LONG, errors))
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.NON_UTF8_CHARS, errors))


if __name__ == '__main__':
    unittest.main()
