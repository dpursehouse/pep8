#! /usr/bin/env python

""" Class for managing branch DMS policies. """

from optparse import OptionParser
import re
from xml.etree.ElementTree import ElementTree
from xml.parsers.expat import ExpatError

import semcutil

VALID_CODE_REVIEW = ["-2", "-1", "0"]
VALID_VERIFY = ["-1", "0"]
DEFAULT_CONFIG_FILE = 'etc/dms_policy.xml'


def _get_element(node, element_name):
    """ Get `element_name` from `node` and return its text value
    converted to lower case.  Return None if the element was not found,
    or the element had no text value.
    Raise BranchPolicyError if more than one element was found.
    """
    elements = node.findall(element_name)
    if elements:
        if len(elements) > 1:
            raise BranchPolicyError("Cannot have more than one `%s` "
                                    "element per branch" % element_name)
        if elements[0].text:
            return elements[0].text.lower()
    return None


def _get_score(node, review_type, valid_scores):
    """ Get the score `review_type` from `node` and return it as an
    integer, or None if the score was not found in the node.
    Raise BranchPolicyError if the score is not in `valid_scores`.
    """
    score = _get_element(node, review_type)
    if score:
        if score not in valid_scores:
            raise BranchPolicyError("Invalid %s value: %s" % \
                                    (review_type, score))
        return int(score)
    return None


class BranchPolicyError(Exception):
    """ BranchPolicyError is raised when an invalid policy is
    configured.
    """


class BranchPolicies(object):
    """ Encapsulation of branch issue tag policies.
    """

    def __init__(self, config_file):
        """Raises an xml.parsers.expat.ExpatError exception if the
        input XML file can't be parsed, an IOError exception if the
        file can't be opened, or a BranchPolicyError if the XML file
        contains an invalid policy configuration.
        """

        self.branches = []

        if not config_file:
            raise BranchPolicyError("Config file must be specified")

        # Using XPath via xml.etree.ElementTree to parse the XML
        # file.  I thought /branches/branch would be a valid XPath
        # query returning all <branch> elements that were children
        # of the <branches> root element, but this wasn't the
        # case.
        doc = ElementTree(file=config_file)
        branches = []
        for branch in doc.findall("branch"):
            name = branch.get("name")
            if not name:
                raise BranchPolicyError("Branch must have a `name` element")

            if name in branches:
                raise BranchPolicyError("Cannot specify branch " \
                                        "more than once (%s)" % name)
            branches.append(name)
            tagnames = []
            tagpatterns = []
            dms_required = False
            code_review = None
            verify = None
            for tag in branch.findall("allowed-dms-tag"):
                tagname = tag.get("name")
                tagpattern = tag.get("pattern")
                if tagname and tagpattern:
                    raise BranchPolicyError("Cannot specify both "
                                            "`name` and `pattern` for "
                                            "`allowed-dms-tag`.")
                elif tagname:
                    tagnames.append(tagname.strip())
                elif tagpattern:
                    tagpatterns.append(tagpattern.strip())

            dms_required_element = _get_element(branch, "dms-required")
            if not dms_required_element:
                raise BranchPolicyError("`dms-required` value not "
                                        "specified for branch %s" % \
                                        name)
            dms_required = dms_required_element == "true"

            code_review = _get_score(branch, "code-review",
                                     VALID_CODE_REVIEW)
            verify = _get_score(branch, "verify", VALID_VERIFY)

            if (code_review or verify) and not dms_required:
                raise BranchPolicyError("Cannot specify score unless "
                                        "DMS is required")

            if dms_required or tagnames or tagpatterns:
                self.branches.append({"name": name,
                                      "tagnames": tagnames,
                                      "tagpatterns": tagpatterns,
                                      "dms_required": dms_required,
                                      "code_review": code_review,
                                      "verify": verify})

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
            if branchpolicy["name"] == dest_branch:
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


def _main():

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
    _main()
