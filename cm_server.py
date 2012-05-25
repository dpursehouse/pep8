""" Classes to interface with the CM server.
"""

from base64 import encodestring
import json
import logging
import netrc
from os.path import expanduser, isfile
import urllib
import urllib2
from urlparse import urljoin

from retry import retry

# Default address of the server
DEFAULT_SERVER = "cmweb.sonyericsson.net"

# URL for cherrypick status update
UPDATE_CHERRYPICK_STATUS = "/harvest/cherry/%(manifest)s/%(target)s/" \
                           "%(source)s/%(sha1)s/update/"

# URL for cherrypick status query
GET_CHERRYPICK_STATUS = "/harvest/cherries/manifest/%(manifest)s/" \
                        "target/%(target)s/source/%(source)s/format/json/"

# URL for branch configuration query
GET_BRANCH_CONFIG = "/explorer/system-branches/%(manifest)s/xml/"

# Path to the default .netrc file
DEFAULT_NETRC_FILE = expanduser("~/.netrc")


class CMServerError(Exception):
    ''' Raised when something goes wrong when accessing the server.
    '''


class CMServerAuthenticationError(CMServerError):
    ''' Raised when the server returns 401 Unauthorized.
    '''
    def __init__(self):
        super(CMServerAuthenticationError, self).__init__(
            "Authentication Error")


class CMServerPermissionError(CMServerError):
    ''' Raised when the server returns 403 Forbidden.
    '''
    def __init__(self):
        super(CMServerPermissionError, self).__init__("Permission Error")


class CMServerResourceNotFoundError(CMServerError):
    ''' Raised when the server returns 404 Not Found.
    '''
    def __init__(self):
        super(CMServerResourceNotFoundError, self).__init__("Not Found")


class CMServerInternalError(CMServerError):
    ''' Raised when the server returns 500 Internal Server Error.
    '''
    def __init__(self):
        super(CMServerInternalError, self).__init__("Internal Error")


class CherrypickStatusError(Exception):
    ''' CherrypickStatusError is raised when something goes wrong
    setting or getting cherry pick status to/from the status server.
    '''


class CredentialsError(Exception):
    ''' Raised when there is a problem getting the credentials from the
    .netrc file.
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


def get_credentials_from_netrc(server_name, netrc_file=DEFAULT_NETRC_FILE):
    ''' Return the login credentials (username, password) for `server_name`
    from `netrc_file`.  Return empty strings if the `server_name` was not
    listed in the netrc file.
    Raise CredentialsError if anything goes wrong.
    '''
    username = ""
    password = ""

    if not isfile(netrc_file):
        raise CredentialsError(".netrc file %s does not exist" % netrc_file)

    try:
        info = netrc.netrc(netrc_file)
        username, _account, password = info.authenticators(server_name)
    except netrc.NetrcParseError, err:
        raise CredentialsError(".netrc parse error: %s", err)
    except TypeError:
        # TypeError is raised when the server is not listed in the
        # .netrc file.
        pass

    return (username, password)


class CMServer(object):
    ''' Encapsulate access to the CM server.
    '''

    # Error codes that are expected.  Map the error codes to the corresponding
    # exception class names.
    ERROR_CODES = {401: "CMServerAuthenticationError",
                   403: "CMServerPermissionError",
                   404: "CMServerResourceNotFoundError",
                   500: "CMServerInternalError"}

    def __init__(self, server=DEFAULT_SERVER):
        ''' Initialise self with the `server` address.
        Raise CredentialsError if an error occurs when parsing the .netrc file.
        '''
        self._server = server
        self._auth = ""

        # Get username and password from .netrc and generate authentication
        # token to be passed in HTTP headers when communicating with the server.
        user, pwd = get_credentials_from_netrc(self._server)
        logging.debug("Username: %s", user if user else "None")
        self._auth = encodestring("%s:%s" % (user, pwd)).replace('\n', '')

    def _open_url(self, path, data=None):
        ''' Open the URL on the server specified by `path`, optionally with
        data given in `data`, and return a file-like object representing
        the opened URL.
        Raise some form of CMServerError if anything goes wrong.
        '''
        try:
            url = urljoin('http://' + self._server, path)
            if data:
                url = urljoin(url, "?" + data)
            logging.debug("URL: %s", url)
            request = urllib2.Request(url)
            request.add_header("Authorization", "Basic %s" % self._auth)
            return urllib2.urlopen(request)
        except urllib2.URLError, error:
            if isinstance(error, urllib2.HTTPError):
                if error.code in self.ERROR_CODES:
                    raise globals()[self.ERROR_CODES[error.code]]()

            raise CMServerError("Unexpected error: %s" % error)

    @retry(CMServerInternalError, tries=2)
    def get_branch_config(self, manifest_name):
        ''' Get the branch configurations for the branches on the manifest
        specified by `manifest_name`.
        Return the config XML as returned from the server.
        Raise some form of CMServerError if anything goes wrong.
        '''
        path = GET_BRANCH_CONFIG % {'manifest': urllib.quote(manifest_name)}
        result = self._open_url(path)
        return result.read()

    @retry(CMServerInternalError, tries=2)
    def get_old_cherrypicks(self, manifest_name, source, target):
        ''' Get the list of existing cherry picks for `source` and `target`
        branch combination on the manifest specified by `manifest_name`.
        Return a list of CherrypickStatus objects.
        Raise some form of CMServerError or CherrypickStatusError if anything
        goes wrong.
        '''
        try:
            path = GET_CHERRYPICK_STATUS % \
                   {'manifest': urllib.quote(manifest_name),
                    'target': urllib.quote(target),
                    'source': urllib.quote(source)}
            data = self._open_url(path).read()
            return CherrypickStatus.cherries_from_json(data)
        except ValueError, err:
            raise CherrypickStatusError("Error in JSON data: %s" % err)

    @retry(CMServerInternalError, tries=2)
    def update_cherrypick_status(self, manifest_name, source, target, status):
        ''' Update cherrypick `status` for `source` and `target` branch
        combination on the manifest specified by `manifest_name`.
        Raise some form of CMServerError if anything goes wrong.
        '''
        path = UPDATE_CHERRYPICK_STATUS % \
               {'manifest': urllib.quote(manifest_name),
                'target': urllib.quote(target),
                'source': urllib.quote(source),
                'sha1': urllib.quote(status.sha1)}
        _result = self._open_url(path, data=str(status))
