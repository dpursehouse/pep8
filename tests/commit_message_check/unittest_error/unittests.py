#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message_check import CommitMessageChecker


class TestError(unittest.TestCase):
    """Test that the error() method behaves correctly.
    """

    def test_add_error(self):
        """Tests that errors can be added.
        """
        c = CommitMessageChecker()
        c.error(100, 1)
        self.assertEquals(c.errors, [[1, 100]])
        c.error(200, 2)
        self.assertEquals(c.errors, [[1, 100], [2, 200]])

    def test_add_error_default_line(self):
        """Tests that errors can be added when the line is
        not specified.
        """
        c = CommitMessageChecker()
        c.error(100)
        self.assertEquals(c.errors, [[0, 100]])
        c.error(200, 2)
        self.assertEquals(c.errors, [[0, 100], [2, 200]])

    def test_add_same_error(self):
        """Tests that the same error cannot be added more than
        once on the same line.
        """
        c = CommitMessageChecker()
        c.error(100, 1)
        self.assertEquals(c.errors, [[1, 100]])
        self.assertRaises(ValueError, c.error, 100, 1)

    def test_add_same_error_default_line(self):
        """Tests that the same error cannot be added more than
        once on the same line (default line).
        """
        c = CommitMessageChecker()
        c.error(100)
        self.assertEquals(c.errors, [[0, 100]])
        self.assertRaises(ValueError, c.error, 100)


if __name__ == '__main__':
    unittest.main()
