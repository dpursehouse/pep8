#!/usr/bin/env python

'''
@author: Ekramul Huq

'''

DESCRIPTION = \
'''
Find cherry pick candidates in source branch(es) by processing the git log of
each base branch and target branch. From the log, list of DMSs will be checked
with DMS tag server and commits with correct DMS tag (--dms-tags) will be
considered. Exclusion filters which are mentioned in --exlude-git,--exclude-dms
and --exclude-commit will be excluded. Then the potential commits will be pushed
to Gerrit for review. As a byproduct a .csv file will be created with the commit
list and a _result.csv file with the result of each cherry pick execution.

Possible to use configuration file(--config) to set the argument values.
Config file has higher priority on default command line parameter values
(e.g. cwd) and command line parameter has higher priority than config file
values for others.

During each cherry pick, commit id will be checked in Gerrit commit message,
and cherry pick of this commit will be skipped if corresponding commit is found
in open or abandoned state.

Email will be sent to corresponding persons for each cherry-pick failure with
reason and Gerrit URL. And in dry-run mode, email will be sent only to executor.

It is possible to simulate the whole process by using the --dry-run option and
possible to create only the cherry pick list and skip the push to Gerrit
action with the -n(--no-push-to-gerrit) option.

SEMC username and password are required in .netrc file for DMS tag check through
web. It is not necessary if dms tag server is used(--dms-tag-server) and web
interface is not used.

repo envirionment must be initialized in working directory before you run this
script.

Example:
 To find out the potential commits for cherry pick from base ginger-dev to
 target edream3.0-release-caf with DMS tag 3.0 CAF:
 Initialize repo first
 $repo init -u git://review.sonyericsson.net/platform/manifest.git -b ginger-dev

 1. To find out the potential commits and push to Gerrit for review
    $%prog -b ginger-dev -t edream3.0-release-caf -d "3.0 CAF"
 2. To simulate the whole execution without actual push to Gerrit
    add --dry-run option
    $%prog -b ginger-dev -t edream3.0-release-caf -d "3.0 CAF" --dry-run
 3. To create only the csv file with potential cherry pick commit list
    add --no-push-to-gerrit option
    $%prog -b ginger-dev -t edream3.0-release-caf -d "3.0 CAF" --no-push-to-gerrit
 4. To push the commits from already created csv file
    $%prog -t edream3.0-release-caf -f <csv_file_name>.csv
 5. To add default reviewers with each cherry pick commit add
    -r <reviewers email addresses> option
    $%prog -b ginger-dev -t edream3.0-release-caf -d "3.0 CAF"
    -r "xx@sonyericsson.com,yy@sonyericsson.com"
 6. To use configuration file use --config <file_name> option
     Suppose you have configuration file config.cfg and content is following:

         [edream3.0-release-caf]
         dry_run = True
         base_branches = esea-ginger-dev,master,esea-ginger-dev-2.6.32
         dms_tags = 3.0 CAF,Fix ASAP

    And want to set verbose flag from command line
    $%prog --config config.cfg -t edream3.0-release-caf -v

'''

import pycurl
import sys
import subprocess
import optparse
import os
import re
import json
import xml.dom.minidom
import time
import socket
import errno
import signal
import threading
import tempfile

DMS_URL = "http://seldclq140.corpusers.net/DMSFreeFormSearch/\
WebPages/Search.aspx"

__version__ = '0.2.9'

REPO = 'repo'
GIT = 'git'
OPT_PARSER = None
OPT = None
dst_manifest = None

#Error codes
STATUS_OK = 0
STATUS_CHERRYPICK_FAILED = 1
STATUS_REPO = 2
STATUS_DMS_SRV = 3
STATUS_MANIFEST = 4
STATUS_ARGS = 5
STATUS_FILE = 6
STATUS_GIT_USR = 7
STATUS_GERRIT_ERR = 8
STATUS_RM_PROJECTLIST = 9
STATUS_USER_ABORTED = 10

#Server communication tags
SRV_DMS_STATUS = 'DMS_STATUS'
SRV_CHERRY_UPDATE = 'CHERRY_UPDATE'
SRV_CHERRY_GET = 'CHERRY_GET'
SRV_ERROR = 'SRV_ERROR'
SRV_END = '|END'

#Commit SHA1 string length
SHA1_STR_LEN = 40

class Httpdump:
    """Http dump class"""
    def __init__(self, url):
        self.url = url
        self.contents = ''

    def body_callback(self, buf):
        """
        Call back function to read data
        """
        self.contents = self.contents + buf

    def perform(self):
        """
        Perform data collection
        """
        my_curl = pycurl.Curl()
        my_curl.setopt(pycurl.URL, self.url)
        my_curl.setopt(pycurl.NETRC, 1)
        my_curl.setopt(pycurl.HTTPAUTH, pycurl.HTTPAUTH_NTLM)
        my_curl.setopt(pycurl.WRITEFUNCTION, self.body_callback)
        my_curl.setopt(pycurl.VERBOSE, False)
        my_curl.perform()
        my_curl.close()

class HelpFormatter(optparse.IndentedHelpFormatter):
    """
    Help formatter to override default formatter
    """
    def format_description(self, description):
        """
        Clean the text format and just print the description
        """
        if description:
            print "Description:", description
        return ''

class Gerrit():
    '''
    Gerrit interface class to collect data from Gerrit
    '''
    def __init__(self,
                 address='review.sonyericsson.net',
                 port='29418',
                 gerrit_user=None):
        '''
        Constructor
        '''
        self.address = address
        self.port = port
        self.gerrit_user = gerrit_user
        self.data_format = 'JSON'

    def collect_email_addresses(self, commit):
        '''
        Collect email addresses from Gerrit of a review
        '''
        r_cmd = ['ssh', '-p', self.port, self.address,
                 '-l', self.gerrit_user,
                 'gerrit',
                 'query',
                 '--format='+self.data_format,
                 'status:merged', 'limit:1',
                 '--current-patch-set',
                 'commit:' + commit
                 ]
        out, err, ret = execmd(r_cmd)
        if ret != 0:
            print_err("%s %s" %(out, err))
            cherry_pick_exit(STATUS_GERRIT_ERR)
        #collect email addresses from Gerrit
        gerrit_patchsets = json.JSONDecoder().raw_decode(out)[0]
        emails, url = None, None
        if gerrit_patchsets:
            approvals_email = filter(lambda a: "email" in a["by"],
                                     gerrit_patchsets["currentPatchSet"]
                                     ["approvals"])
            emails = list(set([a["by"]["email"] for a in approvals_email]))
            url = gerrit_patchsets['url'].strip()
        return emails, url

    def is_commit_available(self, commit, target_branch, prj_name):
        '''
        Return (url,date,status) tuple if commit is available in target_branch
        in open or abandoned state, otherwise return (None,None,None) tuple
        '''
        r_cmd = ['ssh', '-p', self.port, self.address,
                 '-l', self.gerrit_user,
                 'gerrit',
                 'query',
                 '--format='+self.data_format,
                 'project:'+prj_name, 'status:open',
                 'branch:' + target_branch,
                 'message:cherry.picked.from.commit.' + commit,
                 'OR',
                 'project:'+prj_name, 'status:abandoned',
                 'branch:' + target_branch,
                 'message:cherry.picked.from.commit.' + commit,
                 '--current-patch-set'
                  ]
        out, err, ret = execmd(r_cmd)
        if ret != 0:
            print_err("%s %s" %(out, err))
            cherry_pick_exit(STATUS_GERRIT_ERR)
        gerrit_patchsets = json.JSONDecoder().raw_decode(out)[0]
        if gerrit_patchsets:
            if gerrit_patchsets.has_key('url'):
                return (gerrit_patchsets['url'],
                        gerrit_patchsets['lastUpdated'],
                        gerrit_patchsets['status'])
            else:
                return None, None, None

    def approve(self, url):
        """Approve the change-set with +2"""
        #first collect revision
        r_cmd = ['ssh', '-p', self.port, self.address,
             '-l', self.gerrit_user,
             'gerrit',
             'query',
             '--format='+self.data_format,
             'status:open', 'limit:1',
             '--current-patch-set',
             'change:' + url.split('/')[-1]
             ]
        out, err, ret = execmd(r_cmd)
        if ret != 0:
            print_err("%s %s" %(out, err))
            cherry_pick_exit(STATUS_GERRIT_ERR)
        gerrit_patchsets = json.JSONDecoder().raw_decode(out)[0]
        if gerrit_patchsets:
            revision = gerrit_patchsets["currentPatchSet"]["revision"]
            #approve with +2
            r_cmd = ['ssh', '-p', self.port, self.address,
                     '-l', self.gerrit_user,
                     'gerrit',
                     'approve',
                     '--code-review=+2',
                     revision]
            out, err, ret = execmd(r_cmd)
            if ret != 0:
                print_err("%s %s" %(out, err))
            else:
                do_log("Code review for %s set to +2"%url)

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

    def dms_for_tags(self, dmss, dms_tags):
        """
        Connect to tag server and collect dmss for a tag
        """
        dms_list = {}
        for tag in dms_tags.split(','):
            tagged_dms = self.query_srv('%s|%s|%s' %(SRV_DMS_STATUS, tag, dmss))
            if tagged_dms == None:
                return None
            dms_list[tag] = tagged_dms
            do_log("DMS found for tag %s: %s" %(tag, dms_list[tag]),
                   echo=True)
        return dms_list

    def query_srv(self, query):
        """Send the query to server and collect the data"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30) #disconnect after 30 sec
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
                print_err('DMS tag server side error')
                return None
            return msg.split('|')[0]
        except socket.timeout, err:
            print_err('dms tag server error: %s'%err[0])
            return None
        except socket.error, err:
            print_err('dms tag server error: %s'%err[1])
            return None

    def retrieve(self, branch):
        '''Collect data from server of branch'''
        return self.query_srv('%s|%s' %(SRV_CHERRY_GET, branch))

    def update(self, branch, records):
        '''Save data into server for branch'''
        return self.query_srv('%s|%s|%s' %(SRV_CHERRY_UPDATE, branch,
                                           '\n'.join(records)))

class Commit:
    """Data structure for a single commit"""
    def __init__(self, target=None, path=None, name=None,
                 author_date=None, commit=None, dms=None, title=None):
        self.target = target
        self.path = path
        self.name = name
        self.author_date = author_date
        self.commit = commit
        self.dms = dms
        self.title = title
    def cmp(self, commit):
        """compare itself with another commit"""
        if (((self.target, self.name, self.dms) ==
            (commit.target, commit.name, commit.dms)) and
            (self.author_date == commit.author_date or
             self.title == commit.title)) :
            #check author date and title if either one match, to detect
            #manual cherry pick which has different author date in base
            #and target
            return True
        return False
    def __str__(self):
        return "%s,%s,%s,%s,%s" % (self.target, self.path,
                   self.name, self.commit, self.dms)


class ManifestData():
    """Functionality for handling manifest XML data"""
    def __init__(self, xml_input_data):
        """Raises xml.parsers.expat.ExpatError
           if fails to parse data as valid XML"""
        self.dom = xml.dom.minidom.parseString(xml_input_data)

    def update_revision(self, project_name, new_revision):
        for element in self.get_projects():
            if (element.attributes['name'].nodeValue.encode('utf-8') ==
                    project_name):
                element.setAttribute('revision', new_revision)
                return True
        return False

    def write_xmldata_to_file(self, file_path):
        """Raises IOError if fails to write data to file"""
        path = os.path.dirname(file_path)
        fd, tmppath = tempfile.mkstemp(dir=path)
        self.dom.writexml(os.fdopen(fd, "w"), encoding="UTF-8")
        os.rename(tmppath, file_path)

    def get_def_rev(self):
        """Raises KeyError if fails to find tag name and/or revision"""
        return self.dom.getElementsByTagName("default")[0]. \
                    getAttribute('revision').encode('utf-8')

    def get_projects(self):
        """Raises KeyError if fails to find tag name"""
        return self.dom.getElementsByTagName("project")

def get_manifest_str(commit_ref):
    """Reads the manifest file and returns the content as a string"""
    current_path = os.getcwd()
    os.chdir(os.path.join(OPT.cwd, '.repo/manifests'))
    try:
        manifest_str, err, ret = execmd([GIT, 'show', commit_ref + ':default.xml'])
    finally:
        os.chdir(current_path)
    if ret != 0:
        print_err("Can't read the manifest file for %s:\n%s" %
                  (commit_ref, err))
        cherry_pick_exit(STATUS_MANIFEST)
    return manifest_str

def str_list(commit_list):
    """Helper function to convert a list of Commit to list of strings"""
    commit_list = [str(cmt) for cmt in commit_list]
    commit_list.sort()
    return commit_list

def option_parser():
    """
    Option parser
    """
    usage = ("%prog -t TARGET_BRANCH [--config CONF_FILE |-d DMS_TAGS" +
             ",... [options]]")
    opt_parser = optparse.OptionParser(formatter=HelpFormatter(),
                                       usage=usage, description=DESCRIPTION,
                                       version='%prog ' + __version__)
    opt_parser.add_option('-c', '--config',
                     dest='config_file',
                     help='Configuration file name.',
                     action="store", default=None, metavar="FILE")
    opt_parser.add_option('-b', '--base-branches',
                     dest='base_branches',
                     help='base branches (comma separated), default is all.',
                     action="store", default=None)
    opt_parser.add_option('-t', '--target-branch',
                     dest='target_branch',
                     help='target branch')
    opt_parser.add_option('--target-branch-patterns',
                     dest='target_branch_patterns',
                     help='List of branch patterns accepted in the target ' \
                          'manifest for cherry picking to (comma separated)',
                     default='(?!refs/tags)',)
    opt_parser.add_option('-d', '--dms-tags',
                     dest='dms_tags',
                     help='DMS tags (comma separated)',
                     action="store", default=None)
    opt_parser.add_option('-r', '--reviewers',
                     dest='reviewers',
                     help='default reviewers (comma separated)',
                     action="store", default=None)
    opt_parser.add_option('-w', '--work-dir',
                     dest='cwd',
                     help='working directory, default is current directory',
                     action="store", default=os.getcwd())
    opt_parser.add_option('--dms-tag-server',
                     dest='dms_tag_server',
                     help='IP address or name of DMS tag server',
                     action="store", default=None)
    opt_parser.add_option('--approve',
                     dest='approve',
                     help='Approve uploaded change set in Gerrit with +2',
                     action="store_true", default=False)
    opt_parser.add_option('--mail-sender',
                     dest='mail_sender',
                     help='Mail sender address for mail notification.',
                     action="store", default=None)
    opt_parser.add_option('--exclude-git',
                     dest='exclude_git',
                     help='List of gits to be excluded (comma separated)',
                     default=None,)
    opt_parser.add_option('--exclude-commit',
                     dest='exclude_commit',
                     help='List of commits to be excluded (comma separated)',
                     default=None,)
    opt_parser.add_option('--exclude-dms',
                     dest='exclude_dms',
                     help='List of DMSs to be excluded (comma separated)',
                     default=None,)
    opt_parser.add_option('--include-git',
                     dest='include_git',
                     help='List of gits to be included (comma separated)'+
                     '--exclude-git will be ignored.',
                     default=None,)
    #debug options
    opt_group = opt_parser.add_option_group('Debug options')
    opt_group.add_option('-v', '--verbose',
                     dest="verbose", action="store_true", default=False,
                     help="Verbose")
    opt_group.add_option('--no-rm-projectlist',
                     dest='no_rm_projectlist',
                     help='Do not remove .repo/project.list', action="store_true",
                     default=False)
    opt_group.add_option('--no-repo-sync',
                     dest='no_repo_sync',
                     help='Do not repo sync', action="store_true",
                     default=False)
    opt_group.add_option('-n', '--no-push-to-gerrit',
                     dest='no_push_to_gerrit',
                     help='Do not cherry pick and push to Gerrit',
                     action="store_true", default=False)
    opt_group.add_option('-f', '--csv-file',
                     dest='csv_file',
                     help='load the cherry pick list from csv file and push ' +
                     'to gerrit',
                     metavar="FILE")
    opt_group.add_option('--dry-run',
                     dest='dry_run',
                     help='Do not push to Gerrit',
                     action="store_true", default=False)
    opt_group.add_option('--gerrit-user',
                     dest='gerrit_user',
                     help='Use this Gerrit user to push, useful for hudson job',
                     default=None)
    return opt_parser

def cherry_pick_exit(exit_code):
    """
    Exit this script with exit code and message
    """
    reason = {
              STATUS_OK: "Cherry pick completed",
              STATUS_CHERRYPICK_FAILED : "Some or all cherry picks failed",
              STATUS_REPO: "Repo error",
              STATUS_DMS_SRV: "DMS tag server is not reachable",
              STATUS_MANIFEST: "Manifest file error",
              STATUS_ARGS: "Using wrong arguments",
              STATUS_FILE: "File error",
              STATUS_GIT_USR: "Git config error",
              STATUS_GERRIT_ERR: "Gerrit server is not reachable",
              STATUS_RM_PROJECTLIST: "Failed to remove .repo/project.list",
              STATUS_USER_ABORTED: "Aborted by user"
              }
    msg = reason.get(exit_code)
    if exit_code != STATUS_OK:
        print_err(msg)
    else:
        do_log(msg, echo=True)
    exit(exit_code)

def parse_base_and_target_manifest(target_branch):
    """Parses base and target manifest files"""
    #parse base manifest
    try:
        base_manifest = ManifestData(get_manifest_str('HEAD'))
        base_proj_rev = {}
        for node in base_manifest.get_projects():
            rev = node.getAttribute('revision')
            path = node.getAttribute('path')
            name = node.getAttribute('name')
            rev = base_manifest.get_def_rev() if rev == '' else rev
            if OPT.base_branches: #if any base branches mentioned, consider these
                for base_branch in  OPT.base_branches.split(','):
                    if rev == base_branch:
                        base_proj_rev[name] = base_branch + ',' + path
                        break
            else:               #otherwise consider all
                base_proj_rev[name] = rev + ',' + path
    except (KeyError, xml.parsers.expat.ExpatError), err:
        print_err("Failed to parse base manifest: %s" % err)
        cherry_pick_exit(STATUS_MANIFEST)
    #parse target manifest
    try:
        global dst_manifest
        dst_manifest = ManifestData(get_manifest_str('origin/' +
                                                     target_branch))
        dst_proj_rev = {}
        for node in dst_manifest.get_projects():
            rev = node.getAttribute('revision')
            rev = dst_manifest.get_def_rev() if rev == '' else rev
            dst_proj_rev[node.getAttribute('path')] = rev
    except (KeyError, xml.parsers.expat.ExpatError), err:
        print_err("Failed to parse target manifest: %s" % err)
        cherry_pick_exit(STATUS_MANIFEST)
    return base_proj_rev, dst_proj_rev

def repo_sync():
    """
    Repo sync
    """
    os.chdir(OPT.cwd)
    if not OPT.no_rm_projectlist:
        do_log("Removing .repo/project.list...", echo=True)
        try:
            os.remove('.repo/project.list')
        except os.error, err:
            if err.errno != errno.ENOENT:
                print_err("Error removing .repo/project.list: %s" % err)
                cherry_pick_exit(STATUS_RM_PROJECTLIST)
    do_log("Repo sync...", echo=True)
    result, err, ret = execmd([REPO, 'sync', '-j5'], 3600)
    do_log(result, file_name='repo_sync.log')
    if ret != 0:
        print_err("Repo sync error %s" %err)
        cherry_pick_exit(STATUS_REPO)

def is_str_git_sha1(input_string):
    """
    Checks if the input string is a valid commit SHA1.
    A character string is considered to be a commit SHA1 if it has exactly
    the expected length and is a base 16 represented integer.
    """
    if (len(input_string) != SHA1_STR_LEN):
        return False
    else:
        try:
            #convert from base 16 to base 10 to ensure it's a valid base 16
            #integer
            sha10 = int(input_string, 16)
        except:
            return False
    return True

def loop_match(patterns, string):
    """
    Checks if the input string matches one of the provided patterns.
    """
    for pattern in patterns:
        if (re.match(pattern, string) != None):
            return True
    return False

def get_dms_list(target_branch):
    """
    Collect the DMSs from all projects, from MERGE_BASE to  BASE_BRANCH and
    from MERGE_BASE to  TARGET_BRANCH. Return the DMSs list which are not in
    TARGET_BRANCH.
    """
    #Parse base and target manifest file
    base_proj_rev, dst_proj_rev = parse_base_and_target_manifest(target_branch)

    os.chdir(OPT.cwd)
    merge_base_log = open('merge-base.log', 'wb')
    base_log = open('source_commit.log', 'wb')
    target_log = open(target_branch + '_commit.log', 'wb')
    base_commit_list, target_commit_list = [], []

    for name, rev_path in base_proj_rev.iteritems():
        target_revision = None
        target_is_sha1 = False
        path = rev_path.split(',')[1]
        base_rev = rev_path.split(',')[0]
        if OPT.include_git:
            if name not in OPT.include_git.split(','):
                continue #include gits
        elif OPT.exclude_git and name in OPT.exclude_git.split(','):
            continue    #exclude gits

        os.chdir(os.path.join(OPT.cwd, path))
        #check base rev is sha1 or branch
        ret = execmd([GIT, 'show-ref', '-q', '--verify',
                      'refs/remotes/origin/' + base_rev])[2]
        if ret != 0:
            continue #it is sha1 or tag, so ignore
        #check target branch for this git is available
        if not dst_proj_rev.has_key(path):
            print_err("Branch not found in destination for git %s" % name)
            continue
        t_revision = dst_proj_rev[path]
        if t_revision == base_rev:
            #no need to proceed if both have same revision
            continue

        if (is_str_git_sha1(t_revision)):
            target_revision = t_revision #it's a sha1
            target_is_sha1 = True
        elif (loop_match(OPT.target_branch_patterns.split(','), t_revision)):
            target_revision = 'origin/' + t_revision
        else:
            continue

        os.chdir(os.path.join(OPT.cwd, path))
        mergebase, err, ret = execmd([GIT, 'merge-base', 'origin/' +
                                      base_rev, target_revision])
        if not mergebase:
            merge_base_log.write('No merge-base for %s and %s\n' %
                                 (base_rev, target_branch))
            print_err(err)
            continue
        merge_base_log.write(mergebase + '\n')
        if target_is_sha1: # add traget rev and path to commit
            rev_path = target_branch + ',' + path
        else:
            rev_path = t_revision + ',' + path
        #read merge base to base branch log
        b_commit_list = collect_fix_dms('origin/' + base_rev, mergebase,
                                   rev_path + ',' + name, base_log)
        #read merge base to target branch log
        t_commit_list = collect_fix_dms(target_revision, mergebase,
                                   rev_path + ',' + name, target_log)
        #handle new branch creation if target git rev is sha1
        if target_is_sha1 and b_commit_list:
            if not create_branch(target_branch, b_commit_list,
                                 t_commit_list, name, target_revision):
                os.chdir(OPT.cwd)
                continue # nothing is to cherry pick in this git, so go next
        if b_commit_list:
            base_commit_list += b_commit_list
        if t_commit_list:
            target_commit_list += t_commit_list
        os.chdir(OPT.cwd)

    do_log('\n'.join(str_list(base_commit_list)), file_name='base_dms_list.log')
    do_log('\n'.join(str_list(target_commit_list)), file_name=
            target_branch + '_dms_list.log')
    #remove the common commits both in base and target
    final_commit_list = []
    final_commit_list += base_commit_list
    for cmt in base_commit_list:
        for t_cmt in target_commit_list:
            if cmt.cmp(t_cmt):
                final_commit_list.remove(cmt)
                break
    do_log('\n'.join(str_list(final_commit_list)),
            file_name=target_branch + '_diff_dms_list.log',
            info='Diff list')
    return final_commit_list

def create_branch(target_branch, b_commit_list, t_commit_list, git_name, sha1):
    """
    Create branch from sha1 if somethig to cherry pick
    """
    delta_list = []
    delta_list += b_commit_list
    for cmt in b_commit_list:
        for t_cmt in t_commit_list:
            if cmt.cmp(t_cmt):
                delta_list.remove(cmt)
                break
    if not delta_list:
        return False
    delta_list = dms_get_fix_for(delta_list)
    if delta_list:
        #We have some change to cherry pick, so need to create branch
        gituser = get_git_user()
        gerrit = Gerrit(gerrit_user=gituser)
        #take a commit
        cmt = delta_list[0]
        if OPT.dry_run:
            recipient = [gituser + '@sonyericsson.com']
        else:
            recipient = gerrit.collect_email_addresses(cmt.commit)[0]
        ret = execmd([GIT, 'show-ref', '-q', '--verify',
                      'refs/remotes/origin/' + target_branch])[2]
        if ret == 0:
            do_log("Branch %s already available for %s. Please update manifest."
                   % (target_branch, git_name), echo=True)
            #mail to inform manifest updated is needed
            update_manifest_mail(cmt.target, cmt.name, recipient)
            return True
        cmd = [GIT, 'push','ssh://%s@review.sonyericsson.net:29418/%s.git' %
               (gituser,git_name),'%s:refs/heads/%s'%(sha1, target_branch)]
        log, err, ret = execmd(cmd)
        if ret == 0:
            do_log("Branch %s created for %s." % (target_branch, git_name),
                   echo=True)
            do_log(log)
            do_log(err)
            execmd([GIT, 'fetch'])
            #mail to inform manifest updated is needed
            create_branch_mail(cmt.target, cmt.name, recipient)
            return True
        else:
            do_log("Failed to create %s branch for %s." %
                   (target_branch, git_name), echo=True)
            do_log(log)
            do_log(err)
            return False
    else:
        return False

def collect_fix_dms(branch, commit_begin, project, log_file):
    """
    Collect FIX=DMSxxxxxxx and commit id from the logs.
    return the list of commits.
    """
    commit_list = []
    git_log = execmd([GIT, 'log', '--pretty=fuller',
                      commit_begin + '..' + branch])[0]
    log_file.write(git_log + '\n')
    git_log_list = git_log.split('\n')
    commit_id, author_date, title = '', '', ''
    for log_str in git_log_list:
        if re.match(r'^commit\s.*?', log_str):
            commit_id = log_str.split(' ')[1] #sha1
        elif re.match(r'AuthorDate: ', log_str):
            author_date = log_str
        elif re.match(r'CommitDate:', log_str): #get the title 2 lines bellow it
            title = git_log_list[git_log_list.index(log_str) + 2].strip()
        elif re.match(r'^\s*?FIX\s*=\s*DMS[0-9]+', log_str):   #"FIX=DMSxxxxx"
            dms_str = log_str.split('=')
            dms_id = dms_str[1].strip()     #DMSxxxxxxx
            if (OPT.exclude_commit and
                commit_id in OPT.exclude_commit.split(',')):
                continue                    #exclude commit
            if OPT.exclude_dms and dms_id in OPT.exclude_dms.split(','):
                continue                    #exclude dms
            rev, path, name = project.split(',')
            cmt = Commit(target=rev, path=path, name=name, dms=dms_id,
                         commit=commit_id, author_date=author_date,
                         title=title)
            commit_list.append(cmt)

    return commit_list

def dms_get_fix_for(commit_list):
    """
    Collect DMS status from DMS server. Collect only the commits match with
    OPT.tag_list
    """
    commit_tag_list = []
    progress = 0
    total = len(commit_list)

    if OPT.dms_tag_server:
        server = DMSTagServer(OPT.dms_tag_server)
        tags_dmss = server.dms_for_tags(','.join([x.dms for x in commit_list]),
                                        OPT.dms_tags)
        if tags_dmss != None:
            for cmt in commit_list:
                dms = cmt.dms
                for tag in OPT.dms_tags.split(','):
                    if dms in tags_dmss[tag]:
                        commit_tag_list.append(cmt)
                        break
            return commit_tag_list

    do_log('DMS tag server is not available, trying web interface..', echo=True)
    for cmt in commit_list:
        dms = cmt.dms
        dump = Httpdump(DMS_URL + "?q=0___" + str(dms) + "___issue")
        progress += 1
        dump.perform()
        contents = dump.contents
        if "TITLE>You are not authorized to view this page</TITLE" in contents:
            print_err('Authentication error, please check your .netrc file')
            print_err(('Put "machine seldclq140.corpusers.net ' +
                       'login <semcid> password <password>" in ' +
                       '.netrc file and run again.'))
            cherry_pick_exit(STATUS_DMS_SRV)
        #read fix for and ecb decision and add to dms tag list
        fixfor = re.findall(r'_lbFixFor.*>(.*)</span>&nbsp;</td>', contents)
        ecbdecision = re.findall(r'CCBECBDecisionLog.*>(.*)</span>&nbsp;</td>',
                                  contents)
        if fixfor and ecbdecision:
            fixfor = fixfor[0]
            ecbdecision = ecbdecision[0]
            if fixfor in OPT.dms_tags.split(','):
                commit_tag_list.append(cmt)
        print 'Collecting DMS info[' + int(progress*50/total) * '+',
        print int((total - progress)*50/total) * '-' + "]", str(progress),
        print '/' + str(total), "\r",
        sys.stdout.flush()

    print ''
    return commit_tag_list

def create_cherry_pick_list(commit_tag_list):
    """
    Make unique list and save it to file
    """
    target_branch = OPT.target_branch
    #make single commit for multiple dms
    commit_dict = {}
    for cmt in commit_tag_list:
        key = cmt.commit
        if commit_dict.has_key(key):
            commit_dict[key].dms += '-' + cmt.dms
        else:
            commit_dict[key] = cmt
    unique_commit_tag_list = [v for v in commit_dict.values()]

    os.chdir(OPT.cwd)
    do_log('\n'.join(str_list(unique_commit_tag_list)), echo=True,
           file_name="%s_cherrypick.csv" %(target_branch),
           info="Cherrys..")
    return unique_commit_tag_list

def get_git_user():
    """
    Collect git user id
    """
    gituser = None
    if OPT.gerrit_user:
        gituser = OPT.gerrit_user
    else:
        gituser = execmd([GIT, 'config', '--get', 'user.email'])[0]
        if gituser:
            gituser = gituser.split('@')[0]
        if not gituser:
            print_err("user.email is not configured for git yet")
            print_err("Please run this after git configuration is done.")
            cherry_pick_exit(STATUS_GIT_USR)
    return gituser

def cherry_pick(unique_commit_list, target_branch):
    """
    1. Create the topic-cherrypick branch
    2. Collect email addresses for review
    3. Cherry pick the commit
    4. Change the commit message
    5. push it to gerrit
    6. save the status to a file
    7. Move out from topic branch
    8. delete topic-cherrypick branch
    """
    ret_err = STATUS_OK
    gituser = get_git_user()
    if not OPT.mail_sender:
        OPT.mail_sender = gituser + '@sonyericsson.com'

    #keep the result here
    cherrypick_result = []
    dry_run = '_dry_run' if OPT.dry_run else ''

    #check cherry pick history
    old_cherries = None
    tag_server = None
    if OPT.dms_tag_server:
        tag_server = DMSTagServer(OPT.dms_tag_server)
        records = tag_server.retrieve(target_branch + dry_run)
        if not records:
            print_err("No old cherries found or server is not "+
                      "reachable to check old cherries")
        elif 'Unavailable' not in records:
            do_log(records, info="Old cherries", echo=True)
            old_cherries =  records.strip().split('\n')

    do_log("", info="Cherry pick starting...", echo=True)
    gerrit = Gerrit(gerrit_user=gituser)
    for cmt in unique_commit_list:
        #Check old cherries
        go_next = False
        if old_cherries:
            for cherry in old_cherries:
                if cmt.commit in cherry:
                    do_log('Already processed once %s' %cherry, echo=True)
                    go_next = True
                    break
        #end of old cherry check
        url_date = gerrit.is_commit_available(cmt.commit, cmt.target,
                                              cmt.name)
        if url_date[0]:
            do_log('%s is %s in Gerrit, url %s, last updated on %s' %
                   (cmt, url_date[2], url_date[0],
                    time.ctime(url_date[1])),
                    echo=True)
            if not go_next: # if not in tag server, but in Gerrit, add it
                if tag_server:
                    if not tag_server.update(target_branch + dry_run,
                                       [str(cmt) + ',' + url_date[0]]):
                        print_err("Server is not reachable to update")
            continue
        if go_next:
            continue
        pick_result = ''
        do_log( 'Cherry picking %s ..' % cmt, echo=True)
        os.chdir(os.path.join(OPT.cwd, cmt.path))
        #checkout the topic branch
        r_cmd = [GIT, 'checkout', '-b', 'topic-cherrypick', 'origin/'
                 + cmt.target]
        git_log, err, ret = execmd(r_cmd)
        if ret == 0:
            reviewers, url = gerrit.collect_email_addresses(cmt.commit)
            if  OPT.reviewers:
                reviewers +=  OPT.reviewers.split(',')
            # now cherry pick
            git_log, err, ret = execmd([GIT, 'cherry-pick', '-x', cmt.commit])
            if ret == 0:
                #now edit commit msg to remove change id
                commit_msg = open(".git/COMMIT_EDITMSG", 'r').read().split('\n')
                commit_msg_file = open(".git/COMMIT_EDITMSG", 'w')
                for msg in commit_msg:
                    if not re.match(r"^Change-Id: \S+\s*$", msg):
                        commit_msg_file.write(msg + '\n')
                commit_msg_file.close()

                #amend to add a new change id
                git_log, err, ret = execmd([GIT, 'commit', '--amend',
                                            '-F', '.git/COMMIT_EDITMSG'])
                cmd = [GIT, 'push',
                       '--receive-pack=git receive-pack %s' %
                       ' '.join(['--reviewer %s' %r for r in reviewers]),
                       'ssh://%s@review.sonyericsson.net:29418/%s.git' %
                       (gituser,cmt.name),
                       'HEAD:refs/for/%s' % cmt.target]
                if OPT.dry_run:
                    cmd.append('--dry-run')
                git_log, err, ret = execmd(cmd)
                do_log(err)
                if ret == 0:
                    if OPT.dry_run:
                        pick_result = 'Dry-run ok'
                    else:
                        match = re.search('http[s]?://review.sonyericsson.net/[0-9]+', err)
                        if match:
                            #collect the gerrit id
                            pick_result = match.group(0)
                            if OPT.approve:
                                gerrit.approve(pick_result)
                        else:
                            pick_result = 'Gerrit URL not found after push'
                else:
                    pick_result = 'Failed to push to Gerrit'
            else:
                emails = [gituser+'@sonyericsson.com'] if OPT.dry_run else reviewers
                if 'the conflicts' in err:
                    pick_result = 'Failed due to merge conflict'
                    conflict_mail(target_branch, url, cmt.commit,
                                  emails, pick_result)
                elif 'is a merge but no -m' in err:
                    pick_result = 'It is a merge commit'
                elif 'nothing to commit' in git_log:
                    pick_result = 'Already merged, nothing to commit'
                else:
                    pick_result = 'Failed due to unknown reason'
                    conflict_mail(target_branch, url, cmt.commit,
                                  emails, pick_result)
                print_err(err)
                print_err("Resetting to HEAD...")
                git_log, err, ret = execmd([GIT, 'reset', '--hard'])
                do_log(git_log)
        else:
            pick_result = '%s %s' % (git_log, err)
            do_log(pick_result)
        #move to origin and delete topic branch
        git_log, err, ret = execmd([GIT, 'checkout', 'origin/' + cmt.target])
        do_log(git_log)
        git_log, err, ret = execmd([GIT, 'branch', '-D' , 'topic-cherrypick'])
        do_log(git_log)
        if (not pick_result.startswith('https://review.sonyericsson.net'
                                       if not OPT.dry_run else 'Dry-run ok')):
            ret_err = STATUS_CHERRYPICK_FAILED

        cherrypick_result.append(str(cmt) + ',' + pick_result)
        if tag_server:
            if not tag_server.update(target_branch + dry_run,
                                       [str(cmt) + ',' + pick_result]):
                print_err("Server is not reachable to update")

    os.chdir(OPT.cwd)
    #report the result if any cherry pick done
    if cherrypick_result:
        cherrypick_result.sort()
        do_log('\n'.join(cherrypick_result), echo=True, file_name=
              "%s_cherrypick%s_result.csv" %
              (target_branch, dry_run), info="New cherries picked:")
    else:
        do_log("No new cherry", echo=True)
    return ret_err

def execmd(cmd, timeout=30):
    """
    Execute a command in a new child process. The child process is killed
    if the timeout is up.
    """
    kill_check = threading.Event()

    def kill_process_after_timeout(pid):
        p = subprocess.Popen(['ps', '--ppid', str(pid)],
                             stdout=subprocess.PIPE)
        child_pids = []
        for line in p.stdout:
            if len(line.split()) > 0:
                local_pid = (line.split())[0]
                if local_pid.isdigit():
                    child_pids.append(int(local_pid))
        os.kill(pid, signal.SIGKILL)
        for child_pid in child_pids:
            os.kill(child_pid, signal.SIGKILL)
        kill_check.set() #tell the main routine that we had to kill
        return

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        watchdog = threading.Timer(timeout,
                                   kill_process_after_timeout,
                                   args=(process.pid, ))
        watchdog.start()
        out, err = process.communicate()
        result_out = ''.join(out).strip()
        result_err = ''.join(err).strip()
        watchdog.cancel() #if it's still waiting to run
        if kill_check.isSet():
            result_err = "Timeout: the command \"%s\" did not " \
                         "complete in %dsec." % (" ".join(cmd), timeout)
        kill_check.clear()
        if process.poll() != 0 and OPT.verbose:
            print_err('Error executing: ' + " ".join(cmd))
        return result_out, result_err, process.poll()
    except OSError, exp:
        print_err(exp)
    except KeyboardInterrupt:
        kill_process_after_timeout(process.pid)
        watchdog.cancel()
        print
        cherry_pick_exit(STATUS_USER_ABORTED)

def print_err(err):
    """print error message"""
    print >> sys.stderr, err
    sys.stderr.flush()

def do_log(contents, file_name=None, info=None, echo=False):
    """
    log function to write in file or/and print to stdout
    """
    if file_name != None:
        log_file = open(file_name, 'wb')
        log_file.write(contents)
    if OPT.verbose or echo:
        if info != None:
            print (10*'=' ) + info + (10*'=' )
        print >> sys.stdout, contents
    sys.stdout.flush()

def create_branch_mail(branch, name, recipient):
    """
    Mail to notify branch creation.
    """
    subject = ('[Cherrypick] [%s] New branch created for %s.'%
               (branch, name))
    body = ('Hello,\n\nNew branch has been created for %s.' % name +
            '\nPlease update manifest file of %s branch and reply '% branch +
            'this mail with change id.\n\nThanks,\nCherry-picker.')
    email(subject, body, recipient)

def update_manifest_mail(branch, name, recipient):
    """
    Mail to update manifest request.
    """
    subject = ('[Cherrypick] [%s] Manifest is not updated for %s.'%
               (branch, name))
    body = ('Hello,\n\nManifest file of %s branch is not updated ' % branch +
            'for %s.\nPlease update manifest file for %s '% (name, branch) +
            'branch and reply this mail with change id.' +
            '\n\nThanks,\nCherry-picker.')
    email(subject, body, recipient)

def conflict_mail(branch, url, change_id, recipient, result):
    """
    Mail for cherry pick conflict.
    """
    subject = ('[Cherrypick] [%s] cherry-pick of change %s has failed.'%
               (branch, change_id))
    body = ('Hello,\n\nAutomated cherry-pick of %s into %s '%(url, branch) +
            'branch has failed.\n\n%s.\n\nPlease ' %(result) +
            'manually upload this if it is needed for %s branch and ' %branch +
            'add the following persons as reviewers:\n%s' %'\n'.join(recipient)+
            '\nPlease reply to this mail with the new change ID once it is'+
            ' done.\n\nThanks,\nCherry-picker.'+
            '\n\nUseful links:'+
            '\n\nHow to cherry pick:'+
            ' https://wiki.sonyericsson.net/androiki/How_to_cherry-pick' +
            '\nCherry pick status page:' +
            ' http://android-cm-web.sonyericsson.net/cherrypick/index.php')
    email(subject, body, recipient)

def email(subject, body, recipient):
    '''
    Email function
    '''
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header

    sender = OPT.mail_sender
    msg = MIMEText(body)
    msg['Subject'] = Header(subject)
    if not OPT.dry_run:
        recipient.append(sender)
    msg['From'] = sender
    msg['To'] = ', '.join(recipient)
    # Send the email via our own SMTP server.
    try:
        mailer = smtplib.SMTP('smtpem1.sonyericsson.net')
        mailer.sendmail(sender, recipient, msg.as_string())
        mailer.quit()
    except smtplib.SMTPException, exp:
        print_err('Failed to send mail due to SMTP error: %s'%exp[1])
        return
    do_log('Mail sent to %s for %s' % (', '.join(recipient), subject))

def config_parser():
    """
    Parse config file and load the values into OPT option parser. Config file
    has higher priority on default command line parameter values(e.g. cwd) and
    command line parameter has higher priority than config file values for
    others.
    """
    import ConfigParser
    config = ConfigParser.SafeConfigParser()
    try:
        config.read(OPT.config_file)
        items = dict(config.items(OPT.target_branch))
    except ConfigParser.NoSectionError, exp:
        print_err("No branch configuration in config file: %s"% exp)
        cherry_pick_exit(STATUS_FILE)
    except ConfigParser.ParsingError, exp:
        print_err("%s file parsing error: %s"% (OPT.config_file, exp))
        cherry_pick_exit(STATUS_FILE)
    except ConfigParser.Error, exp:
        print_err("Config File error: %s"% exp)
        cherry_pick_exit(STATUS_FILE)

    for key, value in OPT.__dict__.iteritems():
        if items.has_key(key):
            if value: #handle default values here and give priority to config
                if key == 'cwd':
                    OPT.__dict__[key] = items[key]
                if key == 'target_branch_patterns':
                    OPT.__dict__[key] = items[key]
            else:     # cmd line parameter has higher priority on non-defaults
                if items[key].lower() == 'true':
                    OPT.__dict__[key] = True
                elif items[key].lower() == 'false':
                    OPT.__dict__[key] = False
                elif items[key].lower() == 'none':
                    OPT.__dict__[key] = None
                else:
                    OPT.__dict__[key] = items[key]

def main():
    """
    Cherry pick main function
    """
    global OPT_PARSER, OPT
    OPT_PARSER = option_parser()
    OPT = OPT_PARSER.parse_args()[0]

    if len(sys.argv) <2:
        OPT_PARSER.error("Insufficient arguments")
    if OPT.config_file:
        if not OPT.target_branch:
            print_err("Must pass target (-t) branch name")
            cherry_pick_exit(STATUS_ARGS)
        config_parser()


    args = ["%s = %s" % (key, value) for key, value in OPT.__dict__.iteritems()]
    do_log("Arguments are:\n%s\n" %"\n".join(args), echo=False)
    status_code = STATUS_OK

    if not os.path.exists(OPT.cwd+'/.repo' ):
        print_err(('repo not installed, Use "repo init -u url" to '+
                   'install it here. '))
        cherry_pick_exit(STATUS_REPO)

    do_log("Cherrypick.py " +__version__, info="Cherry pick script", echo=True)
    if OPT.cwd:
        OPT.cwd = os.path.abspath(OPT.cwd)
        os.chdir(OPT.cwd)

    if not OPT.no_repo_sync:
        repo_sync()

    if  OPT.csv_file:
        commit_list = []
        if OPT.target_branch == None:
            print_err("Must pass target (-t) branch name")
            cherry_pick_exit(STATUS_ARGS)
        try:
            csv = open(OPT.csv_file, 'r')
            unique_commit_list = csv.read().splitlines()
        except IOError, err:
            print_err(err)
            cherry_pick_exit(STATUS_FILE)
        for commit in unique_commit_list:
            prts = commit.split(',')
            if len(prts) < 5:
                print_err('Not enough parameters in %s' %commit)
                continue
            else:
                cmt = Commit(target=prts[0], path=prts[1], name=prts[2],
                             commit=prts[3], dms=prts[4])
                commit_list.append(cmt)
        if commit_list:
            status_code = cherry_pick(commit_list, OPT.target_branch)
        cherry_pick_exit(status_code)

    if (OPT.target_branch is None or OPT.dms_tags is None):
        print_err(("Must provide target branch name (-t) " +
                              "and DMS tag list (-d)"))
        OPT_PARSER.print_help()
        cherry_pick_exit(STATUS_ARGS)

    commit_list = get_dms_list(OPT.target_branch)
    if not commit_list :
        do_log("Nothing is found to process ", echo=True)
        cherry_pick_exit(STATUS_OK)

    commit_tag_list = dms_get_fix_for(commit_list)
    unique_commit_list = create_cherry_pick_list(commit_tag_list)
    if not OPT.no_push_to_gerrit:
        status_code = cherry_pick(unique_commit_list, OPT.target_branch)

    cherry_pick_exit(status_code)

if __name__ == '__main__':
    main()
