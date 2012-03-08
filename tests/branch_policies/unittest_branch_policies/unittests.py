#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import unittest
from xml.parsers.expat import ExpatError

from branch_policies import BranchPolicies, BranchPolicyError


class TestBranchPolicies(unittest.TestCase):
    """ Test that the TestBranchPolicies class behaves correctly.
    """

    def _get_policy(self, filename):
        """Use the file specified by `filename` to create
        a BranchPolicies object.  Return the BranchPolicies object.
        """
        return BranchPolicies(os.path.join(os.environ["TESTDIR"], filename))

    def test_init_with_no_config(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated without a config.
        """
        p = BranchPolicies()
        self.assertEquals(p.branches, [])
        self.assertFalse(p.branch_has_policy("xyz"))
        self.assertFalse(p.branch_requires_dms("xyz"))
        self.assertEquals(p.get_branch_tagnames("xyz"), [])
        self.assertEquals(p.get_policy("xyz"), None)
        self.assertTrue(p.is_tag_allowed("tag", "xyz"))

    def test_valid_config_single_branch(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated with a config containing
        a single valid branch policy.
        """
        p = self._get_policy("policy_valid_single_branch.xml")
        self.assertEquals(len(p.branches), 1)
        self.assertTrue(p.branch_has_policy("branch-1"))
        self.assertFalse(p.branch_has_policy("branch-2"))
        self.assertTrue(p.branch_requires_dms("branch-1"))
        self.assertEquals(p.get_branch_tagnames("branch-1"),
            ["TAG 1", "TAG 2"])
        self.assertTrue(p.is_tag_allowed("TAG 1", "branch-1"))
        self.assertTrue(p.is_tag_allowed("TAG 2", "branch-1"))
        self.assertFalse(p.is_tag_allowed("TAG 3", "branch-1"))
        self.assertEquals((-2, -1), p.get_branch_score_values("branch-1"))

    def test_valid_config_multi_branch(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated with a config containing
        multiple valid branch policies.
        """
        p = self._get_policy("policy_valid_multi_branch.xml")
        self.assertEquals(len(p.branches), 2)

        self.assertTrue(p.branch_has_policy("branch-1"))
        self.assertTrue(p.branch_requires_dms("branch-1"))
        self.assertEquals(p.get_branch_tagnames("branch-1"),
            ["TAG 1", "TAG 2"])
        self.assertTrue(p.is_tag_allowed("TAG 1", "branch-1"))
        self.assertTrue(p.is_tag_allowed("TAG 2", "branch-1"))
        self.assertFalse(p.is_tag_allowed("TAG 3", "branch-1"))

        self.assertTrue(p.branch_has_policy("branch-2"))
        self.assertTrue(p.branch_requires_dms("branch-2"))
        self.assertEquals(p.get_branch_tagnames("branch-2"),
            ["TAG 3", "TAG 4"])
        self.assertTrue(p.is_tag_allowed("TAG 3", "branch-2"))
        self.assertTrue(p.is_tag_allowed("TAG 4", "branch-2"))
        self.assertFalse(p.is_tag_allowed("TAG 5", "branch-2"))

    def test_valid_config_regex_branch(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated with a config containing
        a branch policy with a regular expression branch pattern.
        """
        p = self._get_policy("policy_valid_regex_branch.xml")
        self.assertEquals(len(p.branches), 1)
        self.assertTrue(p.branch_has_policy("branch-1"))
        self.assertTrue(p.branch_has_policy("branch-11"))
        self.assertTrue(p.branch_has_policy("branch-111"))
        self.assertFalse(p.branch_has_policy("x-branch-1"))
        self.assertFalse(p.branch_has_policy("branch-2"))
        self.assertFalse(p.branch_has_policy("branch-22"))
        self.assertFalse(p.branch_has_policy("branch-222"))

    def test_valid_config_regex_tags(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated with a config containing
        a branch policy with a regular expression tags pattern.
        """
        p = self._get_policy("policy_valid_regex_tags.xml")
        self.assertEquals(len(p.branches), 1)
        self.assertTrue(p.branch_has_policy("branch-name"))
        self.assertTrue(p.branch_requires_dms("branch-name"))
        self.assertEquals(p.get_branch_tagnames("branch-name"), [])
        self.assertTrue(p.is_tag_allowed("TAG 1", "branch-name"))
        self.assertTrue(p.is_tag_allowed("TAG 12", "branch-name"))
        self.assertTrue(p.is_tag_allowed("TAG 123", "branch-name"))
        self.assertFalse(p.is_tag_allowed("TAG 2", "branch-name"))

    def test_valid_dms_not_required(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated with a config containing
        a branch policy that does not require DMS.
        """
        p = self._get_policy("policy_valid_dms_not_required.xml")
        self.assertFalse(p.branch_requires_dms("branch-name"))
        self.assertTrue(p.is_tag_allowed("tag", "branch-name"))
        self.assertEquals((None, None),
                          p.get_branch_score_values("branch-name"))

    def test_invalid_xml(self):
        """ Test that the class constructor raises an exception
        when instantiated with invalid XML data.
        """
        self.assertRaises(ExpatError, self._get_policy,
            "policy_invalid_xml.xml")

    def test_xml_file_does_not_exist(self):
        """ Test that the class constructor raises an exception
        when instantiated with a filename that does not exist.
        """
        self.assertRaises(IOError, self._get_policy,
            "policy_does_not_exist.xml")

    def test_invalid_multiple_dms_required(self):
        """ Test that the class constructor raises an exception
        when instantiated with a config that specifies more than
        one "dms-required" element in a branch.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_multi_dms_required.xml")

    def test_invalid_multiple_code_review_scores(self):
        """ Test that the class constructor raises an exception
        when instantiated with a config that specifies more than
        one "code-review" element in a branch.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_multi_code_review_scores.xml")

    def test_invalid_multiple_verify_scores(self):
        """ Test that the class constructor raises an exception
        when instantiated with a config that specifies more than
        one "verify" element in a branch.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_multi_verify_scores.xml")

    def test_invalid_code_review_score(self):
        """ Test that the class constructor raises an exception
        when instantiated with a config that specifies an invalid
        "code-review" element in a branch.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_code_review_score.xml")

    def test_invalid_verify_score(self):
        """ Test that the class constructor raises an exception
        when instantiated with a config that specifies an invalid
        "verify" element in a branch.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_verify_score.xml")

    def test_invalid_score_without_dms(self):
        """ Test that the class constructor raises an exception
        when instantiated with a config that specifies a score
        element in a branch that does not require DMS.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_score_without_dms.xml")

    def test_invalid_missing_dms_required_element(self):
        """ Test that the class constructor raises an exception
        when instantiated with a config that does not have a "dms-required"
        element.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_missing_dms_required_element.xml")

    def test_invalid_empty_dms_required_element(self):
        """ Test that the class constructor raises an exception
        when instantiated with a config that has an empty "dms-required"
        element.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_empty_dms_required_element.xml")

if __name__ == '__main__':
    unittest.main()
