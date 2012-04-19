#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest

from cm_server import get_credentials_from_netrc, CredentialsError


class TestNetRC(unittest.TestCase):
    """ Test that the .netrc functionality works correctly
    """

    def _get_credentials_from_netrc(self, server, filename):
        _filename = os.path.join(os.environ["TESTDIR"], filename)
        return get_credentials_from_netrc(server, _filename)

    def test_valid_netrc(self):
        """ Test that the get_credentials_from_netrc method returns
        correct values when the .netrc file is valid.
        """
        user, pwd = self._get_credentials_from_netrc("server1",
                                                     "netrc_valid.txt")
        self.assertEquals(user, "user1")
        self.assertEquals(pwd, "password1")

        user, pwd = self._get_credentials_from_netrc("server2",
                                                     "netrc_valid.txt")
        self.assertEquals(user, "user2")
        self.assertEquals(pwd, "password2")

        user, pwd = self._get_credentials_from_netrc("server3",
                                                     "netrc_valid.txt")
        self.assertEquals(user, "")
        self.assertEquals(pwd, "")

    def test_non_existent_netrc_file(self):
        """ Test that the get_credentials_from_netrc method raises an
        exception when the given .netrc filename does not exist.
        """
        def f():
            get_credentials_from_netrc("server", "does_not_exist.txt")
        self.assertRaises(CredentialsError, f)

    def test_invalid_netrc(self):
        """ Test that the get_credentials_from_netrc method raises an
        exception when the given .netrc file is invalid and cannot be
        parsed.
        """
        def f():
            user, pwd = self._get_credentials_from_netrc("server2",
                                                         "netrc_invalid.txt")
        self.assertRaises(CredentialsError, f)

if __name__ == '__main__':
    unittest.main()
