""" Classes to interface with the CM server.
"""

from base64 import encodestring
from httplib import HTTPException
import logging
import netrc
from os.path import expanduser, isfile
from StringIO import StringIO
import urllib
import urllib2
from urlparse import urljoin

from branch_policies import BranchPolicies
from cherry_status import CherrypickStatus, CherrypickStatusError
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


class CredentialsError(Exception):
    ''' Raised when there is a problem getting the credentials from the
    .netrc file.
    '''


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
        except (HTTPException, urllib2.URLError), error:
            if isinstance(error, urllib2.HTTPError):
                if error.code in self.ERROR_CODES:
                    raise globals()[self.ERROR_CODES[error.code]]()

            raise CMServerError("Unexpected error: %s" % error)

    @retry(CMServerInternalError, tries=2)
    def get_branch_config(self, manifest_name):
        ''' Get the branch configurations for the branches on the manifest
        specified by `manifest_name`.
        Return a BranchPolicies object encapsulating the config returned from
        the server.
        Raise some form of CMServerError, BranchPolicyError, or
        CherrypickPolicyError if anything goes wrong.
        '''
        path = GET_BRANCH_CONFIG % {'manifest': urllib.quote(manifest_name)}
        result = self._open_url(path)
        return BranchPolicies(StringIO(result.read()))

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
