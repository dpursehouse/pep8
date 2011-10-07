import socket

#Server communication tags
SRV_DMS_STATUS = 'DMS_STATUS'
SRV_CHERRY_UPDATE = 'CHERRY_UPDATE'
SRV_CHERRY_GET = 'CHERRY_GET'
SRV_ERROR = 'SRV_ERROR'
SRV_END = '|END'


class DMSTagServerError(Exception):
    '''DMSTagServerError is raised when an error occurs during
    connection to the tag server
    '''


class DMSTagServer():
    '''
    This is interface to send request to dms_tag_server.py to collect old and
    save new cherry pick records and dms for tags.
    '''
    def __init__(self, server, port=55655):
        '''
        Constructor
        '''
        self.server = server
        self.port = port

    def dms_for_tags(self, dmss, dms_tags, target_branch):
        """
        Connect to tag server and collect dmss tagged with one of the
        `dms_tags`, specific to the `target_branch`
        """
        dms_list = {}
        for tag in dms_tags.split(','):
            tagged_dms = self.query_srv('%s|%s|%s|%s'
                                        % (SRV_DMS_STATUS,
                                        tag, dmss, target_branch))
            if tagged_dms == None:
                return None
            dms_list[tag] = tagged_dms
        return dms_list

    def query_srv(self, query):
        '''Send the query to server and collect the data
        Raise DMSTagServerError if any error occurs
        '''
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # Disconnect after 30 sec
            sock.connect((self.server, self.port))
            sock.send(query)
            sock.send(SRV_END)
            data = sock.recv(1024)
            msg = ''
            while 1:
                msg = msg + data
                if SRV_END in str(data):
                    break
                data = sock.recv(1024)
            sock.close()
            if SRV_ERROR in msg:
                raise DMSTagServerError('Server side error: ' + msg)
            return msg.split('|')[0]
        except socket.timeout, err:
            raise DMSTagServerError('Server timeout')
        except socket.error, err:
            raise DMSTagServerError('Socket error: %s' % err[1])

    def retrieve(self, branch):
        '''Collect data from server of branch'''
        return self.query_srv('%s|%s' % (SRV_CHERRY_GET, branch))

    def update(self, branch, records):
        '''Save data into server for branch'''
        return self.query_srv('%s|%s|%s' % (SRV_CHERRY_UPDATE, branch,
                                           '\n'.join(records)))
