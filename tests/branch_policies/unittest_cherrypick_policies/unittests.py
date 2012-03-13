#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Test cases for the CherrypickPolicy class. """

import os
import unittest

from branch_policies import BranchPolicies, BranchPolicyError
from branch_policies import CherrypickPolicyError


def _get_policy(filename):
    """Use the file specified by `filename` to create
    a BranchPolicies object.  Return the BranchPolicies object.
    """
    return BranchPolicies(os.path.join(os.environ["TESTDIR"], filename))


class TestCherrypickPolicies(unittest.TestCase):
    """ Test that the TestBranchPolicies class behaves correctly
    when given a configuration containing cherrypick policy.
    """

    def test_valid_config_single_config(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated with a config containing
        a single valid cherrypick policy.
        """
        policy = _get_policy("policy_valid_single_policy.xml")

        self.assertEquals(len(policy.branches), 1)
        self.assertTrue(policy.branch_has_policy("target-branch"))
        self.assertFalse(policy.branch_has_policy("branch-2"))
        self.assertTrue(policy.branch_requires_dms("target-branch"))
        self.assertEquals(policy.get_branch_tagnames("target-branch"),
                          ["TAG 1", "TAG 2"])
        self.assertTrue(policy.is_tag_allowed("TAG 1", "target-branch"))
        self.assertTrue(policy.is_tag_allowed("TAG 2", "target-branch"))
        self.assertFalse(policy.is_tag_allowed("TAG 3", "target-branch"))
        self.assertEquals((-2, -1),
                          policy.get_branch_score_values("target-branch"))

        cherry_policy = policy.get_cherrypick_policy("source-branch",
                                                     "target-branch")
        self.assertNotEquals(None, cherry_policy)
        self.assertEquals(cherry_policy.source, "source-branch")
        self.assertEquals(cherry_policy.exclude_component,
                          ["component/to/exclude",
                           "another/component/to/exclude"])
        self.assertEquals(cherry_policy.include_component,
                          ["component/to/include",
                           "another/component/to/include"])
        self.assertEquals(cherry_policy.exclude_target_revision,
                          ["target-revision-to-exclude",
                           "another-target-revision-to-exclude"])
        self.assertEquals(cherry_policy.include_target_revision,
                          ["target-revision-to-include",
                           "another-target-revision-to-include"])
        self.assertEquals(cherry_policy.exclude_source_revision,
                          ["source-revision-to-exclude",
                           "another-revision-to-exclude"])
        self.assertEquals(cherry_policy.include_source_revision,
                          ["source-revision-to-include",
                           "another-revision-to-include"])
        self.assertEquals(cherry_policy.exclude_dms,
                          ["DMS00123456", "DMS00654321"])

    def test_valid_config_single_config_empty(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated with a config containing
        a single valid cherrypick policy that is empty, i.e. has no
        excluded or included items.
        """
        policy = _get_policy("policy_valid_single_policy_empty.xml")

        self.assertEquals(len(policy.branches), 1)
        self.assertTrue(policy.branch_has_policy("target-branch"))
        self.assertFalse(policy.branch_has_policy("branch-2"))
        self.assertTrue(policy.branch_requires_dms("target-branch"))
        self.assertEquals(policy.get_branch_tagnames("target-branch"),
                          ["TAG 1", "TAG 2"])
        self.assertTrue(policy.is_tag_allowed("TAG 1", "target-branch"))
        self.assertTrue(policy.is_tag_allowed("TAG 2", "target-branch"))
        self.assertFalse(policy.is_tag_allowed("TAG 3", "target-branch"))
        self.assertEquals((-2, -1),
                          policy.get_branch_score_values("target-branch"))

        cherry_policy = policy.get_cherrypick_policy("source-branch",
                                                     "target-branch")
        self.assertNotEquals(None, cherry_policy)
        self.assertEquals(cherry_policy.source, "source-branch")
        self.assertEquals(cherry_policy.exclude_component, [])
        self.assertEquals(cherry_policy.include_component, [])
        self.assertEquals(cherry_policy.exclude_target_revision, [])
        self.assertEquals(cherry_policy.include_target_revision, [])
        self.assertEquals(cherry_policy.exclude_source_revision, [])
        self.assertEquals(cherry_policy.include_source_revision, [])
        self.assertEquals(cherry_policy.exclude_dms, [])

    def test_valid_config_multi_config(self):
        """ Test that the class constructor and its methods behave
        correctly when it is instantiated with a config containing
        multiple valid cherrypick policies.
        """
        policy = _get_policy("policy_valid_multi_policy.xml")
        cherry_policy = policy.get_cherrypick_policy("source-branch",
                                                     "target-branch")
        self.assertNotEquals(None, cherry_policy)
        self.assertEquals(cherry_policy.source, "source-branch")
        self.assertEquals(cherry_policy.exclude_component,
                          ["component/to/exclude",
                           "another/component/to/exclude"])
        self.assertEquals(cherry_policy.include_component,
                          ["component/to/include",
                           "another/component/to/include"])
        self.assertEquals(cherry_policy.exclude_target_revision,
                          ["target-revision-to-exclude",
                           "another-target-revision-to-exclude"])
        self.assertEquals(cherry_policy.include_target_revision,
                          ["target-revision-to-include",
                           "another-target-revision-to-include"])
        self.assertEquals(cherry_policy.exclude_source_revision,
                          ["source-revision-to-exclude",
                           "another-revision-to-exclude"])
        self.assertEquals(cherry_policy.include_source_revision,
                          ["source-revision-to-include",
                           "another-revision-to-include"])
        self.assertEquals(cherry_policy.exclude_dms,
                          ["DMS00123456", "DMS00654321"])

        cherry_policy = policy.get_cherrypick_policy("another-source-branch",
                                                     "target-branch")
        self.assertNotEquals(None, cherry_policy)
        self.assertEquals(cherry_policy.source, "another-source-branch")
        self.assertEquals(cherry_policy.exclude_component,
                          ["another/component/to/exclude",
                           "yet/another/component/to/exclude"])
        self.assertEquals(cherry_policy.include_component,
                          ["another/component/to/include",
                           "yet/another/component/to/include"])
        self.assertEquals(cherry_policy.exclude_target_revision,
                          ["another-target-revision-to-exclude",
                           "yet-another-target-revision-to-exclude"])
        self.assertEquals(cherry_policy.include_target_revision,
                          ["another-target-revision-to-include",
                           "yet-another-target-revision-to-include"])
        self.assertEquals(cherry_policy.exclude_source_revision,
                          ["another-source-revision-to-exclude",
                           "yet-another-revision-to-exclude"])
        self.assertEquals(cherry_policy.include_source_revision,
                          ["another-source-revision-to-include",
                           "yet-another-revision-to-include"])
        self.assertEquals(cherry_policy.exclude_dms,
                          ["DMS11123456", "DMS11654321"])

    def test_valid_config_nonexistent_branches(self):
        """ Test that the class behaves correctly when attempting to
        get the cherrypick configuration for a nonexistent source/target
        combination.
        """
        policy = _get_policy("policy_valid_single_policy.xml")
        cherry_policy = policy.get_cherrypick_policy("source-branch-no",
                                                     "target-branch")
        self.assertEquals(None, cherry_policy)
        cherry_policy = policy.get_cherrypick_policy("source-branch",
                                                     "target-branch-no")
        self.assertEquals(None, cherry_policy)
        cherry_policy = policy.get_cherrypick_policy("source-branch-no",
                                                     "target-branch-no")
        self.assertEquals(None, cherry_policy)

    def test_invalid_empty_element(self):
        """ test that the class constructor behaves correctly when
        instantiated with a config that contains an empty element.
        """
        self.assertRaises(BranchPolicyError, _get_policy,
                          "policy_invalid_empty_element.xml")

    def test_invalid_no_source(self):
        """ test that the class constructor behaves correctly when
        instantiated with a config that does not have a source parameter.
        """
        self.assertRaises(CherrypickPolicyError, _get_policy,
                          "policy_invalid_no_source_parameter.xml")

if __name__ == '__main__':
    unittest.main()
