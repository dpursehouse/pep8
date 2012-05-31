""" Class and support methods to interface with DMS over ODBC. """

import sys

try:
    import pyodbc
except ImportError:
    # If pyodbc cannot be imported, it means it is not installed.
    # Use DMS Tag Server instead.
    from dmsutil import DMSTagServer, DMSTagServerError

from cm_server import get_credentials_from_netrc, CredentialsError


# SQL query to check which of the given DMS are tagged with the
# given tags for the given release
QRY_DMS_FOR_TAGS = """
 select distinct I.id
 from ((((DMSUSER_JPTOH.dbo.issue I
 INNER JOIN DMSUSER_JPTOH.dbo.statedef S
    ON I.state = S.id)
 LEFT OUTER JOIN DMSUSER_JPTOH.dbo.parent_child_links P
    ON I.dbid = P.parent_dbid)
 LEFT OUTER JOIN DMSUSER_JPTOH.dbo.fielddef FD
    ON P.parent_fielddef_id = FD.id)
 LEFT OUTER JOIN DMSUSER_JPTOH.dbo.deliveryrecord D
    ON P.child_dbid = D.dbid)
 where I.dbid <> 0
 and D.deliver_to = '%(targetbranch)s'
 and (%(dmss)s)
 and (%(tags)s)
 and D.decisionstatus = 'Accepted'
 and FD.name = 'Delivery'
 order by I.id ASC
"""

QRY_DMS_AND_TITLES = """
 select distinct I.id, I.title
 from DMSUSER_JPTOH.dbo.issue I
 where I.dbid <> 0
 and (%(dmss)s)
 order by I.id ASC
"""

# Default parameters for connection to the ODBC server
ODBC_DRIVER = "{FreeTDS}"
ODBC_SERVER = "JPTOCLQ201"
ODBC_DATABASE = "DMSUSER_JPTOH"
ODBC_SCHEMA = "DMSUSER_JPTOH"

# Parameters template for connection to the ODBC server
ODBC_PARAMETERS = 'DRIVER=%(driver)s;'\
                  'SERVER=%(server)s;' \
                  'DATABASE=%(database)s;' \
                  'UID=%(username)s;' \
                  'PWD=%(password)s;' \
                  'CurrentSchema=%(schema)s'


def _build_sql_or_query(name, values):
    ''' Build an SQL query from `name` and `values`.

    For example given the parameters:
        `name` - "id"
        `values` - ["1", "2", "3"]

    the returned query string will be:
        "id = '1' or id = '2' or id = '3'"

    Return SQL query as a string.
    '''
    if not name:
        raise ValueError("name must have a value")
    if not values:
        raise ValueError("values must have values")
    return " or ".join(["%s = '%s'" % (name, value) for value in values])


class DMSODBCError(Exception):
    ''' Raised when an error occurs during ODBC operation.
    '''


class DMSODBC(object):
    ''' Class for interfacing with DMS over ODBC.
    '''
    def __init__(self, username=None, password=None,
                driver=ODBC_DRIVER, server=ODBC_SERVER,
                database=ODBC_DATABASE, schema=ODBC_SCHEMA):
        ''' Initialise the ODBC connection with the given parameters.
        Raise DMSODBCError if there is an error getting the server login
        credentials from the .netrc file, or if the login credentials for
        the given `server` were not found in the .netrc file.
        '''
        # Don't need to initialise internal data unless we're using
        # the pyodbc module
        if not 'pyodbc' in sys.modules:
            return

        self.connection = None
        # If either the username or the password is not specified, attempt
        # to get them from the .netrc file
        if (not username) or (not password):
            try:
                username, password = get_credentials_from_netrc(server)
                if (not username) or (not password):
                    raise DMSODBCError("Unable to get login credentials for " \
                                       "%s from .netrc file." % server)
            except CredentialsError, err:
                raise DMSODBCError("Error getting login credentials for %s " \
                                   "from .netrc file: %s" % (server, err))

        self.parameters = ODBC_PARAMETERS % {"driver": driver,
                                             "server": server,
                                             "database": database,
                                             "username": username,
                                             "password": password,
                                             "schema": schema}

    def _get_cursor(self):
        ''' Connect to ODBC if not already connected, and get the cursor.
        Return the cursor.
        Raise pyodbc.Error if error occurs when connecting to ODBC or
        getting the cursor.
        Raise DMSODBCError if pyodbc is not available.
        '''
        if not self.connection:
            try:
                self.connection = pyodbc.connect(self.parameters)
            except NameError:
                raise DMSODBCError("pyodbc is not installed")
        cursor = self.connection.cursor()
        return cursor

    def dms_with_title(self, dmss):
        ''' Return a list of `dmss` and titles in format "ID Title".
        Raise DMSODBCError if any error occurs.
        '''
        # Remove duplicates from the input list
        unique_dmss = list(set(dmss))

        # Fall back to DMS Tag Server if ODBC not available
        if not 'pyodbc' in sys.modules:
            try:
                return DMSTagServer().dms_with_title(unique_dmss)
            except DMSTagServerError, e:
                raise DMSODBCError("Fallback to DMS Tag Server failed: %s" % e)

        issues_list = []
        if unique_dmss:
            dms_query = _build_sql_or_query("I.id", unique_dmss)
            try:
                query = QRY_DMS_AND_TITLES % {"dmss": dms_query}
                result = self._get_cursor().execute(query)
            except pyodbc.Error, err:
                raise DMSODBCError("ODBC driver error: %s" % err)
            issues_list = ["%s %s" % (row.id, row.title) for row in result]

        return issues_list

    def dms_for_tags(self, dmss, tags, target_branch):
        ''' Return a list of the `dmss` which are tagged with at least one of
        the `tags` for `target_branch`.
        Raise DMSODBCError if any error occurs.
        '''
        if not target_branch:
            raise DMSODBCError("Target branch must be specified")

        # Remove any duplicates from the input list
        unique_dmss = list(set(dmss))
        unique_tags = list(set(tags))

        # Fall back to DMS Tag Server if ODBC not available
        if not 'pyodbc' in sys.modules:
            try:
                return DMSTagServer().dms_for_tags(unique_dmss,
                                                   unique_tags,
                                                   target_branch)
            except DMSTagServerError, e:
                raise DMSODBCError("Fallback to DMS Tag Server failed: %s" % e)

        tagged_dms = []
        if unique_dmss and unique_tags:
            dms_query = _build_sql_or_query("I.id", unique_dmss)
            tags_query = _build_sql_or_query("D.fix_for", unique_tags)
            try:
                query = QRY_DMS_FOR_TAGS % {"targetbranch": target_branch,
                                            "dmss": dms_query,
                                            "tags": tags_query}
                result = self._get_cursor().execute(query)
            except pyodbc.Error, err:
                raise DMSODBCError("ODBC driver error: %s" % err)
            tagged_dms = [row.id for row in result]

        return tagged_dms
