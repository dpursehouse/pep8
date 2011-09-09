#! /usr/bin/env python

from collections import defaultdict
import json
import optparse

import gerrit
from semcutil import fatal


# Default number of previous reviews from which to find approvers
DEFAULT_LIMIT = 50


class FindReviewersError(Exception):
    '''FindReviewersError is raised for any kind of error that
    occurs when attempting to find reviewers for a change.
    '''


class FindReviewers:
    '''Class to find reviewers for a change or project
    '''

    def __init__(self, user=None):
        '''Sets up the Gerrit connection.
        Raises GerritSshConfigError if Gerrit connection fails.
        '''
        self.g = gerrit.GerritSshConnection("review.sonyericsson.net", user)

    def __find_project_and_owner(self, gerrit_connection, change):
        '''Finds the project name and owner associated with `change`.
        Returns (project name, owner) or None if not found.
        Raises GerritQueryError if Gerrit query fails.
        '''
        result = gerrit_connection.query(change)
        try:
            if len(result) == 1:
                return result[0]["project"], result[0]["owner"]["email"]
        except ValueError:
            pass
        return None

    def find(self, change=None, project=None, branch=None,
        limit=DEFAULT_LIMIT, exclude=[]):
        '''Finds reviewers for `change`, or for `project` and `branch`.
        `change` may be a SHA-1 or a change number.  Checks the last `limit`
        number of previously merged changes.
        Returns a list of (approver, count) tuples, where approver is
        the approver's email address and count it the number of times
        they have approved, sorted by count, in descending order.
        '''
        _exclude = exclude
        # Validate options
        if not change and not project:
            raise FindReviewersError("Must specify either change ID "
                                     "or project name")
        if change and (project or branch):
            raise FindReviewersError("Cannot specify change ID and "
                                     "project/branch")

        # Set up the query
        self.query = ["status:merged", "limit:%s" % (limit),
            "label:CodeReview>=2"]
        if change:
            project, owner = self.__find_project_and_owner(self.g, change)
            if not project or not owner:
                raise FindReviewersError("Couldn't find details for change %s"
                    % (change))
            if owner not in _exclude:
                _exclude.add(owner)
            self.query.append("project:%s" % (project))
        else:
            self.query.append("project:%s" % (project))
            if branch:
                self.query.append("branch:%s" % (branch))

        try:
            # Find the approvers of the changes
            approvers = defaultdict(int)
            for result in self.g.query(" ".join(self.query)):
                for approval in result["currentPatchSet"]["approvals"]:
                    if approval["type"] == "CRVW" and \
                            approval["value"] == "2" and \
                            "email" in approval["by"] and \
                            approval["by"]["email"] not in _exclude:
                        approvers[approval["by"]["email"]] += 1

        except KeyError, e:
            raise FindReviewersError("Missing key %s in data from Gerrit"
                % (e))

        except Exception, e:
            raise FindReviewersError("Unexpected error: %s" % (e))

        # Sort the list of approvers by number of approvals made
        return sorted(approvers.iteritems(), reverse=True,
                      key=lambda (k, v): (v, k))


def main():
    usage = "usage: %prog [-c <change>] [-p <project>] [-b <branch>] " \
        "[-u <username>] [-l <limit>] [-e <exclude>]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-c", "--change", dest="change",
        default=None, help="Find reviewers based on change ID")
    parser.add_option("-p", "--project", dest="project",
        default=None, help="Find reviewers based on project name")
    parser.add_option("-b", "--branch", dest="branch",
        default=None, help="Limit to changes on given branch")
    parser.add_option("-u", "--username", dest="username",
        default=None, help="Username to use when connecting to Gerrit")
    parser.add_option("-l", "--limit", dest="limit",
        default=DEFAULT_LIMIT, help="Number of previous reviews to check")
    parser.add_option("-e", "--exclude", dest="exclude",
        default="", help="Comma separated list of users to exclude")
    (opts, args) = parser.parse_args()

    finder = FindReviewers(user=opts.username)
    exclude_list = set([s.strip() for s in opts.exclude.split(',')])
    approvers = finder.find(change=opts.change, project=opts.project,
                            branch=opts.branch, limit=opts.limit,
                            exclude=exclude_list)

    # Print out the top 3 approvers
    for approver, count in approvers[0:3]:
        print "%s" % (approver)

if __name__ == '__main__':
    try:
        main()
    except Exception, e:
        fatal(1, "Failed to find reviewers: %s" % (e))
    except KeyboardInterrupt:
        fatal(1, "Terminated by user")
