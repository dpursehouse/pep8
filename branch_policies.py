#! /usr/bin/env python

from optparse import OptionParser
import os
import re
import sys
from xml.etree.ElementTree import ElementTree
from xml.parsers.expat import ExpatError

import semcutil

VALID_CODE_REVIEW = ["-2", "-1", "0"]
VALID_VERIFY = ["-1", "0"]
DEFAULT_CONFIG_FILE = 'etc/dms_policy.xml'


class BranchPolicyError(Exception):
    """ BranchPolicyError is raised when an invalid policy is
    configured.
    """


class BranchPolicies():
    """ Encapsulation of branch issue tag policies.
    """

    def __init__(self, config_file=None):
        """Raises an xml.parsers.expat.ExpatError exception if the
        input XML file can't be parsed, or an IOError exception if the
        file can't be opened.
        """

        self.branches = []
        if config_file:
            # Using XPath via xml.etree.ElementTree to parse the XML
            # file.  I thought /branches/branch would be a valid XPath
            # query returning all <branch> elements that were children
            # of the <branches> root element, but this wasn't the
            # case.
            doc = ElementTree(file=config_file)
            for branch in doc.findall("branch"):
                pattern = branch.get("pattern")
                if pattern:
                    tagnames = []
                    tagpatterns = []
                    dms_required = False
                    codereview = None
                    verify = None
                    for element in branch.findall("allowed-dms-tag"):
                        tagname = element.get("name")
                        if tagname:
                            tagnames.append(tagname.strip())
                        tagpattern = element.get("pattern")
                        if tagpattern:
                            tagpatterns.append(tagpattern.strip())

                    dms_required_element = self._get_element(branch,
                                                             "dms-required")
                    if not dms_required_element:
                        raise BranchPolicyError("`dms-required` value not "
                                                "specified for branch %s" % \
                                                pattern)
                    dms_required = dms_required_element == "true"

                    code_review = self._get_score(branch, "code-review",
                                                  VALID_CODE_REVIEW)
                    verify = self._get_score(branch, "verify", VALID_VERIFY)

                    if (code_review or verify) and not dms_required:
                        raise BranchPolicyError("Cannot specify score unless "
                                                "DMS is required")

                    if dms_required or tagnames or tagpatterns:
                        self.branches.append({"pattern": pattern,
                                              "tagnames": tagnames,
                                              "tagpatterns": tagpatterns,
                                              "dms_required": dms_required,
                                              "code_review": code_review,
                                              "verify": verify})

    def _get_element(self, node, element_name):
        """ Get `element_name` from `node` and return its text value
        converted to lower case, or None if the element was not found.
        Raise BranchPolicyError if more than one element was found.
        """
        elements = node.findall(element_name)
        if not elements:
            return None
        if len(elements) > 1:
            raise BranchPolicyError("Cannot have more than one `%s` element "
                                    "per branch" % element_name)
        return elements[0].text.lower()

    def _get_score(self, node, type, valid_scores):
        """ Get the score `type` from `node` and return it as an integer, or
        None if the score was not found in the node.
        Raise BranchPolicyError if the score is not in `valid_scores`.
        """
        score = self._get_element(node, type)
        if score:
            if score not in valid_scores:
                raise BranchPolicyError("Invalid %s value: %s" % (type, score))
            return int(score)
        return None

    def branch_has_policy(self, dest_branch):
        """ Check if the `dest_branch` has a tag policy.
        Return True if so, otherwise return False.
        """
        return self.get_policy(dest_branch) != None

    def branch_requires_dms(self, dest_branch):
        """ Check if the `dest_branch` requires DMS.
        Return True if so, otherwise return False.
        """
        policy = self.get_policy(dest_branch)
        if policy:
            return policy["dms_required"]
        else:
            # If the branch doesn't have a policy, default to being
            # permissive.
            return False

    def get_branch_score_values(self, dest_branch):
        """ Get the Gerrit review scores to be used for `dest_branch` if its
        DMS policy is not met.
        Return a tuple of code review and verify scores.
        """
        if self.branch_requires_dms(dest_branch):
            policy = self.get_policy(dest_branch)
            return (policy["code_review"], policy["verify"])
        return (None, None)

    def get_branch_tagnames(self, dest_branch):
        """ Get the tags required by `dest_branch`.
        Return a list of tags, empty if there are no tags required.
        """
        policy = self.get_policy(dest_branch)
        if policy and policy["tagnames"]:
            return policy["tagnames"]
        else:
            return []

    def get_policy(self, dest_branch):
        """ Return the policy for `dest_branch`, or None if there is
        no policy.
        """
        for branchpolicy in self.branches:
            if re.search(branchpolicy["pattern"], dest_branch):
                return branchpolicy
        return None

    def is_tag_allowed(self, tag, dest_branch):
        """ Check if `tag` is allowed on `dest_branch`.
        Return True if so, otherwise return False.
        """
        policy = self.get_policy(dest_branch)
        if policy:
            if tag in policy["tagnames"]:
                return True
            for tagpattern in policy["tagpatterns"]:
                if tagpattern and re.search(tagpattern, tag):
                    return True
            return False
        else:
            # If the branch doesn't have a policy, default to being
            # permissive.
            return True


def _main(argv):

    usage = "usage: %prog [options] BRANCH"
    parser = OptionParser(usage=usage)
    parser.add_option("--print_tags", dest="print_tags",
                      action="store_true", default=True,
                      help="Print the tags for the branch, `BRANCH` from " + \
                           "the specified policy file.")
    parser.add_option("--allow_empty_tags", dest="allow_empty_tags",
                      action="store_true", default=False,
                      help="If set to `True` prints an empty string even " + \
                           "if no tags are found for the branch else " + \
                           "fails with fatal error.")
    parser.add_option("-p", "--policy_file", dest="policy_file",
                      default=DEFAULT_CONFIG_FILE,
                      help="Path to the branch policy file.")
    (options, args) = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        parser.error("Incorrect number of arguments")
    if options.print_tags:
        branch = args[0]
        try:
            config = BranchPolicies(options.policy_file)
        except (ExpatError, BranchPolicyError), err:
            semcutil.fatal(1, "Error parsing %s: %s" % \
                           (options.policy_file, err))

        tags = config.get_branch_tagnames(branch)
        if tags or options.allow_empty_tags:
            print ','.join(tags)
        else:
            semcutil.fatal(1, "No tags found for branch: %s" % (branch))

if __name__ == "__main__":
    _main(sys.argv)
