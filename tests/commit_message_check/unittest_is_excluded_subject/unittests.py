#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

from commit_message_check import CommitMessageChecker


class TestIsExcludedSubject(unittest.TestCase):
    """Test that the is_excluded_subject() method behaves correctly.
    """

    def test_excluded_subjects(self):
        """Tests that the method behaves correctly for subjects that
        are excluded.
        """
        subjects = ["Merge something into something else",
                    "Revert commit xyz",
                    "DO NOT MERGE: this should not be merged",
                    "DO NOT SUBMIT: this should not be submitted",
                    "DON\'T SUBMIT: this should not be submitted"]
        c = CommitMessageChecker()
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
        c = CommitMessageChecker()
        for subject in subjects:
            self.assertFalse(c.is_excluded_subject(subject))


if __name__ == '__main__':
    unittest.main()
