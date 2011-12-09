#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from git import is_sha1, is_tag, is_sha1_or_tag


class TestIsSha1(unittest.TestCase):
    """Test that the is_sha1 method behaves correctly.
    """

    def test_valid_sha1(self):
        """ Test that the method behaves correctly with a valid sha1.
        """
        self.assertTrue(is_sha1("390d268bec042db37dd6d2d813694cc60eb6376c"))

    def test_sha1_invalid_too_short(self):
        """ Test that the method behaves correctly with a sha1 that
        is too short.
        """
        self.assertFalse(is_sha1("390d268bec042db37dd6d2d813694cc60eb6376"))

    def test_sha1_invalid_not_base16(self):
        """ Test that the method behaves correctly with a sha1 that
        is not a valid base16 number.
        """
        self.assertFalse(is_sha1("390d268bec042db37dd6d2d813694cc60eb6376g"))


class TestIsTag(unittest.TestCase):
    """Test that the is_tag method behaves correctly.
    """

    def test_valid_tag(self):
        """ Test that the method behaves correctly with a valid tag.
        """
        self.assertTrue(is_tag("refs/tags/my-tag"))

    def test_not_a_tag(self):
        """ Test that the method behaves correctly with a non-valid tag.
        """
        self.assertFalse(is_tag("refs/heads/my-tag"))

    def test_sha1(self):
        """ Test that the method behaves correctly with a sha1.
        """
        self.assertFalse(is_tag("390d268bec042db37dd6d2d813694cc60eb6376c"))

if __name__ == '__main__':
    unittest.main()
