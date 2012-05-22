#!/usr/bin/env python

""" Update the status of cherry picks for given branch, or all target
branches.
"""

import logging
import optparse
import sys

from cm_server import CMServer, CherrypickStatusError, CMServerError
from cm_server import DEFAULT_SERVER
from gerrit import GerritSshConnection, GerritSshConfigError, GerritQueryError
from processes import ChildExecutionError
from semcutil import fatal

# URL of the Gerrit server
GERRIT_URL = "review.sonyericsson.net"


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

    if cherry.change_nr:
        query = str(cherry.change_nr)
    elif cherry.message:
        # For cherry picks recorded as an error, check if a change has been
        # uploaded in the meantime.
        if cherry.message == "Already merged":
            cherry.set_status("MERGED")
            cherry.set_review(2)
            cherry.set_verify(1)
        elif cherry.message.startswith("Failed"):
            query = "project:%s " \
                    "branch:%s " \
                    "message:cherry.picked.from.commit.%s" % \
                    (cherry.project, cherry.branch, cherry.sha1)

    if query:
        # Query Gerrit for the change.
        results = gerrit.query(query)
        if len(results) == 1:
            # Extract the data from the Gerrit query results, if it exists,
            # and update in the cherry pick.
            result = results[0]
            if "number" in result:
                cherry.set_change_nr(int(result["number"]))
            if "status" in result:
                cherry.set_status(result["status"])
            if "currentPatchSet" in result:
                if "approvals" in result["currentPatchSet"]:
                    approvals = result["currentPatchSet"]["approvals"]
                    for approval in approvals:
                        if approval["type"] == "CRVW":
                            reviews += [int(approval["value"])]
                        elif approval["type"] == "VRIF":
                            verifies += [int(approval["value"])]
                cherry.set_review(_calculate_score(reviews, -2))
                cherry.set_verify(_calculate_score(verifies, -1))

    return cherry


def _update_cherrypicks(server, manifest, source, target, dry_run):
    ''' Connect to the `server` and get the list of cherry picks for the
    `source` and `target` combination.  For each cherry pick, find the current
    status from Gerrit and then update on the status server if the status has
    changed.  If `dry_run` is True, don't actually update the status on the
    server.
    Skip any cherry picks with error status.
    Raise GerritQueryError if the gerrit query returns an error.
    Return total cherry picks processed, total skipped, total
    updated, and total errors occurred.
    '''
    cherries = server.get_old_cherrypicks(manifest, source, target)
    total = len(cherries)

    errors = 0
    skipped = 0
    updated = 0

    if total:
        gerrit = GerritSshConnection(GERRIT_URL)
        for cherry in cherries:
            try:
                # No need to update the status if it's already merged
                if cherry.status != "MERGED":
                    cherry = _update_status_from_gerrit(gerrit, cherry)

                if cherry.is_dirty():
                    logging.info("Updating: %s", str(cherry))
                    if not dry_run:
                        server.update_cherrypick_status(manifest,
                                                        source,
                                                        target,
                                                        cherry)
                    updated += 1
                else:
                    logging.info("Skipping: %s,%s",
                                 cherry.project, cherry.sha1)
                    skipped += 1
            except CherrypickStatusError, e:
                errors += 1
                logging.error("Cherry pick status error: %s", e)
            except CMServerError, e:
                errors += 1
                logging.error("CM server error: %s", e)
            except GerritQueryError, e:
                errors += 1
                logging.error("Gerrit query error: %s", e)
            except ChildExecutionError, e:
                errors += 1
                logging.error("Gerrit query execution error: %s", e)

    return total, skipped, updated, errors


def _main():
    usage = "usage: %prog --source SOURCE --target TARGET [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("", "--source", action="store", default=None,
                      dest="source", help="Source branch.")
    parser.add_option("", "--target", action="store", default=None,
                      dest="target", help="Target branch.")
    parser.add_option("", "--manifest", action="store",
                      default="platform/manifest",
                      dest="manifest", help="Manifest git name.")
    parser.add_option("", "--dry-run", dest="dry_run", action="store_true",
                      help="Do everything except actually update the status.")
    parser.add_option("", "--server", dest="server",
                      help="IP address or name of the CM server.",
                      action="store", default=DEFAULT_SERVER)
    parser.add_option("-v", "--verbose", dest="verbose", default=0,
                      action="count", help="Verbose logging.")
    (options, _args) = parser.parse_args()

    level = logging.WARNING
    logging.basicConfig(format='[%(levelname)s] %(message)s',
                        level=level)
    if (options.verbose > 1):
        level = logging.DEBUG
    elif (options.verbose > 0):
        level = logging.INFO
    logging.getLogger().setLevel(level)

    try:
        if not options.source:
            parser.error("Must specify --source")
        if not options.target:
            parser.error("Must specify --target")

        server = CMServer(options.server)
        logging.info("Updating status for %s -> %s on manifest %s",
                     options.source, options.target, options.manifest)

        total, skipped, updated, errors = _update_cherrypicks(server,
                                                              options.manifest,
                                                              options.source,
                                                              options.target,
                                                              options.dry_run)
        logging.info("\nProcessed %d cherry picks\n" +
                     "Updated: %d\n" +
                     "Skipped: %d\n" +
                     "Errors: %d\n", total, updated, skipped, errors)
        return errors
    except CherrypickStatusError, e:
        fatal(1, "Cherry pick status error: %s" % e)
    except CMServerError, e:
        fatal(1, "CM server error: %s" % e)
    except GerritSshConfigError, e:
        fatal(1, "Gerrit SSH error: %s" % e)

if __name__ == "__main__":
    try:
        sys.exit(_main())
    except KeyboardInterrupt:
        sys.exit(1)
