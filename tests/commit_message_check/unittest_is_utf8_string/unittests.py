#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message_check import is_utf8_string


class TestIsUtf8String(unittest.TestCase):
    """Test that the is_utf8_string() method behaves correctly.
    """

    def test_non_utf8_string(self):
        """Tests that the method behaves correctly for a string that
        is not UTF-8 encoded.
        """
        non_utf8 = "This string is not UTF-8".encode('utf-16')
        self.assertFalse(is_utf8_string(non_utf8))

    def test_utf8_string(self):
        """Tests that the method behaves correctly for a string that
        is UTF-8 encoded.
        """
        utf8 = unicode("This string is UTF-8")
        self.assertTrue(is_utf8_string(utf8))


if __name__ == '__main__':
    unittest.main()
