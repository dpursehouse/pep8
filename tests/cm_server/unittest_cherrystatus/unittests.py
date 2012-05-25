#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest

from cherry_status import CherrypickStatus


class TestCherrypickStatus(unittest.TestCase):
    """ Test that the CherrypickStatus class works correctly
    """

    def _get_cherry(self):
        ''' Create and return an empty cherry status object.
        '''
        cherry = CherrypickStatus()
        self.assertEquals(cherry.sha1, None)
        self.assertEquals(cherry.project, None)
        self.assertEquals(cherry.branch, None)
        self.assertEquals(cherry.dms, [])
        self.assertEquals(cherry.message, None)
        self.assertEquals(cherry.change_nr, 0)
        self.assertEquals(cherry.review, 0)
        self.assertEquals(cherry.verify, 0)
        self.assertEquals(cherry.status, None)
        self.assertEquals(cherry.dirty, False)
        return cherry

    def test_set_status(self):
        ''' Test that the set_status method works properly.
        '''
        cherry = self._get_cherry()
        cherry.set_status(None)
        self.assertEquals(cherry.status, None)
        self.assertEquals(cherry.dirty, False)
        cherry.set_status("status")
        self.assertEquals(cherry.status, "status")
        self.assertEquals(cherry.dirty, True)

    def test_set_message(self):
        ''' Test that the set_message method works properly.
        '''
        cherry = self._get_cherry()
        cherry.set_message(None)
        self.assertEquals(cherry.message, None)
        self.assertEquals(cherry.dirty, False)
        cherry.set_message("message")
        self.assertEquals(cherry.message, "message")
        self.assertEquals(cherry.dirty, True)

    def test_set_change_nr(self):
        ''' Test that the set_change_nr method works properly.
        '''
        cherry = self._get_cherry()
        cherry.set_change_nr(0)
        self.assertEquals(cherry.change_nr, 0)
        self.assertEquals(cherry.dirty, False)
        cherry.set_change_nr(1)
        self.assertEquals(cherry.change_nr, 1)
        self.assertEquals(cherry.dirty, True)

    def test_set_review(self):
        ''' Test that the set_review method works properly.
        '''
        cherry = self._get_cherry()
        cherry.set_review(0)
        self.assertEquals(cherry.review, 0)
        self.assertEquals(cherry.dirty, False)
        cherry.set_review(1)
        self.assertEquals(cherry.review, 1)
        self.assertEquals(cherry.dirty, True)

    def test_set_verify(self):
        ''' Test that the set_verify method works properly.
        '''
        cherry = self._get_cherry()
        cherry.set_verify(0)
        self.assertEquals(cherry.verify, 0)
        self.assertEquals(cherry.dirty, False)
        cherry.set_verify(1)
        self.assertEquals(cherry.verify, 1)
        self.assertEquals(cherry.dirty, True)

    def test_set_dms(self):
        ''' Test that the set_dms method works properly.
        '''
        cherry = self._get_cherry()
        cherry.set_dms(None)
        self.assertEquals(cherry.dms, [])
        self.assertEquals(cherry.dirty, False)
        cherry.set_dms("DMS00123456")
        self.assertEquals(cherry.dms, ["DMS00123456"])
        self.assertEquals(cherry.dirty, True)
        cherry.set_dms("DMS00123456-DMS00654321")
        self.assertEquals(cherry.dms, ["DMS00123456", "DMS00654321"])
        self.assertEquals(cherry.dirty, True)
        cherry.set_dms(None)
        self.assertEquals(cherry.dms, [])
        self.assertEquals(cherry.dirty, True)

if __name__ == '__main__':
    unittest.main()
