#!/usr/bin/env python

from optparse import OptionParser
import os
import sys

from gerrit import GerritSshConnection, GerritQueryError
from processes import run_cmd, ChildRuntimeError
from semcutil import fatal

GERRIT_SERVER = "review.sonyericsson.net"


def get_commit(git_dir, tag):
    """
       This function returns the commit SHA1 corresponding to the given tag.
    """

    command = ["git", "--git-dir", os.path.join(git_dir, ".git"),
               "rev-list", tag, "-n", "1"]
    exitcode, commitid, err = run_cmd(command)
    return commitid


def get_branch(gerrit_conn_obj, git_dir, tag):
    """
        This function returns the branch name where the tag is tagged on via
        gerrit record.
    """

    commitid = get_commit(git_dir, tag)
    branch = ""
    res = gerrit_conn_obj.query(commitid)
    if res:
        if "branch" in res[0]:
            branch = res[0]["branch"]
        else:
            fatal(1, "There's no branch property in the record.")
    else:
        #when the tag is tagged on a merged commit, there's no record in gerrit
        #for this, then we search its first parent commit. If not find this
        #time, it will search the the parent of the parent, until the original
        #commit, and exit
        tag += "^"
        branch = get_branch(gerrit_conn_obj, git_dir, tag)
    return branch


def _main():
    usage = "Usage: %prog [-s server_name] [-u user_name] <-d git_dir> <tag>"
    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--dir", dest="git_dir",
                      help="set the git directory")
    parser.add_option("-s", "--server-name", dest="server_name",
                      default=GERRIT_SERVER,
                      help="set the host name of gerrit server")
    parser.add_option("-u", "--user-name", dest="user_name",
                      help="overwrite the user name in gerrit module")
    (options, args) = parser.parse_args()
    if len(args) != 1:
        fatal(1, "Wrong number of arguments \n %s" % usage)
    tag = args[0]
    if not options.git_dir:
        fatal(1, "Please specify the git directory")
    try:
        conn_obj = GerritSshConnection(options.server_name, options.user_name)
        branch = get_branch(conn_obj, options.git_dir, tag=tag)
    except ChildRuntimeError, error:
        fatal(1, "Reach to the initial commit without results!")
    except GerritQueryError, error:
        fatal(1, "Can't get branch for %s" % tag)
    except Exception, error:
        fatal(1, error)
    print branch


if __name__ == "__main__":
    _main()
