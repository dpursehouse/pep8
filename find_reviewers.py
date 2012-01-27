#! /usr/bin/env python

""" Find reviewers for a change.  Reviewers can be found for a given change
ID, or for a given project, based on approvals on previously merged changes.

When finding reviewers for a project, it is possible to limit the search to
previously merged changes on a specific branch.  It is also possible to set
the number of previous changes to search, and the number of reviewers to
find.

Specific reviewers can be excluded from the results.
"""

from collections import defaultdict
import optparse

import gerrit
from processes import ChildExecutionError
from semcutil import fatal


# Default number of previous reviews from which to find approvers
DEFAULT_LIMIT = 50

# Default number of reviewers to find/add
DEFAULT_COUNT = 3

# URL of the Gerrit review server
GERRIT_URL = "review.sonyericsson.net"


class AddReviewersError(Exception):
    '''AddReviewersError is raised for any kind of error that
    occurs when attempting to add reviewers to a change.
    '''


class FindReviewersError(Exception):
    '''FindReviewersError is raised for any kind of error that
    occurs when attempting to find reviewers for a change.
    '''


class FindReviewers:
    '''Class to find and add reviewers for a change or project.
    '''

    def __init__(self, user=None):
        '''Sets up the Gerrit connection.
        Raises GerritSshConfigError if Gerrit connection fails.
        '''
        self.gerrit = gerrit.GerritSshConnection(GERRIT_URL, user)

    def __find_project_and_owner(self, change):
        '''Finds the project name and email address of the owner for the
        change specified by `change`.
        Returns (project name, owner email address) or None if not found.
        Raises GerritQueryError if Gerrit query fails.
        '''
        result = self.gerrit.query(change)
        try:
            if len(result) == 1:
                return result[0]["project"], result[0]["owner"]["email"]
        except ValueError:
            pass
        return None

    def add(self, change, reviewers):
        '''Calls Gerrit to add `reviewers` onto `change`, where `reviewers`
        is an iterable object contianing reviewers' email addresses, and
        `change` is any change identifier accepted by Gerrit.
        Raises AddReviewersError if Gerrit returns an error
        '''
        if len(reviewers):
            add_cmd = ["set-reviewers", str(change)]
            for reviewer in reviewers:
                add_cmd += ["--add", reviewer]
            try:
                self.gerrit.run_gerrit_command(add_cmd)
            except ChildExecutionError, err:
                raise AddReviewersError("Error adding reviewers to change "
                                        "'%s': %s" % (str(change), err))

    def find(self, change=None, project=None, branch=None,
             limit=DEFAULT_LIMIT, exclude=[]):
        '''Finds reviewers for `change`, or for `project` and `branch`.
        `change` may be a SHA-1 or a change number.  Checks the last `limit`
        number of previously merged changes. `limit` must be 1 or more.
        Reviewers listed in `exclude` will be ignored.
        Returns a list of (approver, count) tuples, where approver is
        the approver's email address and count it the number of times
        they have approved, sorted by count, in descending order.
        Raises FindReviewError if any error occurs when finding reviewers.
        Raises ValueError if invalid parameters are passed.
        '''
        _exclude = []
        _exclude += exclude
        # Validate options
        if int(limit) < 1:
            raise ValueError("Parameter `limit` must be 1 or more")
        if not change and not project:
            raise ValueError("Must specify either change ID or "
                             "project name")
        if change and (project or branch):
            raise ValueError("Cannot specify both change ID and "
                             "project/branch")

        # Set up the query
        query = ["status:merged",
                 "limit:%s" % limit,
                 "label:CodeReview>=2"]
        if change:
            project, owner = self.__find_project_and_owner(change)
            if not project or not owner:
                raise FindReviewersError("Couldn't find project and owner for "
                                         "change '%s'" % change)
            if owner not in _exclude:
                _exclude.append(owner)
            query.append("project:%s" % project)
        else:
            query.append("project:%s" % project)
            if branch:
                query.append("branch:%s" % branch)

        try:
            # Find the approvers of the changes
            approvers = defaultdict(int)
            for result in self.gerrit.query(" ".join(query)):
                for approval in result["currentPatchSet"]["approvals"]:
                    if approval["type"] == "CRVW" and \
                            approval["value"] == "2" and \
                            "email" in approval["by"] and \
                            approval["by"]["email"] not in _exclude:
                        approvers[approval["by"]["email"]] += 1

        except KeyError, err:
            raise FindReviewersError("Missing key '%s' in Gerrit response" % \
                                     err)

        except Exception, err:
            raise FindReviewersError("Unexpected error: %s" % err)

        # Sort the list of approvers by number of approvals made
        return sorted(approvers.iteritems(), reverse=True,
                      key=lambda (k, v): (v, k))


def main():
    ''' Main function.
    '''
    usage = "usage: %prog [-c <change>] [-p <project>] [-b <branch>] " \
        "[-u <username>] [-l <limit>] [-e <exclude>]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-c", "--change", dest="change",
        default=None, help="find reviewers for specified change ID")
    parser.add_option("-p", "--project", dest="project",
        default=None, help="find reviewers for specified project name")
    parser.add_option("-b", "--branch", dest="branch",
        default=None, help="limit to changes on specified branch")
    parser.add_option("-u", "--username", dest="username",
        default=None, help="username to use when connecting to Gerrit")
    parser.add_option("-l", "--limit", dest="limit",
        default=DEFAULT_LIMIT, help="number of previous reviews to check" \
                                    " (default %default)")
    parser.add_option("-e", "--exclude", dest="exclude",
        default="", help="comma-separated list of users to exclude")
    parser.add_option("-a", "--add", dest="add", action="store_true",
        default=False, help="also add the reviewers (default %default), " \
                            "cannot be used in combination with --project")
    parser.add_option("-n", "--count", dest="count", type="int",
        default=DEFAULT_COUNT, help="number of reviewers to find/add" \
                                    " (default %default)")
    (opts, args) = parser.parse_args()

    # Validate options
    if int(opts.count) < 1:
        raise ValueError("Parameter `count` must be 1 or more")
    if opts.add and not opts.change:
        raise ValueError("Must specify change to add reviewers")
    if opts.add and opts.project:
        raise ValueError("Cannot add reviewers for project")

    # Find reviewers
    finder = FindReviewers(user=opts.username)
    exclude_list = set([s.strip() for s in opts.exclude.split(',')])
    approvers = finder.find(opts.change, opts.project, opts.branch,
                            opts.limit, exclude_list)
    reviewers = [approver for approver, count in approvers[0:opts.count]]

    # Print out the list of reviewers
    for reviewer in reviewers:
        print "%s" % reviewer

    # Add reviewers to the change
    if opts.add:
        finder.add(opts.change, reviewers)

if __name__ == '__main__':
    try:
        main()
    except FindReviewersError, err:
        fatal(1, "Failed to find reviewers: %s" % err)
    except AddReviewersError, err:
        fatal(1, "Failed to add reviewers: %s" % err)
    except ValueError, err:
        fatal(1, "Error: %s" % err)
    except KeyboardInterrupt:
        fatal(1, "Terminated by user")
