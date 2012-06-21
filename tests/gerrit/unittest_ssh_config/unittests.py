#!/usr/bin/env python
import os
import unittest

from gerrit import _get_config_from_alias as _test_fn

CONFIG_LOWER_CASE = ".ssh_config_lowercase"
CONFIG_UPPER_CASE = ".ssh_config_uppercase"
CONFIG_MIXED_CASE = ".ssh_config_mixedcase"


class TestSshConfigParser(unittest.TestCase):
    ''' Tests that the ssh config parser works properly
    in GerritSshConnection.
    '''

    def _get_config(self, filename):
        return os.path.join(os.environ["TESTDIR"], filename)

    def test_ssh_config(self):
        ''' Test that the config parser works.
        '''
        for t_file in [CONFIG_LOWER_CASE, CONFIG_UPPER_CASE, CONFIG_MIXED_CASE]:
            username, port = _test_fn("testhost.sonyericsson.net",
                                      self._get_config(t_file))
            self.assertEquals(username, "test.user")
            self.assertEquals(port, "12345")

if __name__ == '__main__':
    unittest.main()
