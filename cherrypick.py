#!/usr/bin/env python

'''
@author: Ekramul Huq

@version: 0.1.5
'''

DESCRIPTION = \
'''
Find cherry pick candidates in source branch(es) by processing the git log of
each base branch and target branch. From the log, list of DMSs will be checked
with DMS server and commits with correct DMS tag (--dms-tags) will be
considered. Commits with the DMSs mentioned in dms_filter.txt will be excluded.
Then the potential commits will be pushed to Gerrit for review. As a byproduct
a .csv file will be created with the commit list and a _result.csv file with
the result of each cherry pick execution.

During each cherry pick, commit id will be checked in Gerrit commit message,
and cherry pick of this commit will be skipped if corresponding commit is found
in open or abandoned state.

It is possible to simulate the whole process by using the --dry-run option and
possible to create only the cherry pick list and skip the push to Gerrit
action with the -n(--no-push-to-gerrit) option.

SEMC username and password are required in .netrc file for DMS tag check.

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

DMS_URL = "http://seldclq140.corpusers.net/DMSFreeFormSearch/\
WebPages/Search.aspx"

__version__ = '0.1.5'

REPO = 'repo'
GIT = 'git'
OPT_PARSER = None
OPT = None

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
        emails = None
        if gerrit_patchsets:
            approvals_email = filter(lambda a: "email" in a["by"],
                                     gerrit_patchsets["currentPatchSet"]
                                     ["approvals"])
            emails = list(set([a["by"]["email"] for a in approvals_email]))
        return emails

    def is_commit_available(self, commit, target_branch, prj_name):
        '''
        Return (url,date) tuple if commit is available in target_branch
        in open or abandoned state, otherwise return (None,None,None) tuple
        '''
        r_cmd = ['ssh', '-p', self.port, self.address,
                 '-l', self.gerrit_user,
                 'gerrit',
                 'query',
                 '--format='+self.data_format,
                 'project:'+prj_name, 'status:open',
                 'message:cherry.picked.from.commit.' + commit,
                 'OR',
                 'project:'+prj_name, 'status:abandoned',
                 'message:cherry.picked.from.commit.' + commit,
                 '--current-patch-set',
                 'branch:' + target_branch
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

class Commit:
    """Data structure for a single commit"""
    base, path, name, = None, None, None
    author_date, commit, title, dms = None, None, None, None
    def __init__(self, base=None, path=None, name=None,
                 author_date=None, commit=None, dms=None, title=None):
        self.base = base
        self.path = path
        self.name = name
        self.author_date = author_date
        self.commit = commit
        self.dms = dms
        self.title = title
    def cmp(self, commit):
        """compare itself with another commit"""
        if (((self.base, self.name, self.dms) ==
            (commit.base, commit.name, commit.dms)) and
            (self.author_date == commit.author_date or
             self.title == commit.title)) :
            #check author date and title if either one match, to detect
            #manual cherry pick which has different author date in base
            #and target
            return True
        return False
    def __str__(self):
        return "%s,%s,%s,%s,%s" % (self.base, self.path,
                   self.name, self.commit, self.dms)

def str_list(commit_list):
    """Helper function to convert a list of Commit to list of strings"""
    commit_list = [str(cmt) for cmt in commit_list]
    commit_list.sort()
    return commit_list

def option_parser():
    """
    Option parser
    """
    usage = ("%prog -b BASE_BRANCHES,... -t TARGET_BRANCH " +
             "-d DMS_TAGS,... [options]")
    opt_parser = optparse.OptionParser(formatter=HelpFormatter(),
                                       usage=usage, description=DESCRIPTION,
                                          version='%prog ' + __version__)
    opt_parser.add_option('-b', '--base-branches',
                     dest='base_branches',
                     help='base branches (comma separated)',
                     action="store", default=None)
    opt_parser.add_option('-t', '--target-branch',
                     dest='target_branch',
                     help='target branch')
    opt_parser.add_option('-d', '--dms-tags',
                     dest='dms_tags',
                     help='DMS tags (comma separated)',
                     action="store", default=None)
    opt_parser.add_option('-r', '--reviewers',
                     dest='reviewers',
                     help='default reviewers (comma separated)',
                     action="store", default=None)
    opt_parser.add_option('--dms-filter',
                     dest='dms_filter',
                     help='DMS filter file name', default='dms_filter.txt',
                     metavar="FILE")
    opt_parser.add_option('-w', '--work-dir',
                     dest='cwd',
                     help='working directory, default is current directory',
                     action="store", default=os.getcwd())
    #debug options
    opt_group = opt_parser.add_option_group('Debug options')
    opt_group.add_option('-v', '--verbose',
                     dest="verbose", action="store_true", default=False,
                     help="Verbose")
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
              STATUS_OK: "Cherry pick completed.",
              STATUS_CHERRYPICK_FAILED : "Some or all cherry picks failed.",
              STATUS_REPO: "Repo error",
              STATUS_DMS_SRV: "DMS tag server is not reachable",
              STATUS_MANIFEST: "Manifest file error",
              STATUS_ARGS: "Using wrong arguments",
              STATUS_FILE: "File error",
              STATUS_GIT_USR: "Git config error",
              STATUS_GERRIT_ERR: "Gerrit server is not reachable"
              }
    msg = reason.get(exit_code)
    if exit_code != STATUS_OK:
        print_err(msg)
    else:
        do_log(msg, echo=True)
    exit(exit_code)

def repo_sync():
    """
    Repo sync
    """
    do_log("Repo sync ....", echo=True)
    os.chdir(OPT.cwd)
    result, err, ret = execmd([REPO, 'sync', '-j5'])
    do_log(result, file_name='repo_sync.log')
    if ret != 0:
        print_err("Repo sync error %s" %err)
        cherry_pick_exit(STATUS_REPO)

def get_dms_list(target_branch):
    """
    Collect the DMSs from all projects, from MERGE_BASE to  BASE_BRANCH and
    from MERGE_BASE to  TARGET_BRANCH. Return the DMSs list which are not in
    TARGET_BRANCH.
    """
    base_manifest = None
    try:
        base_manifest = open(os.path.join(OPT.cwd, '.repo')+
                      '/manifest.xml','r').read()
    except IOError, err:
        print_err(err)
        cherry_pick_exit(STATUS_MANIFEST)
    base_proj_rev_dict = {}
    dom = xml.dom.minidom.parseString(base_manifest)
    def_rev = dom.getElementsByTagName("default")[0].getAttribute('revision')
    dom_nodes = dom.getElementsByTagName("project")
    for node in dom_nodes:
        rev = node.getAttribute('revision')
        path = node.getAttribute('path')
        name = node.getAttribute('name')
        rev = def_rev if rev == '' else rev
        for base_branch in  OPT.base_branches.split(','):
            if rev == base_branch:
                base_proj_rev_dict[name] = base_branch + ',' + path
                break

    merge_base_log = open('merge-base.log', 'wb')
    base_log = open('source_commit.log', 'wb')
    target_log = open(target_branch + '_commit.log', 'wb')
    base_commit_list, target_commit_list = [], []
    os.chdir(os.path.join(OPT.cwd, '.repo/manifests'))
    cmd = [GIT, 'show', 'origin/' + target_branch +':default.xml']
    dst_manifest, err, ret = execmd(cmd)
    if ret != 0:
        print_err("manifest file for origin/%s not found.\n" % target_branch)
        cherry_pick_exit(STATUS_MANIFEST)
    dom = xml.dom.minidom.parseString(dst_manifest)
    dom_nodes = dom.getElementsByTagName("project")
    dst_proj_rev = {}
    for node in dom_nodes:
        dst_proj_rev[node.getAttribute('path')] = node.getAttribute('revision')

    for name, rev_path in base_proj_rev_dict.iteritems():
        #-------check if current git is available in destination ------
        target_revision = None
        path = rev_path.split(',')[1]
        base_rev = rev_path.split(',')[0]
        os.chdir(os.path.join(OPT.cwd, path))
        ret = execmd([GIT, 'show-ref', '-q', '--verify',
                      'refs/remotes/origin/' + target_branch])[2]
        if ret != 0:
            if dst_proj_rev.has_key(path):
                revision = dst_proj_rev[path]
                if revision :
                    target_revision = revision
                    os.chdir(os.path.join(OPT.cwd, path))
                    ret = execmd([GIT, 'show-ref', '-q', '--verify',
                                'refs/remotes/origin/' + target_revision])[2]
                    #if target_revision exits
                    if ret == 0:
                        #its a branch name
                        target_revision = 'origin/' + target_revision
                    #otherwise its sha1 or tag
                else:
                    target_revision = 'origin/' + target_branch #use default
            else:
                print_err("Branch not found in destination for git %s" % name)
                continue
            if target_revision == 'origin/' + base_rev:
                #no need to merge
                continue
        #------------end of unspecified git in destination handle--------------

        os.chdir(os.path.join(OPT.cwd, path))
        if target_revision is None:
            target_revision = 'origin/' + target_branch

        mergebase, err, ret = execmd([GIT, 'merge-base', 'origin/' +
                                      base_rev, target_revision])
        if not mergebase:
            merge_base_log.write('No merge-base for %s and %s\n' %
                                 (base_rev, target_branch))
            print_err(err)
            continue
        merge_base_log.write(mergebase + '\n')
        #read merge base to base branch log
        b_commit_list = collect_fix_dms('origin/' + base_rev, mergebase,
                                   rev_path + ',' + name, base_log)
        if b_commit_list:
            base_commit_list += b_commit_list
        #read merge base to target branch log
        t_commit_list = collect_fix_dms(target_revision, mergebase,
                                   rev_path + ',' + name, target_log)
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
            rev, path, name = project.split(',')
            cmt = Commit(base=rev, path=path, name=name, dms=dms_id,
                         commit=commit_id, author_date=author_date,
                         title=title)
            commit_list.append(cmt)

    return commit_list


def filter_dms_list(commit_list):
    """
    Filter the DMSs which are mentioned in dms_filter.txt file.
    Commit that matches the filter will be excluded.
    """
    if not os.path.exists(OPT.dms_filter):
        print_err("File not found " + OPT.dms_filter)
        print_err("Continue without DMS filter.")
        return commit_list

    dms_filter_file = open(OPT.dms_filter, 'r')
    dms_filter = dms_filter_file.read()
    filtered_commit_list = []
    for cmt in commit_list:
        if cmt.dms not in dms_filter:
            filtered_commit_list.append(cmt)
    return filtered_commit_list

def dms_get_fix_for(commit_list):
    """
    Collect DMS status from DMS server. Collect only the commits match with
    OPT.tag_list
    """
    commit_tag_list = []
    progress = 0
    total = len(commit_list)

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

def cherry_pick(unique_commit_list, target_branch):
    """
    1. Create the topic-cherrypick branch
    2. Collect email addresses for review
    3. Cherry pick the commit
    4. Change the commit message
    5. push it to gerrit
    6. save the status to a file
    7. Checkout source branch
    8. delete topic-cherrypick branch
    """
    ret_err = STATUS_OK
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
    #keep the result here
    result_dms_tag_list = []
    dry_run = '_dry_run' if OPT.dry_run else ''

    do_log("", info="Cherry pick starting...", echo=True)
    gerrit = Gerrit(gerrit_user=gituser)
    for cmt in unique_commit_list:
        url_date = gerrit.is_commit_available(cmt.commit, target_branch,
                                              cmt.name)
        if url_date[0]:
            do_log('%s is %s in Gerrit, url %s, last updated on %s' %
                   (cmt, url_date[2], url_date[0],
                    time.ctime(url_date[1])),
                    echo=True)
            continue

        pick_result = ''
        do_log( 'Cherry picking %s ..' % cmt, echo=True)
        os.chdir(os.path.join(OPT.cwd, cmt.path))
        #checkout the topic branch
        r_cmd = [GIT, 'checkout', '-b', 'topic-cherrypick', 'origin/'
                 + target_branch]
        git_log, err, ret = execmd(r_cmd)
        if ret == 0:
            emails = gerrit.collect_email_addresses(cmt.commit)
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
                reviewers = emails
                if  OPT.reviewers:
                    reviewers +=  OPT.reviewers.split(',')
                cmd = [GIT, 'push',
                       '--receive-pack=git receive-pack %s' %
                       ' '.join(['--reviewer %s' %r for r in reviewers]),
                       'ssh://%s@review.sonyericsson.net:29418/%s.git' %
                       (gituser,cmt.name),
                       'HEAD:refs/for/%s' % target_branch ]
                if OPT.dry_run:
                    cmd.append('--dry-run')
                git_log, err, ret = execmd(cmd)
                do_log(err)
                if ret == 0:
                    if OPT.dry_run:
                        pick_result = 'Dry-run ok'
                    else:
                        match = re.search('https://review.sonyericsson.net/[0-9]+', err)
                        if match:
                            #collect the gerrit id
                            pick_result = match.group(0)
                        else:
                            pick_result = 'Failed'
                else:
                    pick_result = 'Failed'
            else:
                if 'the conflicts' in err:
                    pick_result = 'Failed due to merge conflict'
                elif 'nothing to commit' in git_log:
                    pick_result = 'Already merged, nothing to commit'
                else:
                    pick_result = 'Failed due to unknown reason'
                print_err(err)
                print_err("Resetting to HEAD...")
                git_log, err, ret = execmd([GIT, 'reset', '--hard'])
                do_log(git_log)
        else:
            pick_result = 'Failed'
        #move to origin and delete topic branch
        git_log, err, ret = execmd([GIT, 'checkout', 'origin/' + target_branch])
        do_log(git_log)
        git_log, err, ret = execmd([GIT, 'branch', '-D' , 'topic-cherrypick'])
        do_log(git_log)
        if (not pick_result.startswith('https://review.sonyericsson.net'
                                       if not OPT.dry_run else 'Dry-run ok')):
            ret_err = STATUS_CHERRYPICK_FAILED

        result_dms_tag_list.append(str(cmt) + ',' + pick_result)
    os.chdir(OPT.cwd)
    do_log('\n'.join(result_dms_tag_list), echo=True, file_name=
          "%s_cherrypick%s_result.csv" %
          (target_branch, dry_run), info="Result.")
    return ret_err

def execmd(cmd):
    """
    Execute a command in a new child process
    """
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        out, err = process.communicate()
        result_out = ''.join(out).strip()
        result_err = ''.join(err).strip()
        if process.wait() != 0 and OPT.verbose:
            print_err('Error to execute ' + " ".join(cmd))
        return result_out, result_err, process.poll()
    except OSError, exp:
        print_err(exp)


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

def main():
    """
    Cherry pick main function
    """

    global OPT_PARSER, OPT
    OPT_PARSER = option_parser()
    if len(sys.argv) <2:
        OPT_PARSER.error("Insufficient arguments")

    OPT = OPT_PARSER.parse_args()[0]
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
                cmt = Commit(base=prts[0], path=prts[1], name=prts[2],
                             commit=prts[3], dms=prts[4])
                commit_list.append(cmt)
        if commit_list:
            status_code = cherry_pick(commit_list, OPT.target_branch)
        cherry_pick_exit(status_code)

    if (OPT.base_branches is None or
       OPT.target_branch is None or
       OPT.dms_tags is None):
        print_err(("Must provide base branch name(s) (-b), " +
                              "target branch name (-t) " +
                              "and DMS tag list (-d)"))
        OPT_PARSER.print_help()
        cherry_pick_exit(STATUS_ARGS)

    if OPT.target_branch in OPT.base_branches.split(','):
        print_err("Base branch and target branch is same.")
        cherry_pick_exit(STATUS_ARGS)

    commit_list = get_dms_list(OPT.target_branch)
    if not commit_list :
        do_log("Nothing is found to process ", echo=True)
        cherry_pick_exit(STATUS_OK)

    filtered_commit_list = filter_dms_list(commit_list)
    commit_tag_list = dms_get_fix_for(filtered_commit_list)
    unique_commit_list = create_cherry_pick_list(commit_tag_list)
    if not OPT.no_push_to_gerrit:
        status_code = cherry_pick(unique_commit_list, OPT.target_branch)

    cherry_pick_exit(status_code)

if __name__ == '__main__':
    main()
