#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

import commit_message_check


_SUBJECT_LINE_VALID = "This is a valid subject line"
_SUBJECT_LINE_VALID_MAX = "X" * commit_message_check.MAX_SUBJECT_LENGTH
_SUBJECT_LINE_INVALID_LONG = "X" * \
                             (commit_message_check.MAX_SUBJECT_LENGTH + 1)
_SUBJECT_LINE_INVALID_MULTI = "This is an invalid\nsubject line"
_SUBJECT_LINE_INVALID_MULTI_LONG = _SUBJECT_LINE_INVALID_LONG + "\n" + \
                                   _SUBJECT_LINE_INVALID_LONG
_SUBJECT_LINE_INVALID_DMS = "Mentioning DMS00123456 in the title"
_SUBJECT_LINE_INVALID_LONG_DMS = _SUBJECT_LINE_INVALID_LONG + "DMS00123456"
_SUBJECT_LINE_INVALID_MULTI_DMS = _SUBJECT_LINE_INVALID_MULTI + "DMS00123456"
_SUBJECT_LINE_INVALID_NON_UTF8 = "This is not UTF-8".encode('utf-16')


class TestCheckSubject(unittest.TestCase):
    """Test that the check_subject() method behaves correctly.
    """

    def test_valid(self):
        """Tests that the method behaves correctly when a valid
        subject line is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_VALID)
        self.assertEquals(c.errors, [])

    def test_valid_max_length(self):
        """Tests that the method behaves correctly when a valid
        subject line is passed with max length.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_VALID_MAX)
        self.assertEquals(c.errors, [])

    def test_invalid_too_long(self):
        """Tests that the method behaves correctly when an invalid
        subject line (too long) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_INVALID_LONG)
        self.assertEquals(c.errors,
            [[0, commit_message_check.ERROR_CODE.SUBJECT_TOO_LONG]])

    def test_invalid_multi_line(self):
        """Tests that the method behaves correctly when an invalid
        subject line (multiple lines) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_INVALID_MULTI)
        self.assertEquals(c.errors,
            [[0, commit_message_check.ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT]])

    def test_invalid_multi_line_too_long(self):
        """Tests that the method behaves correctly when an invalid
        subject line (multiple lines) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_INVALID_MULTI_LONG)
        self.assertEquals(c.errors,
            [[0, commit_message_check.ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT],
             [0, commit_message_check.ERROR_CODE.SUBJECT_TOO_LONG]])

    def test_invalid_dms(self):
        """Tests that the method behaves correctly when an invalid
        subject line (DMS mentioned) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_INVALID_DMS)
        self.assertEquals(c.errors,
            [[0, commit_message_check.ERROR_CODE.DMS_IN_TITLE]])

    def test_invalid_too_long_dms(self):
        """Tests that the method behaves correctly when an invalid
        subject line (too long and DMS mentioned) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_INVALID_LONG_DMS)
        self.assertEquals(c.errors,
            [[0, commit_message_check.ERROR_CODE.DMS_IN_TITLE],
             [0, commit_message_check.ERROR_CODE.SUBJECT_TOO_LONG]])

    def test_invalid_multi_line_dms(self):
        """Tests that the method behaves correctly when an invalid
        subject line (multiple lines and DMS mentioned) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_INVALID_MULTI_DMS)
        self.assertEquals(c.errors,
            [[0, commit_message_check.ERROR_CODE.DMS_IN_TITLE],
             [0, commit_message_check.ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT]])

    def test_invalid_non_utf8(self):
        """Tests that the method behaves correctly when an invalid
        line (non utf-8 characters) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_subject(_SUBJECT_LINE_INVALID_NON_UTF8)
        self.assertEquals(c.errors,
            [[0, commit_message_check.ERROR_CODE.NON_UTF8_CHARS]])


if __name__ == '__main__':
    unittest.main()
