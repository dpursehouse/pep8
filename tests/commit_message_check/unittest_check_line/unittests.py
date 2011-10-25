#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

import commit_message_check


_LINE_VALID = "This is a valid line"
_LINE_VALID_MAX = "X" * commit_message_check.MAX_LINE_LENGTH
_LINE_INVALID_LONG = "X" * (commit_message_check.MAX_LINE_LENGTH + 1)
_LINE_INVALID_NON_UTF8 = "This is not UTF-8".encode('utf-16')
_LINE_INVALID_TAG = "DMS=DMS00123456"
_LINE_INVALID_ONE_DMS = [ \
    "FIX=DMS00123456 FIX=DMS00654321",
    " FIX=DMS00123456",
    "FIX=DMS00123456 ",
    "Some text FIX=DMS00123456",
    "FIX=DMS00123456 some text"]
_LINE_INVALID_FIX_TAG = [ \
    "FIX = DMS00123456",
    "fix = DMS00123456",
    "Fix = DMS00123456",
    "FIX= DMS00123456",
    "fix= DMS00123456",
    "Fix= DMS00123456",
    "FIX =DMS00123456",
    "fix =DMS00123456",
    "Fix =DMS00123456",
    "FIX:DMS00123456",
    "fix:DMS00123456",
    "Fix:DMS00123456",
    "FIX : DMS00123456",
    "fix : DMS00123456",
    "Fix : DMS00123456",
    "FIX: DMS00123456",
    "fix: DMS00123456",
    "Fix: DMS00123456",
    "FIX :DMS00123456",
    "fix :DMS00123456",
    "Fix :DMS00123456"]


class TestCheckLine(unittest.TestCase):
    """Test that the check_line() method behaves correctly.
    """

    def test_valid(self):
        """Tests that the method behaves correctly when a valid
        line is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_line(_LINE_VALID, 1)
        self.assertEquals(c.errors, [])

    def test_valid_max_length(self):
        """Tests that the method behaves correctly when a valid
        line is passed with max length.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_line(_LINE_VALID_MAX, 1)
        self.assertEquals(c.errors, [])

    def test_invalid_too_long(self):
        """Tests that the method behaves correctly when an invalid
        line (too long) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_line(_LINE_INVALID_LONG, 1)
        self.assertEquals(c.errors,
            [[1, commit_message_check.ERROR_CODE.LINE_TOO_LONG]])

    def test_invalid_non_utf8(self):
        """Tests that the method behaves correctly when an invalid
        line (non utf-8 characters) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_line(_LINE_INVALID_NON_UTF8, 1)
        self.assertEquals(c.errors,
            [[1, commit_message_check.ERROR_CODE.NON_UTF8_CHARS]])

    def test_invalid_tag(self):
        """Tests that the method behaves correctly when an invalid
        line (invalid DMS tag) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        c.check_line(_LINE_INVALID_TAG, 1)
        self.assertEquals(c.errors,
            [[1, commit_message_check.ERROR_CODE.DMS_WITHOUT_FIX_TAG]])

    def test_invalid_not_one_dms(self):
        """Tests that the method behaves correctly when an invalid
        line (DMS tag not on its own line, no whitespace) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        for line in _LINE_INVALID_ONE_DMS:
            c.reset()
            c.check_line(line, 1)
            self.assertEquals(c.errors,
                [[1, commit_message_check.ERROR_CODE.MULTIPLE_DMS_ON_LINE]])

    def test_invalid_fix_tag(self):
        """Tests that the method behaves correctly when an invalid
        line (invalid FIX=) is passed.
        """
        c = commit_message_check.CommitMessageChecker()
        for line in _LINE_INVALID_FIX_TAG:
            c.reset()
            c.check_line(line, 1)
            self.assertEquals(c.errors,
                [[1, commit_message_check.ERROR_CODE.INVALID_TAG_FORMAT]])


if __name__ == '__main__':
    unittest.main()
