""" Interface to the DMS tag server. """

import socket

#Server communication tags
SRV_DELIMITER = ':EoL:'
SRV_DMS_STATUS = 'DMS_STATUS'
SRV_DMS_INFO = 'DMS_INFO'
SRV_ERROR = 'SRV_ERROR'
SRV_END = '|END'

BUFFER_LEN = 1024

# Maximum number of DMS sent to the server per request
MAX_DMS_PER_REQUEST = 100


def split_to_block(dmss):
    ''' Generator function to split the list of `dmss` into blocks of
    maximum `MAX_DMS_PER_REQUEST` items.
    '''
    index = 0
    total = len(dmss)
    while index < total:
        yield dmss[index:index + MAX_DMS_PER_REQUEST]
        index += MAX_DMS_PER_REQUEST


class DMSTagServerError(Exception):
    '''DMSTagServerError is raised when an error occurs during
    connection to the tag server
    '''


class DMSTagServer():
    '''
    This is interface to send request to dms_tag_server.py to get dms for tags.
    '''
    def __init__(self, server, port=55655, timeout=30):
        '''
        Constructor
        '''
        self.server = server
        self.port = port
        self.timeout = timeout

    def dms_for_tags(self, dmss, tags, target_branch):
        """
        Connect to tag server and collect `dmss` tagged with one of the
        `tags`, specific to the `target_branch`.
        """

        # Remove duplicates from the list
        unique_dmss = list(set(dmss))

        # If there are no DMS in the list, return immediately
        if not unique_dmss:
            return None

        # Send to the tag server in multiple batches.
        result_dms = []
        for dms_block in split_to_block(unique_dmss):
            # Get the list of tagged DMS from the tag server. The result is
            # a comma-separated list of DMS.
            msg = self.query_srv('%s|%s|%s|%s' % (SRV_DMS_STATUS,
                                                  ','.join(tags),
                                                  ','.join(dms_block),
                                                  target_branch))
            dms_list = msg.split('|')[0]
            if dms_list:
                result_dms += dms_list.split(',')

        return ','.join(result_dms)

    def dms_with_title(self, dmss):
        """
        Connect to tag server and get the title for the list of `dmss`.
        Returns a list of strings in the format "IssueID Title".
        """

        issue_list = []

        # Remove duplicates from the list
        unique_dmss = list(set(dmss))

        # If there are no DMS in the list, return immediately
        if not unique_dmss:
            return issue_list

        # Send to the tag server in multiple batches.
        for dms_block in split_to_block(unique_dmss):
            msg = self.query_srv('%s|%s' % (SRV_DMS_INFO, ','.join(dms_block)))

            for line in msg.split(SRV_DELIMITER):
                (issue, title) = line.split('|', 1)
                issue_list.append('%s %s' % (issue, title))

        return issue_list

    def query_srv(self, query):
        '''Send the query to server and collect the data
        Raise DMSTagServerError if any error occurs
        '''
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.server, self.port))
            totalsent = 0
            while totalsent != len(query):
                totalsent += sock.send(query[totalsent:totalsent + BUFFER_LEN])
            sock.send(SRV_END)
            data = sock.recv(BUFFER_LEN)
            msg = ''
            while 1:
                msg = msg + data
                if msg.endswith(SRV_END):
                    break
                data = sock.recv(BUFFER_LEN)
            sock.close()
            # Strip the 'SRV_END' part from the result
            msg = msg.rstrip(SRV_END)
            if SRV_ERROR in msg:
                msg = msg.strip(SRV_ERROR)
                raise DMSTagServerError('Server side error' + msg)
            return msg
        except socket.timeout, err:
            raise DMSTagServerError('Server timeout')
        except socket.error, err:
            raise DMSTagServerError('Socket error: %s' % err[1])
