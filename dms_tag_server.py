#!/usr/bin/env python

'''
The purpose of this server is following:
    1. Collect DMSs of a tag from CQ and send back the list
    to requester
    2. Save the list of cherry pick history for each target
    branch
    3. Send back the history of cherry pick to requester
This script is using run_query.pl script to collect data from CQ.
'''

from datetime import datetime
import httplib
import netrc
import optparse
import os
import pythoncom
import servicemanager
import socket
import string
import sys
import thread
import urllib
import win32event
import win32service
import win32serviceutil
from _winreg import *

import dmsutil
from processes import *
import semcutil

HOST = ''
MAX_QUEUE_SIZE = 5
OPTIONS = ['install', 'start', 'stop', 'remove']
PORT = 55655  # Arbitrary non-privileged port
REGPATH = "SYSTEM\\CurrentControlSet\\Services\\DMSTagServer"
USAGE = "Usage: %s -a install -p home-path | -a <start|stop|remove> | -h" % \
        (sys.argv[0])


def invalid_usage(message):
    '''Print the script's usage followed by `message`, and then exit.
    '''
    semcutil.fatal(1, "%s\nError: %s" % (USAGE, message))


def initialize_path():
    '''Parse the arguments (if any) and initialize the working path
    '''
    parser = optparse.OptionParser(usage=USAGE)
    parser.add_option("-p", "--home-path", dest="home", default=None,
        help="Path to the user's home folder (Mandatory for 'install' action)")
    parser.add_option("-a", "--action", dest="action", default="",
        help="Action should be one of 'install', 'start', 'stop' or 'remove'.")
    (opts, args) = parser.parse_args()

    if not opts.action:
        invalid_usage("Insufficient options.")

    if opts.action.lower() not in OPTIONS:
        invalid_usage("Unknown action '%s'." % opts.action)

    working_dir = string.replace(
                                os.path.realpath(
                                os.path.dirname(sys.argv[0])), '\\', '\\\\')

    open(working_dir + "\\server_log.txt", "ab").write("")
    open(working_dir + "\\cqperl_log.txt", "ab").write("")
    argv = []

    if opts.action == "install":
        if opts.home is None:
            invalid_usage("Install action requires the path to .netrc " \
                          "file.\nSpecify the path with -p option.")

        try:
            regkey = CreateKey(HKEY_LOCAL_MACHINE, REGPATH)
            SetValue(regkey, "HomeDir", REG_SZ, opts.home)
            CloseKey(regkey)
        except:
            semcutil.fatal(1, "Unable to access the registry.\n" \
                              "Try installing the service again.")

        # User credentials are required only for installing the service
        (account, password) = parse_netrc(working_dir, opts.home)

        if account == -1:
            semcutil.fatal(1, "Error reading .netrc file.")

        argv = [sys.argv[0], "--username", "corpusers\\" + str(account),
                        "--password", str(password), "--startup", "auto",
                        opts.action]
    else:
        argv = [sys.argv[0], opts.action]

    win32serviceutil.HandleCommandLine(DmsTagServer,
                                       serviceClassString=None,
                                       argv=argv)


def parse_netrc(working_dir, home_dir):
    #read username and password from netrc file
    #.netrc file should have the following line
    #machine dms_tag_server account JPTO login <loginid> password <password>
    try:
        host = netrc.netrc(home_dir + '\\.netrc').hosts['dms_tag_server']
        return (str(host[0]), str(host[2]))
    except KeyError:
        open(working_dir + "\\server_log.txt", "ab").write(
            'dms_tag_server info is not in .netrc file\n')
    except netrc.NetrcParseError:
        open(working_dir + "\\server_log.txt", "ab").write(
            'Error parsing .netrc file\n')
    except IOError:
        host = ['-1']
        open(working_dir + "\\server_log.txt", "ab").write(
            'Error opening .netrc file\n ' + host[0] + "'" + home_dir + "'")
    except:
        open(working_dir + "\\server_log.txt", "ab").write(
            'Unexpected error %s\n' % sys.exc_info()[0])
    return (-1, -1)


class DmsTagServer (win32serviceutil.ServiceFramework):
    _svc_name_ = "DMSTagServer"
    _svc_display_name_ = "DMS Tag Server"
    _svc_description_ = "DMS Query Server for Cherry Picking"

    def __init__(self, args):
        try:
            self.arg = args
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            socket.setdefaulttimeout(60)
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
        try:
            regkey = OpenKey(HKEY_LOCAL_MACHINE, REGPATH)
            cwd = string.replace(QueryValue(regkey, "PythonClass"),
                                '\\', '\\\\')
            home_dir = string.replace(QueryValue(regkey, "HomeDir"),
                                '\\', '\\\\')
            CloseKey(regkey)
        except:
            servicemanager.LogMsg(servicemanager.EVENTLOG_ERROR_TYPE,
                              servicemanager.PYS_SERVICE_STOPPING,
                              (self._svc_name_,
                               'Unable to access the registry.\n' \
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
        self.run_server(cwd, home_dir)

    def run_server(self, working_dir, home_dir):
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

        (account, password) = parse_netrc(working_dir, home_dir)
        if account == -1:
            servicemanager.LogMsg(servicemanager.EVENTLOG_ERROR_TYPE,
                              servicemanager.PYS_SERVICE_STOPPING,
                              (self._svc_name_,
                                'Error reading .netrc file at %s.\n' \
                                + 'See the log for more details \n' % home_dir))
            self.SvcStop()
            sys.exit(1)

        open(working_dir + "\\server_log.txt", "ab").write("Server started\n")

        while self.keep_running:
            s.listen(MAX_QUEUE_SIZE)
            try:
                conn, addr = s.accept()
                thread.start_new_thread(process_req, (working_dir, conn, addr,
                                                        account, password))
            except socket.timeout:
                continue


def process_req(working_dir, channel, address, user, password):
    '''Listen request of client and send data back to client'''
    request = ''
    data = channel.recv(dmsutil.BUFFER_LEN)
    while 1:
        request = request + data
        if dmsutil.SRV_END in str(data):
            break
        data = channel.recv(dmsutil.BUFFER_LEN)

    data_list = request.split('|')

    error_msg = ""
    send_data = ""
    req_type = data_list[0]

    if req_type == dmsutil.SRV_DMS_INFO:
        # Error handling for insufficient data in the stream
        if len(data_list) < 2:
            error_msg = "Insufficient data from %s. Data received was: %s\n" % \
                         (address, request)
            send_data = '%s: %s %s' % (dmsutil.SRV_ERROR, error_msg,
                                       dmsutil.SRV_END)
        else:
            issues = data_list[1]
            open(working_dir + "\\server_log.txt", "ab").write(
                    'Connected by %s at %s for %s \nIssues: %s\n' % (address,
                    datetime.now().strftime("%Y-%m-%d-%H:%M:%S"), req_type,
                    issues))
            cmd = ['cqperl', working_dir + '\\run_query.pl', '-remove_query',
                   '-user', user, '-pwd', password, '-issues', issues,
                   '-log', 'cherry.log', '-list', '-title', '-site', 'JPTO']
            try:
                ret, out, err = run_cmd(cmd)
            except ChildExecutionError, exp:
                # Can't pass the exception as such as it will expose the
                # password from the command, hence handle the exceptions
                # differently.
                if isinstance(exp, ChildRuntimeError):
                    err_msg = 'run_query.pl failed with status: %d\nError: %s' \
                              % (exp.result[0],  exp.result[2])
                else:
                    err_msg = str(exp)
                open(working_dir + "\\cqperl_log.txt", "ab").write(
                     "%s: %s\n" % (datetime.now().strftime("%Y-%m-%d-%H:%M:%S"),
                                   str(exp)))
                channel.send('%s: %s %s' % (dmsutil.SRV_ERROR, err_msg,
                                            dmsutil.SRV_END))
                channel.close()
                return

            try:
                header = out.splitlines()[2]
                # The output from the run_query.pl contains the field names
                # in one line and its values in the following lines (one issue
                # per line) separated by ':'.  Split the header line with
                # ':' as delimiter and find the column index for title field.
                # Later use this index to get the field values.
                columns = header.split(':')
                lines = out.splitlines()[3:]
                title_index = columns.index(' title ')
                dms_list = []
                for line in lines:
                    fields = line.split(':', 1)
                    issue = fields[0].strip()
                    title = fields[title_index].strip().rstrip(':')
                    dms = "%s|%s" % (issue, title)
                    if dms not in dms_list:
                        dms_list.append(dms)
                dms_list.sort()
                send_data = dmsutil.SRV_DELIMITER.join(dms_list)
            except Exception, exp:
                open(working_dir + "\\cqperl_log.txt", "ab").write(str(exp))
                channel.send('%s: %s %s' % (dmsutil.SRV_ERROR, str(exp),
                                            dmsutil.SRV_END))
                channel.close()
                return

            open(working_dir + "\\server_log.txt", "ab").write(
                 'Sending result to %s\nData: %s\n' % (address, send_data))
            totalsent = 0
            while totalsent != len(send_data):
                totalsent += channel.send(send_data[totalsent:totalsent +
                                                    dmsutil.BUFFER_LEN])
            channel.send(dmsutil.SRV_END)
            channel.close()
    elif req_type == dmsutil.SRV_DMS_STATUS:
        # Error handling for insufficient data in the stream
        if len(data_list) < 3:
            error_msg = "Insufficient data from %s. Data received was: %s\n" % \
                         (address, request)
            send_data = '%s: %s %s' % (dmsutil.SRV_ERROR, error_msg,
                                       dmsutil.SRV_END)
        else:
            tag_list = []
            for tag in data_list[1].rstrip(',').split(','):
                if tag.strip():
                    tag_list.append(tag.strip())
            issues = data_list[2]

            # Make it compatible with old cherry-pick script
            deliver_to = ''
            if len(data_list) > 3:
                deliver_to = data_list[3]

            open(working_dir + "\\server_log.txt", "ab").write(
                'Connected by %s at %s for %s \nData:\nTag: %s\nBranch: ' \
                '%s\nIssues: %s\n' % (address,
                datetime.now().strftime("%Y-%m-%d-%H:%M:%S"), req_type,
                tag_list, deliver_to, issues))
            send_data = issues
            # If the tag list is empty no need to check the issues.  Just send
            # back the issues.
            if tag_list:
                cmd = ['cqperl', working_dir + '\\run_query.pl',
                       '-remove_query', '-user', user, '-pwd', password,
                       '-issues', issues, '-log', 'cherry.log', '-list',
                       '-site', 'JPTO']
                try:
                    ret, out, err = run_cmd(cmd)
                except ChildExecutionError, exp:
                    # Can't pass the exception as such as it will expose the
                    # password from the command, hence handle the exceptions
                    # differently.
                    if isinstance(exp, ChildRuntimeError):
                        err_msg = \
                            'run_query.pl failed with status: %d\nError: %s' % \
                            (exp.result[0],  exp.result[2])
                    else:
                        err_msg = str(exp)
                    open(working_dir + "\\cqperl_log.txt", "ab").write(
                         "%s: %s\n" % (datetime.now().strftime(
                                       "%Y-%m-%d-%H:%M:%S"), str(exp)))
                    channel.send('%s: %s %s' % (dmsutil.SRV_ERROR, err_msg,
                                                dmsutil.SRV_END))
                    channel.close()
                    return

                try:
                    header = out.splitlines()[2]
                    # The output from the run_query.pl contains the field names
                    # in one line and its values in the following lines (one
                    # issue per line) separated by ':'.  Split the header line
                    # with ':' as delimiter and find the appropriate column
                    # index for the field names.  Later use this index to get
                    # the field values.
                    columns = header.split(':')
                    deliver_to_index = columns.index(' Delivery.deliver_to ')
                    deliverytag_index = columns.index(' Delivery.fix_for ')
                    decision_index = columns.index(' Delivery.decisionStatus ')
                    delivery_index = columns.index(' Delivery ')
                    lines = out.splitlines()[3:]
                    dms_list = []
                    for line in lines:
                        fields = line.split(':')
                        delivery_in_qry = fields[delivery_index].strip()
                        deliverytag_in_qry = fields[deliverytag_index].strip()
                        decision_in_qry = fields[decision_index].strip()
                        deliver_to_in_qry = fields[deliver_to_index].strip()
                        # Select the DMS issues that match the below
                        # criteria:
                        #  The new type of issues should have Delivery records
                        #  and `Delivery.deliver_to` should match the
                        #  `target_branch` and `Delivery.fix_for` should match
                        #  one of the provided `tag_list`.
                        if (delivery_in_qry != "" and
                                deliver_to_in_qry == deliver_to and
                                string.lower(decision_in_qry) == "accepted" and
                                deliverytag_in_qry in tag_list):
                            dms_list.append(line.split(':')[0].strip())
                    dms_list.sort()
                    send_data = ','.join(dms_list)
                except Exception, exp:
                    open(working_dir + "\\cqperl_log.txt", "ab"). \
                         write("%s: %s\n" % (
                               datetime.now().strftime("%Y-%m-%d-%H:%M:%S"),
                               str(exp)))
                    channel.send('%s: %s %s' % (dmsutil.SRV_ERROR, str(exp),
                                                dmsutil.SRV_END))
                    channel.close()
                    return

            open(working_dir + "\\server_log.txt", "ab").write(
                'Sending result to %s\nData: %s\n' % (address, send_data))
            totalsent = 0
            while totalsent != len(send_data):
                totalsent += channel.send(send_data[totalsent:totalsent +
                                                    dmsutil.BUFFER_LEN])
            channel.send(dmsutil.SRV_END)
            channel.close()
    else:
        error_msg = 'Unknown request received from %s. ' + \
                    'Data received was: %s\n' % (address, request)
        send_data = 'Unknown request' + dmsutil.SRV_END

    if error_msg:
        open(working_dir + "\\cqperl_log.txt", "ab").write(error_msg)
        channel.send(send_data)
        channel.close()


if __name__ == '__main__':
    initialize_path()
