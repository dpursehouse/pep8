#!/usr/bin/env python

""" Migrate cherry pick status from the old server to the new one. """

import logging
import optparse
import re

from cm_server import CherrypickStatus, CherrypickStatusError
from cm_server import CMServer, CMServerError
from semcutil import fatal


class CherrypickStatusOld(object):
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
        self.change_nr = None
        self.error = None
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


def get_legacy_cherries(server, target):
    ''' Get legacy cherries from `server` for `target`.
    '''
    cherries = []
    try:
        data = server.get_old_cherrypicks_legacy(target)
    except (CMServerError, CherrypickStatusError), err:
        fatal(1, "Error getting legacy cherry data: %s" % err)
    for cherry in data:
        try:
            old_status = CherrypickStatusOld(cherry)
            new_status = CherrypickStatus()
        except CherrypickStatusError, err:
            message = "Status error: %s" % err
            logging.error(message)
            continue

        new_status.sha1 = old_status.sha1
        new_status.project = old_status.project
        new_status.branch = old_status.branch
        new_status.change_nr = old_status.change_nr
        new_status.review = old_status.review
        new_status.verify = old_status.verify
        new_status.status = old_status.status
        new_status.message = old_status.error
        new_status.dms = old_status.dms.split('-')
        cherries.append(new_status)
    return cherries


def get_migrated_cherries(server, source, target):
    ''' Get the already migrated cherries from `server` for `source`
    and `target`.
    '''
    try:
        cherries = server.get_old_cherrypicks("platform/manifest",
                                              source, target)
        return [cherry.sha1 for cherry in cherries]
    except (CMServerError, CherrypickStatusError), err:
        fatal(1, "Error getting migrated cherry data: %s" % err)


def migrate(old_server, new_server, source, target, dry_run=False):
    ''' Migrate cherrypick status date from `old_server` to `new_server`
    for `source` and `target` combination.
    '''
    errors = []
    already_migrated = 0
    migrated = 0
    skipped = 0
    server_new = CMServer(new_server)
    server_old = CMServer(old_server)
    legacy_cherries = get_legacy_cherries(server_old, target)
    migrated_cherries = get_migrated_cherries(server_new, source, target)
    for cherry in legacy_cherries:
        if cherry.sha1 in migrated_cherries:
            logging.info("%s: Already migrated", cherry.sha1)
            already_migrated += 1
            continue
        if cherry.message and cherry.message.startswith("Failed to push"):
            logging.info("%s: Not migrating \"Failed to push\"", cherry.sha1)
            skipped += 1
            continue
        logging.info("%s: Migrating...", cherry.sha1)
        if not dry_run:
            try:
                server_new.update_cherrypick_status("platform/manifest",
                                                    source,
                                                    target,
                                                    cherry)
                migrated += 1
            except CMServerError, err:
                message = "%s: %s" % (cherry.sha1, err)
                logging.error(message)
                errors.append(message)
    logging.info("\nMigrated %d cherries", migrated)
    logging.info("\nSkipped %d \"Failed to push\" cherries", skipped)
    logging.info("Skipped %d already migrated cherries", already_migrated)
    if errors:
        logging.error("%d Errors:", len(errors))
        for error in errors:
            logging.error(error)
        return 1
    return 0


def _main():
    usage = "usage: %prog --source SOURCE --target TARGET " \
            "--old-server SERVER --new-server SERVER [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("", "--source", action="store", default=None,
                      dest="source", help="Source branch.")
    parser.add_option("", "--target", action="store", default=None,
                      dest="target", help="Target branch.")
    parser.add_option("", "--dry-run", dest="dry_run", action="store_true",
                      help="Do everything except actually update the " \
                          "status.")
    parser.add_option("", "--old-server", dest="oldserver",
                      help="IP address or name of the old CM server.",
                      action="store", default=None)
    parser.add_option("", "--new-server", dest="newserver",
                      help="IP address or name of the new CM server.",
                      action="store", default=None)
    (options, _args) = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(message)s')

    if not options.source:
        parser.error("Must specify --source")
    if not options.target:
        parser.error("Must specify --target")
    if not options.oldserver:
        parser.error("Must specify --old-server")
    if not options.newserver:
        parser.error("Must specify --new-server")

    return migrate(options.oldserver, options.newserver,
                   options.source, options.target, options.dry_run)

if __name__ == "__main__":
    exit(_main())
