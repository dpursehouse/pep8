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
        one "dms-required" elements in a branch.
        """
        self.assertRaises(BranchPolicyError, self._get_policy,
            "policy_invalid_multi_dms_required.xml")

if __name__ == '__main__':
    unittest.main()
