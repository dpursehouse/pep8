import logging
import optparse
import re
import sys

from cherry_status import CherrypickStatusServer, CherrypickStatusError
from cherry_status import DEFAULT_STATUS_SERVER
from gerrit import GerritSshConnection, GerritSshConfigError, GerritQueryError
from processes import ChildExecutionError
from semcutil import fatal


class CherrypickStatus:
    ''' Encapsulation of cherry pick status.
    '''

    def __init__(self, csvdata):
        ''' Initialise self with `csvdata`.
        Raise CherrypickStatusError if CSV data is not valid.
        '''
        data = csvdata.rstrip().split(',')
        if len(data) < 9:
            raise CherrypickStatusError("Not enough data in csv")
        self.branch = data[0]
        self.path = data[1]
        self.project = data[2]
        self.sha1 = data[3]
        self.dms = data[4]
        self.pick_status = None
        self.set_pick_status(data[5])
        self.review = data[6]
        self.verify = data[7]
        self.status = data[8]
        self.dirty = False

    def set_pick_status(self, pick_status):
        ''' Update pick_status, error and change_nr according to `pick_status`,
        if it has changed, and set the state to dirty.
        '''
        if self.pick_status != pick_status:
            self.pick_status = pick_status
            # If the pick status is a Gerrit review URL, extract
            # the change number.  Otherwise extract the error message.
            match = re.match("^https?.*?(\d+)$", self.pick_status)
            if not match:
                self.error = self.pick_status
                self.change_nr = None
            else:
                self.error = None
                self.change_nr = match.group(1)
            self.dirty = True

    def set_merge_status(self, status):
        ''' Update status with `status` if it has changed and
        set the state to dirty.
        '''
        if self.status != status:
            self.status = status
            self.dirty = True

    def set_review(self, review):
        ''' Update review value with `review` if it has changed and
        set the state to dirty.
        '''
        if self.review != review:
            self.review = review
            self.dirty = True

    def set_verify(self, verify):
        ''' Update verify value with `verify` if it has changed and
        set the state to dirty.
        '''
        if self.verify != verify:
            self.verify = verify
            self.dirty = True

    def is_dirty(self):
        ''' Check if the cherry pick is dirty, i.e. has been updated.
        Return True if so, otherwise False.
        '''
        return self.dirty

    def __str__(self):
        ''' Serialise self to a CSV string.
        '''
        return "%s,%s,%s,%s,%s,%s,%s,%s,%s" % (self.branch, self.path,
            self.project, self.sha1, self.dms, self.pick_status,
            self.review, self.verify, self.status)


def _calculate_score(scores, blocker):
    ''' Given a list of `scores`, determine the score that should be
    stored in the cherry pick status.  If a `blocker` score is included
    in the list, that should be the score.  Otherwise if the opposite of
    the blocking score (i.e. an approval) is given, return that. Otherwise
    return the lowest score from the list.
    Raise CherrypickStatusError if the score list is invalid.
    '''
    if len(scores):
        if 0 in scores:
            raise CherrypickStatusError("Scores should not include 0")
        if max(scores) > abs(blocker):
            raise CherrypickStatusError("Max score too high")
        if min(scores) < blocker:
            raise CherrypickStatusError("Min score too low")
        if blocker in scores:
            return blocker
        if abs(blocker) in scores:
            return abs(blocker)
        return min(scores)
    return 0


def _update_status_from_gerrit(gerrit, cherry):
    ''' Query `gerrit` for the change specified in `cherry` and then
    update `cherry` with the status, review and verify values returned
    in the query results.
    Raise GerritQueryError if the gerrit query returns an error.
    Raise ChildExecutionError if the gerrit query command fails.
    '''
    reviews = []
    verifies = []
    query = None

    # For cherry picks recorded as an error, check if a change has been
    # uploaded in the meantime.
    if cherry.error:
        if cherry.error == "Already merged":
            cherry.set_merge_status("MERGED")
            cherry.set_review("2")
            cherry.set_verify("1")
        elif cherry.error == "Failed due to merge conflict":
            query = "project:%s " \
                    "branch:%s " \
                    "message:cherry.picked.from.commit.%s" % \
                    (cherry.project, cherry.branch, cherry.sha1)
    elif cherry.change_nr:
        query = cherry.change_nr

    if query:
        # Query Gerrit for the change.
        results = gerrit.query(query)
        if len(results) == 1:
            # Extract the data from the Gerrit query results, if it exists,
            # and update in the cherry pick.
            result = results[0]
            if "number" in result:
                cherry.set_pick_status("http://review.sonyericsson.net/%s" % \
                                       result["number"])
            if "status" in result:
                cherry.set_merge_status(result["status"])
            if "currentPatchSet" in result:
                if "approvals" in result["currentPatchSet"]:
                    approvals = result["currentPatchSet"]["approvals"]
                    for approval in approvals:
                        if approval["type"] == "CRVW":
                            reviews += [int(approval["value"])]
                        elif approval["type"] == "VRIF":
                            verifies += [int(approval["value"])]
                cherry.set_review("%d" % _calculate_score(reviews, -2))
                cherry.set_verify("%d" % _calculate_score(verifies, -1))

    return cherry


def _update_cherrypicks(status_server, target, dry_run):
    ''' Connect to the `status_server` and get the list of cherry picks for
    `target`.  For each cherry pick, find the current status from Gerrit and
    then update on the status server if the status has changed.  If `dry_run`
    is True, don't actually update the status on the server.
    Skip any cherry picks with error status.
    Raise GerritQueryError if the gerrit query returns an error.
    Return total cherry picks processed, total skipped, total
    updated, and total errors occurred.
    '''
    csvdata = status_server.get_old_cherrypicks(target)
    total = len(csvdata)

    errors = 0
    skipped = 0
    updated = 0

    if total:
        gerrit = GerritSshConnection("review.sonyericsson.net")
        for line in csvdata:
            try:
                cherry = CherrypickStatus(line)

                # No need to update the status if it's already merged
                if cherry.status != "MERGED":
                    cherry = _update_status_from_gerrit(gerrit, cherry)

                if cherry.is_dirty():
                    logging.info("Updating: %s,%s,%s,%s,%s,%s" % \
                                 (cherry.project, cherry.sha1,
                                  cherry.pick_status, cherry.review,
                                  cherry.verify, cherry.status))
                    if not dry_run:
                        status_server.update_status(target, "%s" % cherry)
                    updated += 1
                else:
                    logging.info("Skipping: %s,%s" % \
                                 (cherry.project, cherry.sha1))
                    skipped += 1
            except CherrypickStatusError, e:
                errors += 1
                logging.error("Cherry pick status error: %s" % e)
            except GerritQueryError, e:
                errors += 1
                logging.error("Gerrit query error: %s" % e)
            except ChildExecutionError, e:
                errors += 1
                logging.error("Gerrit query execution error: %s" % e)

    return total, skipped, updated, errors


def _main():
    usage = "usage: %prog [options]"
    options = optparse.OptionParser(usage=usage)
    options.add_option("", "--target", action="store", default=None,
                       dest="target", help="Target branch.  Update all " \
                            "targets if not specified.")
    options.add_option("", "--dry-run", dest="dry_run", action="store_true",
                       help="Do everything except actually update the " \
                           "status.")
    options.add_option("", "--status-server", dest="status_server",
                       help="IP address or name of the status server.",
                       action="store", default=DEFAULT_STATUS_SERVER)
    (options, args) = options.parse_args()

    logging.basicConfig(format='%(message)s', level=logging.INFO)

    try:
        status_server = CherrypickStatusServer(options.status_server)
        if not options.target:
            targets = status_server.get_all_targets()
        else:
            targets = [options.target]

        error_count = 0
        for target in targets:
            logging.info("Updating status for %s" % target)

            total, skipped, updated, errors = _update_cherrypicks(
                                                status_server, target,
                                                options.dry_run)
            error_count += errors
            logging.info("\nProcessed %d cherry picks\n" % total +
                         "Updated: %d\n" % updated +
                         "Skipped: %d\n" % skipped +
                         "Errors: %d\n" % errors)
        return error_count
    except CherrypickStatusError, e:
        fatal(1, "Cherry pick status error: %s" % e)
    except GerritSshConfigError, e:
        fatal(1, "Gerrit SSH error: %s" % e)

if __name__ == "__main__":
    try:
        sys.exit(_main())
    except KeyboardInterrupt:
        sys.exit(1)
