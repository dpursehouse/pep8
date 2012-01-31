""" Classes to access the cherry pick status server.
"""

import httplib
import urllib

# Default address of the status server
DEFAULT_STATUS_SERVER = "android-cm-web.sonyericsson.net"

# Endpoint for list of all targets
STATUS_TARGETS = "/cherrypick/query.php?alltargets"

# Endpoint for status updates
STATUS_UPDATE = "/cherrypick/update.php?target=%s&data=%s"

# Endpoint for status queries
STATUS_GET = "/cherrypick/query.php?target=%s"


class CherrypickStatusError(Exception):
    ''' CherrypickStatusError is raised when something goes wrong
    setting or getting cherry pick status to/from the status server.
    '''


class CherrypickStatusServer:
    ''' Encapsulate access to the cherry pick status server for
    cherry pick status get/set operations.
    '''

    def __init__(self, server=DEFAULT_STATUS_SERVER):
        ''' Initialise self with the `server` address.
        '''
        self._server = server

    def get_all_targets(self):
        ''' Get the list of targets for which the status server has
        cherry pick status.
        Return a list of targets, or empty list if there are none.
        Raise CherrypickStatusError if anything goes wrong.
        '''
        targets = []
        try:
            conn = httplib.HTTPConnection(self._server)
            conn.request("GET", STATUS_TARGETS)
            response = conn.getresponse()
            if response.status != httplib.OK:
                raise CherrypickStatusError("Unexpected server response: %d" % \
                                            response.status)
            data = response.read()
            targets = data.rstrip().split(',')
            conn.close()
            return targets
        except httplib.HTTPException, e:
            raise CherrypickStatusError("HTTP error: %s" % e)

    def get_old_cherrypicks(self, target=""):
        ''' Get the list of existing cherry picks for `target` branch.
        Return a list of cherry picks.
        Raise CherrypickStatusError if anything goes wrong.
        '''
        cherries = []
        try:
            conn = httplib.HTTPConnection(self._server)
            conn.request("GET", STATUS_GET % urllib.quote(target))
            response = conn.getresponse()
            if response.status != httplib.OK:
                raise CherrypickStatusError("Unexpected server response: %d" % \
                                            response.status)
            data = response.read()
            cherries = data.rstrip().split('\n')
            conn.close()
            return cherries
        except httplib.HTTPException, e:
            raise CherrypickStatusError("HTTP error: %s" % e)

    def update_status(self, target, status):
        ''' Update `status` for `target` branch.
        Raise CherrypickStatusError if anything goes wrong.
        '''
        try:
            conn = httplib.HTTPConnection(self._server)
            conn.request("GET", STATUS_UPDATE % \
                         (urllib.quote(target), urllib.quote(status)))
            response = conn.getresponse()
            if response.status != httplib.OK:
                raise CherrypickStatusError("Unexpected server response: %d" % \
                                            response.status)
            conn.close()
        except httplib.HTTPException, e:
            raise CherrypickStatusError("HTTP error: %s" % e)
