#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message import CommitMessage, CommitMessageError
from commit_message_check import CommitMessageChecker


_TEST_FILE = "commit_message_valid.txt"


class TestIsExcludedSubject(unittest.TestCase):
    """Test that the is_excluded_subject() method behaves correctly.
    """

    def get_checker(self):
        """Open the test commit message and use its content to create
        a CommitMessage object, which is in turn used to create a
        CommitMessageChecker object.
        Return the CommitMessageChecker object.
        """
        data = open(os.path.join(os.environ["TESTDIR"], _TEST_FILE))
        commit_message = CommitMessage(data.read())
        return CommitMessageChecker(commit_message)

    def test_excluded_subjects(self):
        """Tests that the method behaves correctly for subjects that
        are excluded.
        """
        subjects = ["Merge something into something else",
                    "Revert commit xyz",
                    "DO NOT MERGE: this should not be merged",
                    "DO NOT SUBMIT: this should not be submitted",
                    "DON\'T SUBMIT: this should not be submitted"]
        c = self.get_checker()
        for subject in subjects:
            self.assertTrue(c.is_excluded_subject(subject))

    def test_non_excluded_subjects(self):
        """Tests that the method behaves correctly for subjects that
        are not excluded.
        """
        subjects = ["Fix the foo in the bar when baz",
                    "Update the whizzbang",
                    "Wenn ist das Nunstück git und Slotermeyer?",
                    "Ja! Beiherhund das Oder die Flipperwaldt gersput!",
                    "DON\'T MERGE: this should not be merged"]
        c = self.get_checker()
        for subject in subjects:
            self.assertFalse(c.is_excluded_subject(subject))


if __name__ == '__main__':
    unittest.main()
