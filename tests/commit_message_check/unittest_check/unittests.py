#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest

import commit_message_check
from commit_message import CommitMessage


class TestCheck(unittest.TestCase):
    """Test that the check() method behaves correctly.
    """

    def _error_count(self, error, errors):
        count = 0
        for line, code in errors:
            if code is error:
                count += 1
        return count

    def get_checker(self, filename, require_category=False):
        """Open the file specified by `filename` and use its content to create
        a CommitMessage object, which is in turn used to create a
        CommitMessageChecker object.
        Return the CommitMessageChecker object.
        """
        data = open(os.path.join(os.environ["TESTDIR"], filename))
        c = CommitMessage(data.read())
        return commit_message_check.CommitMessageChecker(c, require_category)

    def test_no_commit_message(self):
        """Tests that the method works when there is no commit
        message.
        """
        c = commit_message_check.CommitMessageChecker()
        self.assertRaises(ValueError, c.check)

    def test_valid_commit_message(self):
        """Tests that the method works when there is a valid commit
        message.
        """
        c = self.get_checker("commit_message_valid.txt")
        errors = c.check()
        self.assertEquals(errors, [])
        self.assertEquals(c.category, "development")
        self.assertEquals(c.feature_id, [])

    def test_valid_commit_message_feature_category(self):
        """Tests that the method works when there is a valid commit
        message with feature ID.
        """
        c = self.get_checker("commit_message_valid_feature_category.txt")
        errors = c.check()
        self.assertEquals(errors, [])
        self.assertEquals(c.category, "feature")
        self.assertEquals(c.feature_id, ["FP1234", "FP12345", "FP123456"])

    def test_valid_commit_message_conflicts(self):
        """Tests that the method works when there is a valid commit
        message with conflicts section.
        """
        c = self.get_checker("commit_message_valid_conflicts.txt")
        errors = c.check()
        self.assertEquals(errors, [])

    def test_valid_commit_message_conflicts_no_newline(self):
        """Tests that the method works when there is a valid commit
        message with conflicts section, and the conflicts section is at the
        end of the commit message.
        """
        c = self.get_checker("commit_message_valid_conflicts_no_newline.txt")
        errors = c.check()
        self.assertEquals(errors, [])

    def test_invalid_commit_message_multi_conflicts(self):
        """Tests that the method works when there is a commit
        message with multiple conflicts sections.
        """
        c = self.get_checker("commit_message_invalid_multi_conflicts.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.MULTIPLE_CONFLICTS_SECTIONS,
            errors))

    def test_invalid_commit_message_multi_categories(self):
        """Tests that the method works when there is a commit
        message with multiple category sections.
        """
        c = self.get_checker("commit_message_invalid_multi_categories.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.MULTIPLE_CATEGORIES,
            errors))
        self.assertEquals(c.category, "development")

    def test_invalid_commit_message_missing_feature_id(self):
        """Tests that the method works when there is a commit
        message with category "feature" but no feature ID.
        """
        c = self.get_checker("commit_message_invalid_missing_feature_id.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.MISSING_FEATURE_ID,
            errors))
        self.assertEquals(c.category, "feature")
        self.assertEquals(c.feature_id, [])

    def test_invalid_commit_message_missing_feature_category(self):
        """Tests that the method works when there is a commit
        message with feature ID but no category.
        """
        c = self.get_checker("commit_message_invalid_missing_feature_cat.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.FEATURE_ID_BUT_NO_CATEGORY,
            errors))
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.FEATURE_BEFORE_CATEGORY,
            errors))
        self.assertEquals(c.category, None)
        self.assertEquals(c.feature_id, ["FP1234"])

    def test_invalid_commit_message_multi_feature_id(self):
        """Tests that the method works when there is a commit
        message with multiple feature ID tags.
        """
        c = self.get_checker("commit_message_invalid_multi_feature.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.MULTIPLE_FEATURE_TAGS,
            errors))
        self.assertEquals(c.category, "feature")
        self.assertEquals(c.feature_id, ["FP1234"])

    def test_invalid_commit_message_feature_before_category(self):
        """Tests that the method works when there is a commit
        message with feature ID specified before the category.
        """
        c = self.get_checker("commit_message_invalid_feature_before_cat.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.FEATURE_BEFORE_CATEGORY,
            errors))
        self.assertEquals(c.category, "feature")
        self.assertEquals(c.feature_id, ["FP1234"])

    def test_invalid_commit_message_feature_wrong_category(self):
        """Tests that the method works when there is a commit
        message with feature ID specified but the category is not 'feature'.
        """
        c = self.get_checker("commit_message_invalid_feature_wrong_cat.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.FEATURE_ID_BUT_NOT_FEATURE_CATEGORY,
            errors))
        self.assertEquals(c.category, "development")
        self.assertEquals(c.feature_id, ["FP1234"])

    def test_invalid_commit_message_invalid_category(self):
        """Tests that the method works when there is a commit
        message an invalid category.
        """
        c = self.get_checker("commit_message_invalid_category.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.INVALID_CATEGORY,
            errors))
        self.assertEquals(c.category, None)

    def test_invalid_commit_message_invalid_category_tag(self):
        """Tests that the method works when there is a commit
        message an invalid category tag.
        """
        c = self.get_checker("commit_message_invalid_category_tag.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.INVALID_CATEGORY_TAG,
            errors))
        self.assertEquals(c.category, None)

    def test_invalid_commit_message_invalid_feature_tag(self):
        """Tests that the method works when there is a commit
        message an invalid feature ID tag.
        """
        c = self.get_checker("commit_message_invalid_feature_tag.txt")
        errors = c.check()
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.INVALID_FEATURE_TAG,
            errors))
        self.assertEquals(1, self._error_count(
            commit_message_check.ERROR_CODE.MISSING_FEATURE_ID,
            errors))
        self.assertEquals(c.category, "feature")
        self.assertEquals(c.feature_id, [])

    def test_invalid_commit_message(self):
        """Tests that the method works when there is an invalid commit
        message.
        """
        for testfile in ["commit_message_invalid.txt",
                         "commit_message_invalid1.txt"]:
            c = self.get_checker(testfile, require_category=True)
            c.commit.message += "\n" + "not utf-8".encode('utf-16')
            errors = c.check()
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.DMS_IN_TITLE, errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.MULTIPLE_LINES_IN_SUBJECT,
                errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.SUBJECT_TOO_LONG, errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.DMS_WITHOUT_FIX_TAG, errors))
            self.assertEquals(2, self._error_count(
                commit_message_check.ERROR_CODE.MULTIPLE_DMS_ON_LINE, errors))
            self.assertEquals(2, self._error_count(
                commit_message_check.ERROR_CODE.INVALID_TAG_FORMAT, errors))
            self.assertEquals(2, self._error_count(
                commit_message_check.ERROR_CODE.LINE_TOO_LONG, errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.NON_UTF8_CHARS, errors))
            self.assertEquals(0, self._error_count(
                commit_message_check.ERROR_CODE.MULTIPLE_CONFLICTS_SECTIONS,
                errors))
            self.assertEquals(1, self._error_count(
                commit_message_check.ERROR_CODE.MISSING_CATEGORY, errors))
            self.assertEquals(c.category, None)
            self.assertEquals(c.feature_id, [])


if __name__ == '__main__':
    unittest.main()
