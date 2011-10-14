#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message import CommitMessage, CommitMessageError


class TestCommitMessage(unittest.TestCase):
    """Test that the CommitMessage and CommitMessageAuthor
    classes behave correctly.
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
        self.assertEqual(c.author.type, "author")
        self.assertEqual(c.author.name, "Author Name")
        self.assertEqual(c.author.email, "author.name@sonyericsson.com")
        self.assertEqual(c.author.timestamp, "1318317148 +0900")
        self.assertEqual(c.committer.type, "committer")
        self.assertEqual(c.committer.name, "Committer Name")
        self.assertEqual(c.committer.email, "committer.name@sonyericsson.com")
        self.assertEqual(c.committer.timestamp, "1318317148 +0900")

    def test_commit_message_missing_header_parts(self):
        """Tests that a commit message missing one of the parts in the
        header is handled correctly.
        """
        self.assertRaises(CommitMessageError, self.get_commit_message,
            "commit_message_invalid_missing_header_author.txt")
        self.assertRaises(CommitMessageError, self.get_commit_message,
            "commit_message_invalid_missing_header_committer.txt")
        self.assertRaises(CommitMessageError, self.get_commit_message,
            "commit_message_invalid_missing_header_tree.txt")
        self.assertRaises(CommitMessageError, self.get_commit_message,
            "commit_message_invalid_missing_header_parent.txt")

    def test_commit_message_invalid_header_part(self):
        """Tests that a commit message with an invalid part in the
        header is handled correctly.
        """
        self.assertRaises(CommitMessageError, self.get_commit_message,
            "commit_message_invalid_header.txt")
        self.assertRaises(CommitMessageError, self.get_commit_message,
            "commit_message_invalid_header_author.txt")
        self.assertRaises(CommitMessageError, self.get_commit_message,
            "commit_message_invalid_header_committer.txt")

    def test_commit_message_invalid_header_repeated(self):
        """Tests that a commit message with repeated part in the
        header is handled correctly.
        """
        self.assertRaises(CommitMessageError, self.get_commit_message,
            "commit_message_invalid_header_repeated.txt")


if __name__ == '__main__':
    unittest.main()
