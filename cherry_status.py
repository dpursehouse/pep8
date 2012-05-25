""" Classes to encapsulate cherrypick status data.
"""

import json
import urllib


class CherrypickStatusError(Exception):
    ''' CherrypickStatusError is raised when something goes wrong
    setting or getting cherry pick status to/from the status server.
    '''


class CherrypickStatus(object):
    ''' Encapsulate the status of a cherry pick.
    '''

    def __init__(self):
        self.sha1 = None
        self.project = None
        self.branch = None
        self.dms = []
        self.message = None
        self.change_nr = 0
        self.review = 0
        self.verify = 0
        self.status = None
        self.dirty = False

    def set_status(self, status):
        ''' Update status with `status` if it has changed and
        set the state to dirty.
        '''
        if self.status != status:
            self.status = status
            self.dirty = True

    def set_message(self, message):
        ''' Update message with `message` if it has changed and
        set the state to dirty.
        '''
        if self.message != message:
            self.message = message
            self.dirty = True

    def set_change_nr(self, change_nr):
        ''' Update change_nr value with `change_nr` if it has changed and
        set the state to dirty.
        '''
        if self.change_nr != change_nr:
            self.change_nr = change_nr
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

    def set_dms(self, dms):
        ''' Update dms value with `dms` if it has changed and
        set the state to dirty.
        '''
        if dms:
            dmslist = dms.split('-')
            if dmslist and self.dms != dmslist:
                self.dms = dmslist
                self.dirty = True
        elif self.dms:
            self.dms = []
            self.dirty = True

    def is_dirty(self):
        ''' Check if the cherry pick is dirty, i.e. has been updated.
        Return True if so, otherwise False.
        '''
        return self.dirty

    @staticmethod
    def cherries_from_json(data):
        ''' Parse `data` as JSON data and return a list of CherrypickStatus
        objects.
        Raise CherrypickStatusError if the data is malformed.
        '''
        cherries = []
        json_data = json.loads(data)
        for entry in json_data:
            if not "model" in entry:
                raise CherrypickStatusError("Invalid status data format")
            if not "fields" in entry:
                raise CherrypickStatusError("Invalid status data format")
            if entry["model"] == "harvest.cherry":
                cherry = CherrypickStatus()
                cherry.from_json(entry["fields"])
                cherries.append(cherry)
        return cherries

    def from_json(self, json_data):
        ''' Initialise the class with `json_data`.
        Raise CherrypickStatusError if the data is malformed.
        '''
        if not "commit" in json_data:
            raise CherrypickStatusError("commit missing in json data:\n%s" % \
                                        json_data)

        try:
            commit = json_data["commit"]["fields"]
            self.project = commit["project"]["fields"]["name"]
            self.dms = commit["dms"].split(',')
            self.sha1 = commit["sha1"]
        except KeyError, err:
            raise CherrypickStatusError("missing json data: %s" % err)

        if "branch" in json_data:
            self.branch = json_data["branch"]
        if "message" in json_data:
            self.message = json_data["message"]
        if "change_nr" in json_data and json_data["change_nr"] is not None:
            self.change_nr = int(json_data["change_nr"])
        if "review" in json_data:
            self.review = int(json_data["review"])
        if "verify" in json_data:
            self.verify = int(json_data["verify"])
        if "status" in json_data:
            self.status = json_data["status"]
        self.dirty = False

    def __str__(self):
        ''' Return URL-encoded string of the status data.  Fields are only
        included if they are set.  The sha1 field is not included.
        '''
        data = []
        if self.project:
            data.append(("project", self.project))
        if self.branch:
            data.append(("branch", self.branch))
        data.append(("dms", ','.join(self.dms)))
        if self.message is not None:
            data.append(("message", self.message))
        if self.change_nr is not None:
            data.append(("change_nr", self.change_nr))
        data.append(("review", self.review))
        data.append(("verify", self.verify))
        if self.status:
            data.append(("status", self.status))

        return urllib.urlencode(data)
