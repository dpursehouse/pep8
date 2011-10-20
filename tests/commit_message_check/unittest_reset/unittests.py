#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message_check import CommitMessageChecker


class TestReset(unittest.TestCase):
    """Test that the reset() method behaves correctly.
    """

    def test_reset_empty(self):
        """Tests that the method works when there are no errors.
        """
        c = CommitMessageChecker()
        self.assertEquals(c.errors, [])
        c.reset()
        self.assertEquals(c.errors, [])

    def test_reset(self):
        """Tests that the method works when there are no errors.
        """
        c = CommitMessageChecker()
        self.assertEquals(c.errors, [])
        c.error(100)
        self.assertEquals(c.errors, [[0, 100]])
        c.reset()
        self.assertEquals(c.errors, [])


if __name__ == '__main__':
    unittest.main()
