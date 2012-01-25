import socket

#Server communication tags
SRV_DELIMITER = ':EoL:'
SRV_DMS_STATUS = 'DMS_STATUS'
SRV_DMS_INFO = 'DMS_INFO'
SRV_ERROR = 'SRV_ERROR'
SRV_END = '|END'

BUFFER_LEN = 1024


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

    def dms_for_tags(self, dmss, dms_tags, target_branch):
        """
        Connect to tag server and collect dmss tagged with one of the
        `dms_tags`, specific to the `target_branch`
        """
        msg = self.query_srv('%s|%s|%s|%s' % (SRV_DMS_STATUS, dms_tags,
                             dmss, target_branch))
        return msg.split('|')[0]

    def dms_with_title(self, dmss):
        """
        Connect to tag server and get the title for the list of dmss
        Returns a list of line with issue ID followed by title
        """
        issue_list = []
        msg = self.query_srv('%s|%s' % (SRV_DMS_INFO, dmss))
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
                if SRV_END in str(data):
                    break
                data = sock.recv(BUFFER_LEN)
            sock.close()
            if SRV_ERROR in msg:
                raise DMSTagServerError('Server side error: ' + msg)
            # Strip the 'SRV_END' part from the result
            msg = msg.rstrip(SRV_END)
            return msg
        except socket.timeout, err:
            raise DMSTagServerError('Server timeout')
        except socket.error, err:
            raise DMSTagServerError('Socket error: %s' % err[1])
