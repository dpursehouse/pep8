#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from gerrit import get_patchset_refspec


class TestGetPatchsetRefspec(unittest.TestCase):
    """ Test that the get_patchset_refspec method behaves correctly.
    """

    def test_get_patchset_refspec(self):
        self.assertEquals("refs/changes/45/12345/1",
                          get_patchset_refspec(12345, 1))
        self.assertEquals("refs/changes/45/12345/10",
                          get_patchset_refspec(12345, 10))
        self.assertEquals("refs/changes/01/12301/1",
                          get_patchset_refspec(12301, 1))
        self.assertEquals("refs/changes/01/12301/1",
                          get_patchset_refspec("12301", "1"))

if __name__ == '__main__':
    unittest.main()
