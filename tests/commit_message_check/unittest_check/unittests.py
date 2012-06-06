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

    def test_valid_commit_message_conflicts(self):
        """Tests that the method works when there is a valid commit
        message with conflicts section.
        """
        c = self.get_checker("commit_message_valid_conflicts.txt")
        errors = c.check()
        self.assertEquals(errors, [])

    def test_valid_commit_message_conflicts_no_newline(self):
        """Tests that the method works when there is a valid commit
        message with conflicts section, and the conflicts section is at the
        end of the commit message.
        """
        c = self.get_checker("commit_message_valid_conflicts_no_newline.txt")
        errors = c.check()
        self.assertEquals(errors, [])

    def test_invalid_commit_message_multi_conflicts(self):
        """Tests that the method works when there is a commit
        message with multiple conflicts sections.
        """
        c = self.get_checker("commit_message_invalid_multi_conflicts.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.MULTIPLE_CONFLICTS_SECTIONS,
            errors))

    def test_invalid_commit_message(self):
        """Tests that the method works when there is an invalid commit
        message.
        """
        for testfile in ["commit_message_invalid.txt",
                         "commit_message_invalid1.txt"]:
            c = self.get_checker(testfile)
            c.commit.message += "\n" + "not utf-8".encode('utf-16')
            errors = c.check()
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.DMS_IN_TITLE, errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT,
                errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.SUBJECT_TOO_LONG, errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.DMS_WITHOUT_FIX_TAG, errors))
            self.assertEquals(2, self._error_count(
                commit_message_check.ERROR_CODE.MULTIPLE_DMS_ON_LINE, errors))
            self.assertEquals(2, self._error_count(
                commit_message_check.ERROR_CODE.INVALID_TAG_FORMAT, errors))
            self.assertEquals(2, self._error_count(
                commit_message_check.ERROR_CODE.LINE_TOO_LONG, errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.NON_UTF8_CHARS, errors))
            self.assertEquals(0, self._error_count(
                commit_message_check.ERROR_CODE.MULTIPLE_CONFLICTS_SECTIONS,
                errors))


if __name__ == '__main__':
    unittest.main()
