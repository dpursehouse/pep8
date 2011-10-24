#!/usr/bin/python
'''
     Name: release-shortlog.py

     Usage:
         This script is used to generate the DMS report and commits report
         for direct commits and rebased commits between two specified snapshot
         of one project against the given rebased project.
     Input:
         arguments:
            oldBuildId: It could be snapshot or the specifed manifest file.
            newBuildId: It could be snapshot or the specifed manifest file.
         options:
            -j, --job): The hudson job url. such as
                        http://android-ci.cnbj.sonyericsson.net/job/
                        offbuild_edream2.1/api/xml
            -p, --project): The project name, such as 2.1, the default value is
                            2.1.
            -w, --workspace): The directory contains .repo.
            -r, --rebase): The rebased project name or the manifest file of the
                           rebase  project.
            -q, --query): The name of the query file, the default value is
                          DMSquery.qry
            -c, --git-cmd): You can supply the git command to get the log info
                            as you like. The default is
                            "git shortlog --no-merges"
            -d, --debs-flag): With this flag, the script will generate the
                              package change list in variant spec between the
                              specified two snapshots.

'''

import subprocess
import sys
import os
from xml.dom import minidom
import urllib
import re
from optparse import OptionParser


def parse_config(config):
    project_dict = {}
    f = open("config", 'r')
    for line in f.readlines():
        line_pruned = line.strip()
        if line_pruned == "":
            continue
        elif line_pruned.startswith("project: "):
            project = line_pruned.split(": ")[1]
            project_dict[project] = {}
        else:
            (key, value) = line_pruned.split(": ")
            project_dict[project][key] = value
    f.close()
    return project_dict

project_dict = parse_config("config")


def fatal(exitcode, message):
    '''
        Takes exit code and error message as an arguments

        This method prints the error message on the stderr and exists with
        the provided exitcode.
    '''
    print >> sys.stderr, '%s: %s' % (os.path.basename(sys.argv[0]), message)
    sys.exit(exitcode)


def miniparse(url):
    return minidom.parse(urllib.urlopen(url))


def getTextOfFirstTagByName(element, name):
    rc = ""
    childElements = element.getElementsByTagName(name)
    if len(childElements) > 0:
        for node in childElements[0].childNodes:
            if node.nodeType == node.TEXT_NODE:
                rc = rc + node.data
    return rc.strip()


def dmsqueryShowNoTitle(gitlog):
    cmd = "dmsquery --show"
    dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dmslist_notitle = dmsquery.communicate(input=gitlog)[0]
    return dmslist_notitle.splitlines()


def dmsqueryShow(gitlog):
    cmd = "dmsquery --show-t"
    dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    dmslist = dmsquery.communicate(input=gitlog)[0]
    return dmslist.splitlines()


def dmsqueryQry(gitlog, query):
        cmd = "dmsquery -qry %s" % query

        dmsquery = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        dmsquery.communicate(input=gitlog)
        dmsquery.stdin.close()


def command(command):
    cmd = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    result = cmd.communicate()[0].splitlines()
    retval = cmd.returncode
    return (retval, result)


def get_main_job_url(project_name):
    if project_name not in project_dict.keys():
        fatal(1, "project %s is not defined in dictionary project_dict"
                % project_name)
    for project, project_info in project_dict.items():
        if project_name == project:
            site = project_info['site']
            branch = project_info['branch']
            if site == "seld":
                site = ""
            else:
                site = "." + site
            main_job_url = "http://android-ci%s.sonyericsson.net/view/CM/" \
                        "job/offbuild_%s/api/xml" % (site, branch)
            break
        else:
            continue
    return main_job_url


def generate_delta_packages(oldBuildId, newBuildId, old_manifest_obj,
                          new_manifest_obj):
    output = open('delta_packages_%s-%s.txt' \
                % (oldBuildId, newBuildId), 'w')
    print >>output, "Delta packages between %s and %s:" \
        % (oldBuildId, newBuildId)
    variant_spec_old_rev = old_manifest_obj.get_project_info(\
                                "semctools/semcsystem", "revision")
    variant_spec_new_rev = new_manifest_obj.get_project_info(\
                                "semctools/semcsystem", "revision")
    compare_var_spec = CompareVariantSpec(variant_spec_old_rev,
                                          variant_spec_new_rev)
    var_spec_dict = compare_var_spec.get_compare_result()
    if len(var_spec_dict) != 0:
        for variant_spec, packages in var_spec_dict.items():
            print >>output, "\n===%s===" % variant_spec
            if len(packages['removed']) != 0:
                print >> output, "** Removed packages: **"
                print >> output, '\n'.join(packages['removed']) + '\n'
            if len(packages['added']) != 0:
                print >> output, '** Added packages: **'
                print >> output, '\n'.join(packages['added']) + '\n'
    else:
        print >>output, "There's no packages changes between %s and %s" \
               % (oldBuildId, newBuildId)
    output.close()


class ManifestUrl:
    '''
        Get the Manifest url according to given build_id
    '''
    def __init__(self, build_id, main_job_url):
        self.build_id = build_id
        self.main_job_url = main_job_url
        self.manifest_url = ""
        self._parse_buildid()

    def _urljoin(self, first, *rest):
        return "/".join([first.rstrip('/'), "/".join([part.lstrip('/') \
            for part in rest])])

    def _parse_buildid(self):
        if os.path.isfile(self.build_id) or self.build_id.startswith('http://'):
            self.manifest_url = self.build_id
            job_url = "skip"
        else:
            job_url = "do"
        if not (self.main_job_url.endswith('api/xml')):
            self.main_job_url = self._urljoin(main_job_url, 'api', 'xml')
        if job_url == "do":
            main_job_xml = miniparse(self.main_job_url)
            for build in main_job_xml.getElementsByTagName("build"):
                build_job_url = getTextOfFirstTagByName(build, "url")
                build_job_xml = miniparse(self._urljoin(build_job_url, "api",
                                                        "xml"))
                try:
                    text = getTextOfFirstTagByName(build_job_xml, "description")
                    if job_url == "do":
                        if text.strip() == self.build_id:
                            print text.strip()
                            job_url = build_job_url
                            print "Found build job url: %s" % build_job_url
                            break
                except AttributeError:
                    continue
                    if job_url != "do":
                        break
        if self.manifest_url == "" and job_url != "do":
            self.manifest_url = self._urljoin(job_url,
                                 "artifact", "result-dir/manifest_static.xml")
        if self.manifest_url == "":
            fatal(1, "Could not find the manifest for %s" % self.build_id)

    def get_manifest_url(self):
        return self.manifest_url


class Manifest:
    '''
        Parse manifest and get the project related info.
    '''
    def __init__(self, manifest_xml):
        self.manifest = manifest_xml
        self.project_info = {}
        self._parse_manifest()

    def _parse_manifest(self):
        default_dom = self.manifest.getElementsByTagName("default")
        if default_dom:
            _default_rev = self.manifest.getElementsByTagName("default")[0].\
                  attributes["revision"].value
        prj_elements_list = self.manifest.getElementsByTagName("project")
        for project in prj_elements_list:
            self.project_info[project.attributes["name"].value] = {}
            if "revision" in project.attributes.keys():
                self.project_info[project.attributes["name"].value]["revision"]\
                    = project.attributes["revision"].value
            else:
                self.project_info[project.attributes["name"].value]["revision"]\
                    = _default_rev
            if "path" in project.attributes.keys():
                self.project_info[project.attributes["name"].value]["path"] \
                    = project.attributes["path"].value
            else:
                self.project_info[project.attributes["name"].value]["path"] \
                    = project.attributes["name"].value

    def get_project_list(self):
        return self.project_info.keys()

    def get_project_info(self, project, attribute):
        return self.project_info[project][attribute]


class CompareManifest:
    '''
        Compare two manifests, get the different info of the two manifests.
    '''
    def __init__(self, new_manifest_obj, old_manifest_obj=None):
        self.old_manifest_obj = old_manifest_obj
        self.new_manifest_obj = new_manifest_obj
        self.common_projects = []
        self.removed_projects = []
        self.added_projects = []
        self._compare()

    def _compare(self):
        old_project_set = set(self.old_manifest_obj.get_project_list())
        new_project_set = set(self.new_manifest_obj.get_project_list())
        self.common_projects = new_project_set.intersection(old_project_set)
        self.added_projects = new_project_set.difference(old_project_set)
        self.removed_projects = old_project_set.difference(new_project_set)

    def get_common_projects(self):
        return self.common_projects

    def get_removed_projects(self):
        return self.removed_projects

    def get_added_projects(self):
        return self.added_projects

    def get_old_manifest_obj(self):
        return self.old_manifest_obj

    def get_new_manifest_obj(self):
        return self.new_manifest_obj


class CompareRevisions:
    '''
        Compare two given revisions. Get the commit info between the two
        revisions.
    '''
    def __init__(self, compare_manifest_obj, rebase=None):
        self.compare_manifest_obj = compare_manifest_obj
        self.rebase = rebase
        self.commits_dict = {}
        self.direct_commits_dict = {}
        self._compare()

    def _compare(self):
        common_projects = self.compare_manifest_obj.get_common_projects()
        old_manifest_obj = self.compare_manifest_obj.get_old_manifest_obj()
        new_manifest_obj = self.compare_manifest_obj.get_new_manifest_obj()
        for project in common_projects:
            old_revision = old_manifest_obj.get_project_info(project,
                                                             "revision")
            new_revision = new_manifest_obj.get_project_info(project,
                                                             "revision")
            if old_revision == new_revision:
                continue
            else:
                project_path = new_manifest_obj.get_project_info(project,
                                                                 "path")
                self.commits_dict[project_path] = {}
                self.commits_dict[project_path]['full'] = []
                self.commits_dict[project_path]['direct'] = []
                self.commits_dict[project_path]['rebase'] = []
                _gitcmd = "git rev-list --no-merges"
                _commit_list = self.run_git_log(project_path, new_revision,
                                               old_revision, _gitcmd)
                for item in _commit_list:
                    self.commits_dict[project_path]['full'].append(item)
                if self.rebase is not None and \
                    project in self.rebase.get_project_list():
                    _commit_list = self.run_git_log(project_path,
                                                   new_revision,
                                                   old_revision,
                                                   _gitcmd,
                            self.rebase.get_project_info(project, 'revision'))
                for item in _commit_list:
                    self.commits_dict[project_path]['direct'].append(item)
                self.commits_dict[project_path]['rebase'].\
                    extend(list(set(self.commits_dict[project_path]['full']) - \
                        set(self.commits_dict[project_path]['direct'])))

    def get_commits_info(self):
        return self.commits_dict

    def get_dms_info(self, selector, query):
        concatlog = ""
        dmslist_notitle = []
        dmslist = []
        for project, commits_info in self.commits_dict.items():
            if selector in commits_info and len(commits_info[selector]) != 0:
                for item in commits_info[selector]:
                    gitlog = "\n".join(self.run_git_log(project, item,
                                                        "%s^" % item,\
                                       gitcmd="git log --no-merges"))
                    concatlog += gitlog
                    dmslist.extend(dmsqueryShow(concatlog))
                    dmslist_notitle.extend(dmsqueryShowNoTitle(concatlog))
            else:
                continue
        dmsqueryQry(concatlog, "%s_%s" % (selector, query))
        return (dmslist, dmslist_notitle)

    def run_git_log(self, path=None, newrev=None, oldrev=None, gitcmd=None,\
                    not_filter=None):
        rootdir = os.getcwd()
        try:
            os.chdir(path)
        except OSError:
            print >> sys.stderr, "Could not change directory to %s" % path
            sys.exit(2)
        cmd = "%s %s..%s" % (gitcmd, oldrev, newrev)
        if not_filter != None:
            for item in not_filter.split(','):
                if self._isRef("origin/%s" % item):
                    filterStr = " ^origin/%s" % item
                    cmd = cmd + filterStr
                else:
                    filterStr = " ^%s" % item
                    cmd = cmd + filterStr
        (ret, res) = command(cmd)
        os.chdir(rootdir)
        return res

    def _isRef(self, candidate, gitpath=None):
        cmd = "git show-ref %s" % candidate
        (ret, res) = command(cmd)
        if ret == 0:
            return True
        return False


class CompareVariantSpec:
    def __init__(self, old_rev, new_rev, path="vendor/semc/build/semcsystem"):
        self.old_rev = old_rev
        self.new_rev = new_rev
        self.variant_spec_dict = {}
        self.path = path
        self._compare()

    def _compare(self):
        rootdir = os.getcwd()
        os.chdir(self.path)
        if self.old_rev != self.new_rev:
            cmd = "git diff %s %s --relative=variant_spec" % (self.old_rev, \
                    self.new_rev)
            (ret, self.res) = command(cmd)
            os.chdir(rootdir)
            self._parse_result()
        os.chdir(rootdir)

    def _parse_result(self):
        for item in self.res:
            m1 = re.match("diff --git (?P<file>.*) .", item)
            if m1 is not None:
                file_name = m1.group('file').split('/')[2]
                self.variant_spec_dict[file_name] = {}
                self.variant_spec_dict[file_name]['removed'] = []
                self.variant_spec_dict[file_name]['added'] = []
            m2 = re.search("-\s+<package name=\"(?P<package>[\w|-]+).*>",\
                           item)
            m3 = re.search("^\+\s+<package name=\"(?P<package>[\w|-]+).*>",\
                           item)
            if m2:
                package = m2.group('package')
                self.variant_spec_dict[file_name]['removed'].append(package)
            if m3:
                package = m3.group('package')
                self.variant_spec_dict[file_name]['added'].append(package)

    def get_compare_result(self):
        return self.variant_spec_dict


def _main():
    '''
        Main funtion
    '''

    parser = OptionParser()
    parser.add_option("-p", "--project", dest="project",
                        default="2.1",
                        help="set the project name, such as 2.1")
    parser.add_option("-j", "--job", dest="job_url",
                       help="set the job url.")
    parser.add_option("-w", "--workspace", dest="workspace",
                        default=os.getcwd(),
                        help="set the workspace which directory contains .repo")
    parser.add_option("-q", "--query", dest="query", default="DMSquery.qry",
                        help="set the name of the output query file")
    parser.add_option("-r", "--rebase", dest="rebase",
                        help="set the rebased project")
    parser.add_option("-c", "--git-cmd", dest="gitcmd",
                        default="git shortlog --no-merges",
                        help="set the git command for output display")
    parser.add_option("-d", "--debs-flag", action="store_true",
                        dest="debs_flag",
                        help="with this flag, will generate the delta changes"
                             "in variant spec")
    parser.set_usage("\n%prog [Options] <old_build_id> <new_build_id>")
    (options, args) = parser.parse_args()
    if len(args) != 2:
        fatal(1, "%s\nfor detail info, please type ./release_info.py -h'" \
              % parser.usage)
    oldBuildId = args[0]
    newBuildId = args[1]
    rebase = options.rebase
    os.chdir(options.workspace)
    if options.job_url:
        new_manifest_url_obj = ManifestUrl(newBuildId, options.job_url)
        old_manifest_url_obj = ManifestUrl(oldBuildId, options.job_url)
    else:
        new_manifest_url_obj = \
            ManifestUrl(newBuildId, get_main_job_url(options.project))
        old_manifest_url_obj = \
            ManifestUrl(oldBuildId, get_main_job_url(options.project))
    new_manifest_obj = Manifest(miniparse(
        new_manifest_url_obj.get_manifest_url()))
    old_manifest_obj = Manifest(miniparse(
        old_manifest_url_obj.get_manifest_url()))
    compare_manifest_obj = CompareManifest(old_manifest_obj=old_manifest_obj,
                                           new_manifest_obj=new_manifest_obj)
    # Get the delta projects between two snapshot.
    added_projects = compare_manifest_obj.get_added_projects()
    removed_projects = compare_manifest_obj.get_removed_projects()
    if len(added_projects) != 0:
        print "=====Added Projects in %s against %s=====" \
            % (newBuildId, oldBuildId)
        for item in added_projects:
            print item
    if len(removed_projects) != 0:
        print "======Removed Projects in %s against %s=====" \
            % (newBuildId, oldBuildId)
        for item in removed_projects:
            print item
    # If debs_flag is true, generate package change list in variant spec
    if options.debs_flag:
        generate_delta_packages(oldBuildId, newBuildId,
                              old_manifest_obj, new_manifest_obj)
    # Handle the situation with rebase option is given.
    rebase_manifest = ""
    if rebase is not None:
        if os.path.isfile(rebase) or rebase.startswith("http://"):
            rebase_manifest = rebase
        else:
            if rebase in project_dict.keys():
                rebase_site = project_dict[rebase]['site']
                rebase_branch = project_dict[rebase]['branch']
                if rebase_site == 'seld':
                    rebase_site = ""
                else:
                    rebase_site = "." + rebase_site
                rebase_manifest = "http://android-ci%s.sonyericsson.net/view/"\
                  "CM/job/offbuild_%s/lastSuccessfulBuild/artifact/result-dir/"\
                  "manifest_static.xml" % (rebase_site, rebase_branch)

        rebase_manifest_obj = Manifest(miniparse(rebase_manifest))
        compare_revision_obj = CompareRevisions(compare_manifest_obj,
                                                rebase_manifest_obj)
    else:
        compare_revision_obj = CompareRevisions(compare_manifest_obj)
    # Get and output commit information
    commits_dict = compare_revision_obj.get_commits_info()
    commits_dict = compare_revision_obj.get_commits_info()
    total_commit_count = 0
    direct_commit_count = 0
    not_filter_commit_count = 0

    print "=======Direct Commit Information==========="
    for project, commits_info in commits_dict.items():
        direct_commit_count += len(commits_info['direct'])
        total_commit_count += len(commits_info['full'])
        if len(commits_info['direct']) != 0:
            print "*** %s ***" % project
        for item in commits_info['direct']:
            print '\n'.join(compare_revision_obj.run_git_log(project, item,\
                            "%s^" % item, options.gitcmd))

    print "======Rebased Commits Information========"
    for project, commits_info in commits_dict.items():
        not_filter_commit_count += len(commits_info['rebase'])
        if len(commits_info['rebase']) != 0:
            print "*** %s ***" % project
        for item in commits_info['rebase']:
            print '\n'.join(compare_revision_obj.run_git_log(project, item,\
                             "%s^" % item, options.gitcmd))
    (direct_dmslist, direct_dmslist_notitle) = \
        compare_revision_obj.get_dms_info('direct', options.query)
    (rebase_dmslist, rebase_dmslist_notitle) = \
            compare_revision_obj.get_dms_info('rebase', options.query)

    print "\n===Direct DMS Issues:==="
    if len(direct_dmslist_notitle) == 0:
        print "None"
    if len(direct_dmslist_notitle) != 0:
        if len(direct_dmslist_notitle) != len(direct_dmslist):
            print "Warning: There's problem with DMS server! " +\
                  "Can't get DMS title for following DMS!!!"
            for item in set(direct_dmslist_notitle):
                print item
        else:
            for item in set(direct_dmslist):
                print item

    print "\n===Rebased DMS Issues:==="
    if len(rebase_dmslist_notitle) == 0:
        print "None"
    if len(rebase_dmslist_notitle) != 0:
        if len(rebase_dmslist_notitle) != len(rebase_dmslist):
            print "Warning: There's problem with DMS server! " +\
                  "Can't get DMS title for following DMS!!!"
            for item in set(rebase_dmslist_notitle):
                print item
        else:
            for item in set(rebase_dmslist):
                print item

    print "=========Information Summary============"
    print "Total Commits Count: %d" % total_commit_count
    print "Direct Commits Count: %d" % direct_commit_count
    print "Rebased Commits Count: %d" % not_filter_commit_count
    print "Direct DMS Count: %d" % len(set(direct_dmslist_notitle))
    print "Rebased DMS Count: %d" % len(set(rebase_dmslist_notitle))

if __name__ == "__main__":
    _main()
