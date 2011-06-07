#!/usr/bin/env python

'''
@author: Ekramul Huq

@version: 0.1.2

@bug: not verified against gerrit if the commit is already in gerrit for review
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

DMS_URL = "http://seldclq140.corpusers.net/DMSFreeFormSearch/\
WebPages/Search.aspx"

__version__ = '0.1.1'

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
              STATUS_GIT_USR: "Git config error"
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
    TARGET_BRANCH (one with commit id and another without commit id).
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
    target_log = open(target_branch + '_destination_commit.log', 'wb')

    base_dms_list, target_dms_list = [], []
    base_dms_commit_list = []

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
        #print path + ',' + name
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

        cmd = [GIT, 'merge-base', 'origin/'
                 + base_rev, target_revision]
        mergebase, err, ret = execmd(cmd)

        if mergebase == '':
            merge_base_log.write('No merge-base for '
                           + base_rev + 'and' + target_branch + '\n')
            print >> sys.stderr, err, ret
            continue
        merge_base_log.write(mergebase + '\n')
        #read merge base to base branch log
        dms_list, dms_commit_list = collect_fix_dms('origin/' + base_rev,
                                                    mergebase,
                                                    rev_path + ',' + name,
                                                    base_log)
        base_dms_list.extend(dms_list)
        base_dms_commit_list.extend(dms_commit_list)
        #read merge base to destination branch log
        dms_list, dms_commit_list = collect_fix_dms(target_revision,
                                                     mergebase,
                                                     rev_path + ',' + name,
                                                     target_log)

        target_dms_list.extend(dms_list)
        os.chdir(OPT.cwd)

    base_dms_list.sort()
    do_log('\n'.join(base_dms_list), file_name='source_dms_list.log')
    target_dms_list.sort()
    do_log('\n'.join(target_dms_list), file_name=
            target_branch + '_destination_dms_list.log')
    #Only keep the diff
    diff_list = list(set(base_dms_list) - set(target_dms_list))
    diff_list.sort()

    #now keep the project,git_name,sha1(of source),dms
    project_sha1_dms_list = []
    for dms in diff_list:
        for commit in base_dms_commit_list:
            if dms.split(',')[1] in commit and dms.split(',')[3] in commit:
                project_sha1_dms_list.append(commit)

    do_log('\n'.join(diff_list),
            file_name=target_branch + '_diff_dms_list.log',
            info='Diff list')
    project_sha1_dms_list = list(set(project_sha1_dms_list))
    return diff_list, project_sha1_dms_list


def collect_fix_dms(branch, commit_begin, project, log_file):
    """
    Collect FIX=DMSxxxxxxx and commit id from the logs.
    return list with and without commit id.
    """
    #return sorted dms list
    dms_list = []
    dms_commit_list = []
    r_cmd = [GIT, 'log', '--pretty=fuller', commit_begin + '..' + branch]
    git_log = execmd(r_cmd)[0]
    log_file.write(git_log + '\n')
    git_log_list = git_log.split('\n')
    commit_id, author_date = '', ''
    for log_str in git_log_list:
        if re.match(r'^commit\s.*?', log_str):
            commit_id = log_str.split(' ')[1] #sha1
        elif re.match(r'AuthorDate: ', log_str):
            author_date = log_str
        elif re.match(r'^\s*?FIX\s*=\s*DMS[0-9].*?', log_str):   #"FIX=DMSxxxxx"
            str_list = log_str.split('=')
            dms_id = str_list[1].strip()     #DMSxxxxxxx
            dms_list.append(project + ',' + dms_id + ',' + author_date)
            dms_commit_list.append(project + ',' + commit_id + ',' + dms_id)

    return dms_list, dms_commit_list


def filter_dms_list(dms_list):
    """
    Filter the DMSs which are mentioned in dms_filter.txt file.
    Commit that matches the filter will be excluded.
    """
    if not os.path.exists(OPT.dms_filter):
        print_err("File not found " + OPT.dms_filter)
        print_err("Continue without DMS filter.")
        return dms_list

    dms_filter_file = open(OPT.dms_filter, 'r')
    dms_filter = dms_filter_file.read()
    filtered_dms_list = []
    for dms in dms_list:
        if not dms.split(',')[4] in dms_filter:
            filtered_dms_list.append(dms)
    return filtered_dms_list

def dms_get_fix_for(sha1_dms_list):
    """
    Collect DMS status from DMS server. Collect only the commits match with
    OPT.tag_list
    """
    dms_tag_list = []
    progress = 0
    total = len(sha1_dms_list)

    for commit_dms in sha1_dms_list:
        dms = commit_dms.split(',')[4]
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
        if len(fixfor) and len(ecbdecision):
            fixfor = fixfor[0]
            ecbdecision = ecbdecision[0]
            if fixfor in OPT.dms_tags.split(','):
                dms_tag_list.append(commit_dms + ','+ fixfor + ',' +
                                    ecbdecision)
        print 'Collecting DMS info[' + int(progress*50/total) * '+',
        print int((total - progress)*50/total) * '-' + "]", str(progress),
        print '/' + str(total), "\r",
        sys.stdout.flush()

    print ''
    return dms_tag_list

def create_cherry_pick_list(dms_tag_list, target_branch):
    """
    Make unique list and save it to file
    """
    #make single commit for multiple dms
    commit_list = {}
    for commit in dms_tag_list:
        words = commit.split(',')
        key = words[0] + ',' + words[1] + ',' + words[2] + ','+ words[3]
        if commit_list.has_key(key):
            commit_list[key] = commit_list[key] + '-' + words[4]
        else:
            commit_list[key] = words[4]
    unique_dms_tag_list = [k + ',' + v for k, v in commit_list.iteritems()]
    os.chdir(OPT.cwd)
    unique_dms_tag_list.sort()
    do_log('\n'.join(unique_dms_tag_list), echo=True, file_name=
          "%s_cherrypick.csv" %(target_branch), info="Cherrys..")
    return unique_dms_tag_list

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
    gituser = execmd([GIT, 'config', '--get', 'user.email'])[0]
    if gituser != None:
        gituser = gituser.split('@')[0]
    if not gituser:
        print_err("user.email is not configured for git yet")
        print_err("Please run this after git configuration is done.")
        cherry_pick_exit(STATUS_GIT_USR)
    #keep the result here
    result_dms_tag_list = []
    dry_run = '_dry_run' if OPT.dry_run else ''
    #now we have path,git,commitid,dms
    for pick_candidate in unique_commit_list:
        pick_result = ''
        print 'Cherry picking %s ..' % pick_candidate
        picks = pick_candidate.split(',')
        if len(picks) < 5: # base,path,name,commit,dms
            continue
        proj_path, proj_name, commit = picks[1], picks[2], picks[3]
        os.chdir(os.path.join(OPT.cwd, proj_path))
        #checkout the topic branch
        r_cmd = [GIT, 'checkout', '-b', 'topic-cherrypick', 'origin/'
                 + target_branch]
        git_log, err, ret = execmd(r_cmd)
        if ret == 0:
            #get the review list of this commit
            r_cmd = ['ssh', '-p', '29418', 'review.sonyericsson.net', '-l',
                     gituser, 'gerrit', 'query', '--format=JSON',
                     'status:merged', 'limit:1', '--current-patch-set',
                     'commit:' + commit]
            out, err, ret = execmd(r_cmd)
            #collect email addresses from gerrit
            gerrit_patchsets = json.JSONDecoder().raw_decode(out)[0]
            if gerrit_patchsets:
                approvals_email = filter(lambda a: "email" in a["by"],
                                         gerrit_patchsets["currentPatchSet"]
                                         ["approvals"])
                emails = list(set([a["by"]["email"] for a in approvals_email]))

            # now cherry pick
            git_log, err, ret = execmd([GIT, 'cherry-pick', '-x', commit])
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
                       (gituser,proj_name),
                       'HEAD:refs/for/%s' % target_branch ]
                if OPT.dry_run:
                    cmd.append('--dry-run')
                git_log, err, ret = execmd(cmd)
                do_log(err)
                if ret == 0:
                    if OPT.dry_run:
                        pick_result = 'Dry-run ok'
                    else:
                        match = re.search('https://review.sonyericsson.net.*',
                                          err)
                        if match is not None:
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
                    pick_result = 'nothing to commit'
                else:
                    pick_result = 'Failed to cherry pick'
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

        result_dms_tag_list.append(pick_candidate + ',' + pick_result)
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
            print info
        print >> sys.stdout, contents

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

    print "Cherry pick starting..."
    if OPT.cwd:
        OPT.cwd = os.path.abspath(OPT.cwd)
        os.chdir(OPT.cwd)
    if not OPT.no_repo_sync:
        repo_sync()
    if  OPT.csv_file:
        if OPT.target_branch == None:
            print_err("Must pass target (-t) branch name")
            cherry_pick_exit(STATUS_ARGS)
        try:
            csv = open(OPT.csv_file, 'r')
            unique_commit_list = csv.read().splitlines()
        except IOError, err:
            print_err(err)
            cherry_pick_exit(STATUS_FILE)
        status_code = cherry_pick(unique_commit_list, OPT.target_branch)
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
    sha1_dms_list = get_dms_list(OPT.target_branch)[1]
    if len(sha1_dms_list) == 0:
        do_log("Nothing is found to process ", echo=True)
        cherry_pick_exit(STATUS_OK)

    filtered_dms_list = filter_dms_list(sha1_dms_list)
    dms_tag_list = dms_get_fix_for(filtered_dms_list)
    unique_commit_list = create_cherry_pick_list(dms_tag_list,
                                                 OPT.target_branch)
    if not OPT.no_push_to_gerrit:
        status_code = cherry_pick(unique_commit_list, OPT.target_branch)

    cherry_pick_exit(status_code)

if __name__ == '__main__':
    main()
