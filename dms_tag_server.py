#!/usr/bin/env python

'''
@author: Ekramul Huq

@version: 0.2
'''

DESCRIPTION = \
'''
The purpose of this server is following:
    1. Collect DMSs of a tag from CQ and send back the list
    to requester
    2. Save the list of cherry pick history for each target
    branch
    3. Send back the history of cherry pick to requester
This script is using run_query.pl script to collect data from CQ.
'''
import pythoncom
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import string
import sys
import subprocess
import datetime
import netrc
import thread
import os
from _winreg import *

HOST = ''
PORT = 55655              # Arbitrary non-privileged port

#Server communication tags
SRV_DMS_STATUS = 'DMS_STATUS'
SRV_CHERRY_UPDATE = 'CHERRY_UPDATE'
SRV_CHERRY_GET = 'CHERRY_GET'
SRV_ERROR = 'SRV_ERROR'
SRV_END = '|END'
SCRIPT_DIR = ''

USAGE = "Usage: dms_tag_server.py [install | start | stop | remove | -h]"


def initialize_path():
    '''Parse the arguments (if any) and initialize the working path'''
    if len(sys.argv) < 1:
        print >> sys.stderr, "Insufficient arguments"
        print >> sys.stderr, USAGE
        sys.exit(1)
    if sys.argv[1] == '-h':
        print >> sys.stdout, USAGE
        print >> sys.stdout, DESCRIPTION
        sys.exit(0)

    SCRIPT_DIR = string.replace(
                                os.path.realpath(
                                os.path.dirname(sys.argv[0])), '\\', '\\\\')

    open(SCRIPT_DIR + "\\new_log.txt", "wb").write("")
    open(SCRIPT_DIR + "\\cqperl_log.txt", "wb").write("")

    (account, password) = parse_netrc(SCRIPT_DIR)

    if account == -1:
        print >> sys.stderr, "Error reading .netrc file"
        sys.exit(1)

    cInstallOptions = "--username=corpusers\\" \
                        + str(account) + " --password=" \
                        + str(password) + " --startup=auto"
    win32serviceutil.HandleCommandLine(DmsTagServer,
                                       serviceClassString=None,
                                       argv=sys.argv,
                                       customInstallOptions=cInstallOptions)


def parse_netrc(SCRIPT_DIR):
    #read username and password from netrc file
    #.netrc file should have the following line
    #machine dms_tag_server account JPTO login <loginid> password <password>

    home = os.environ['HOMEDRIVE'] + os.environ['HOMEPATH']

    try:
        host = netrc.netrc(home + '\\.netrc').hosts['dms_tag_server']
        return (host[0], host[2])
    except KeyError:
        open(SCRIPT_DIR + "\\new_log.txt", "ab").write(
            'dms_tag_server info is not in .netrc file\n')
    except netrc.NetrcParseError:
        open(SCRIPT_DIR + "\\new_log.txt", "ab").write(
            'Error parsing .netrc file\n')
    except IOError:
        host = ['-1']
        open(SCRIPT_DIR + "\\new_log.txt", "ab").write(
            'Error opening .netrc file\n ' + host[0])
    except:
        open(SCRIPT_DIR + "\\new_log.txt", "ab").write(
            'Unexpected error %s\n' % sys.exc_info()[0])
    return (-1, -1)


class DmsTagServer (win32serviceutil.ServiceFramework):
    _svc_name_ = "DMSTagServer"
    _svc_display_name_ = "DMS Tag Server"
    _svc_description_ = "DMS Query Server for Cherry Picking"

    def __init__(self, args):
        try:
            win32serviceutil.ServiceFramework.__init__(self, args)
            print "Installed DMSTagServer as a windows service"
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            socket.setdefaulttimeout(30)
            self.keep_running = 1
        except:
            print "Service exception"
            sys.exit(1)

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.keep_running = 0

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        regpath = "SYSTEM\\CurrentControlSet\\Services\\DMSTagServer"
        try:
            regkey = OpenKey(HKEY_LOCAL_MACHINE, regpath)
            cwd = string.replace(QueryValue(regkey, "PythonClass"),
                                '\\', '\\\\')
            CloseKey(regkey)
        except:
            servicemanager.LogMsg(servicemanager.EVENTLOG_ERROR_TYPE,
                              servicemanager.PYS_SERVICE_STOPPING,
                              (self._svc_name_, SCRIPT_DIR \
                                + 'Unable to access the registry.\n' \
                                + 'Try installing the service again'))
            self.SvcStop()
            sys.exit(1)

        cwd = os.path.dirname(cwd)
        if not os.path.exists(cwd):
            servicemanager.LogMsg(servicemanager.EVENTLOG_ERROR_TYPE,
                              servicemanager.PYS_SERVICE_STOPPING,
                              (self._svc_name_,
                              'The directory \"' + cwd + '\" is not found'))
            self.SvcStop()
            sys.exit(1)
        elif not os.path.exists(cwd + "\\dms_tag_server.py"):
            servicemanager.LogMsg(servicemanager.EVENTLOG_ERROR_TYPE,
                              servicemanager.PYS_SERVICE_STOPPING,
                              (self._svc_name_, 'The file \"' + cwd \
                              + '\\dms_tag_server.py\" is not found'))
            self.SvcStop()
            sys.exit(1)
        elif not os.path.exists(cwd + "\\run_query.pl"):
            servicemanager.LogMsg(servicemanager.EVENTLOG_ERROR_TYPE,
                              servicemanager.PYS_SERVICE_STOPPING,
                              (self._svc_name_, 'The file \"' + cwd \
                              + '\\run_query.pl\" is not found'))
            self.SvcStop()
            sys.exit(1)

        os.chdir(cwd)
        self.run_server(cwd)

    def run_server(self, SCRIPT_DIR):
        '''
        Start socket server and listen on a port for client request.
        if any client connected, start a new thread and process client request
        '''
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind((HOST, PORT))
        except socket.error, (value, msg):
            servicemanager.LogMsg(servicemanager.EVENTLOG_ERROR_TYPE,
                              servicemanager.PYS_SERVICE_STOPPING,
                              (self._svc_name_,
                                'Socket Creation Error:' + msg))
            self.SvcStop()
            sys.exit(1)

        open(SCRIPT_DIR + "\\new_log.txt", "wb").write("Server startted\n")

        (account, password) = parse_netrc(SCRIPT_DIR)
        if account == -1:
            servicemanager.LogMsg(servicemanager.EVENTLOG_ERROR_TYPE,
                              servicemanager.PYS_SERVICE_STOPPING,
                              (self._svc_name_,
                                'Error reading .netrc file.\n' \
                                + 'See the log for more details ' + account))
            self.SvcStop()
            sys.exit(1)

        while self.keep_running:
            s.listen(1)
            try:
                conn, addr = s.accept()
                thread.start_new_thread(process_req, (SCRIPT_DIR, conn, addr,
                                            account, password))
            except socket.timeout:
                continue


def process_req(SCRIPT_DIR, channel, address, user, password):
    '''Listen request of client and send data back to client'''
    request = ''
    data = channel.recv(1024)
    while 1:
        request = request + data
        if SRV_END in str(data):
            break
        data = channel.recv(1024)

    data_list = request.split('|')
    # Error handling for insufficient data in the stream
    if len(data_list) < 3:
        error_str = "Insufficient data from %s. Data received was: %s\n" % \
                     (address, request)
        open(SCRIPT_DIR + "\\cqperl_log.txt", "ab").write(error_str)
        channel.send(SRV_ERROR + SRV_END)
        channel.close()
        return

    req_type = data_list[0]
    tag = data_list[1]
    issues = data_list[2]
    # Make it compatible with old cherry-pick script
    deliver_to = ''
    if len(data_list) > 3:
        deliver_to = data_list[3]

    open(SCRIPT_DIR + "\\new_log.txt", "ab").write(
            'Connected by %s at %s for %s \n' % (address,
            datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S"), req_type))
    if req_type == SRV_DMS_STATUS:
        cmd = ['cqperl', SCRIPT_DIR + '\\run_query.pl',
                '-user', user, '-pwd', password, '-issues', issues,
                '-log', 'cherry.log', '-list', '-site', 'JPTO']
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            out, err = process.communicate()
            if process.poll() != 0:
                open(SCRIPT_DIR + "\\cqperl_log.txt", "ab").write(str(err))
                channel.send(SRV_ERROR + SRV_END)
                channel.close()
                return
        except Exception, exp:
            open(SCRIPT_DIR + "\\cqperl_log.txt", "ab").write(str(exp))
            channel.send(SRV_ERROR + SRV_END)
            channel.close()
            return

        try:
            header = out.splitlines()[2]
            # The output from the run_query.pl contains the field names
            # in one line and its values in the following lines (one issue
            # per line) separated by ':'.  Split the header line with
            # ':' as delimiter and find the appropriate column index for
            # the field names.  Later use this index to get the field values.
            fixfor_index = header.split(':').index(' fix_for ')
            deliver_to_index = header.split(':').index(' Delivery.deliver_to ')
            deliveryfixfor_index = header.split(':'). \
                                        index(' Delivery.fix_for ')
            delivery_index = header.split(':').index(' Delivery ')
            lines = out.splitlines()[3:]
            dms_list = []
            for line in lines:
                delivery_in_qry = line.split(':')[delivery_index].strip()
                deliveryfixfor_in_qry = line.split(':')[deliveryfixfor_index]. \
                                            strip()
                deliver_to_in_qry = line.split(':')[deliver_to_index].strip()
                fixfor_in_qry = line.split(':')[fixfor_index].strip()
                # Select the DMS issues that match one of the below criteria:
                # 1. The new type of issues should have Delivery records and
                #    `Delivery.deliver_to` should match the `target_branch` and
                #    `Delivery.fix_for` should match the provided `tag`.
                # 2. The old type of issues should NOT have the Delivery
                #    records and the `fix_for` should match the provided `tag`
                if (delivery_in_qry != "" and \
                    deliver_to_in_qry == deliver_to and \
                    deliveryfixfor_in_qry == tag) or \
                    (delivery_in_qry == "" and fixfor_in_qry == tag):
                        dms_list.append(line.split(':')[0].strip())

        except Exception, exp:
            open(SCRIPT_DIR + "\\cqperl_log.txt", "ab").write(str(exp))
            channel.send(SRV_ERROR + SRV_END)
            channel.close()
            return

        dms_list.sort()
        channel.send(','.join(dms_list))
        channel.send(SRV_END)
        channel.close()
    elif req_type == SRV_CHERRY_GET:
        tag = tag + ".csv"
        if not os.path.exists(SCRIPT_DIR + '\\' + tag):
            channel.send('Unavailable' + SRV_END)
            channel.close()
        else:
            cherries = open(SCRIPT_DIR + '\\' + tag, 'r').read()
            channel.send(cherries + SRV_END)
            channel.close()

    elif req_type == SRV_CHERRY_UPDATE:
        tag = tag + ".csv"
        if not os.path.exists(SCRIPT_DIR + '\\' + tag):
            cherries = open(SCRIPT_DIR + '\\' + tag, 'wb')
        else:
            cherries = open(SCRIPT_DIR + '\\' + tag, 'ab')
        cherries.write(issues + '\n')
        channel.send('Updated' + SRV_END)
        channel.close()
    else:
        channel.send('Unknown request' + SRV_END)
        channel.close()


if __name__ == '__main__':
    initialize_path()
