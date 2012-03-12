#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest

from commit_message import CommitMessage


class TestCommitMessage(unittest.TestCase):
    """Test that the CommitMessage class behaves correctly.
    """

    def get_commit_message(self, filename):
        """Open the file specified by `filename` and use its content to create
        a CommitMessage object.  Return the CommitMessage object.
        """
        data = open(os.path.join(os.environ["TESTDIR"], filename))
        return CommitMessage(data.read())

    def test_commit_message_valid(self):
        """Tests that a valid commit message is handled correctly.
        """
        c = self.get_commit_message("commit_message_valid.txt")
        self.assertEqual(c.subject, "Commit message subject")
        self.assertEqual(c.message.split('\n'),
            ["Commit message body line 1",
             "Commit message body line 2"])


if __name__ == '__main__':
    unittest.main()
