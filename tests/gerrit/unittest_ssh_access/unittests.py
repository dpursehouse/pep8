#!/usr/bin/env python
import unittest

import gerrit


class TestGerritSshConfiguration(unittest.TestCase):
    ''' Tests that the ssh configuration setup works properly
    in GerritSshConnection.
    '''

    def test_default_configuration(self):
        ''' Test that the default setup works (detects ssh hostname
        and port) and can make a connection to run an ssh command.
        '''
        g = gerrit.GerritSshConnection("review.sonyericsson.net")
        g.run_gerrit_command(["ls-projects"])

if __name__ == '__main__':
    unittest.main()
