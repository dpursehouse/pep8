#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from cherry_update import _calculate_score
from cm_server import CherrypickStatusError


class TestCalculateScore(unittest.TestCase):
    """Test that the _calculate_score method behaves correctly.
    """

    def test_valid_scores(self):
        """Tests that the method behaves correctly with valid data.
        """
        self.assertEquals(1, _calculate_score([1], -1))
        self.assertEquals(1, _calculate_score([1, 1], -1))
        self.assertEquals(-1, _calculate_score([1, -1], -1))
        self.assertEquals(-1, _calculate_score([1, -1], -2))
        self.assertEquals(-2, _calculate_score([1, -2], -2))
        self.assertEquals(2, _calculate_score([1, -1, 2], -2))
        self.assertEquals(-2, _calculate_score([1, 2, -2], -2))
        self.assertEquals(-1, _calculate_score([-1, -1], -2))

    def test_invalid_scores(self):
        """Tests that the method behaves correctly with invalid data.
        """
        self.assertRaises(CherrypickStatusError, _calculate_score, [2], -1)
        self.assertRaises(CherrypickStatusError, _calculate_score, [-2], -1)
        self.assertRaises(CherrypickStatusError, _calculate_score, [0, 1], -1)
        self.assertEquals(0, _calculate_score([], -2))
        self.assertEquals(0, _calculate_score([], -1))


if __name__ == '__main__':
    unittest.main()
