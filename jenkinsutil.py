'''Classes and helper methods to access Jenkins data'''

from datetime import datetime, timedelta
from time import gmtime
import os
import urllib2
from urlparse import urlunparse

# Suffix part of the api/xml url in python format
NET_SCHEME = 'http'
DEFAULT_SERVER = 'android-ci.sonyericsson.net'
API_PYTHON_URL_SUFFIX = 'api/python?depth=0'
DEFAULT_JOB_ID = 'lastSuccessfulBuild'


def get_apixml_dict(job=None, job_id=None, server=DEFAULT_SERVER):
    '''Constructs the Jenkins url with the given job name `job` and job id
    `job_id`, if given and fetches the api/xml for the url.  If job name and
    job id are not given then name and url of all the configured jobs in the
    provided server are returned.
    Returns - The constructed job url and a `dict` containing the api/xml
              data if successful.
    Raises - JenkinsError if it fails to fetch the data or the job is None.'''
    path = ''
    if not job:
        if job_id:
            raise JenkinsError("Error: Job name can't be empty")
        else:
            path = os.path.join('view', "All")
    else:
        path = os.path.join('job', job)

    if job_id:
        path = os.path.join(path, str(job_id))

    job_url = urlunparse([NET_SCHEME, server.strip('/'), path.strip('/'),
                          None, None, None])
    api_url = os.path.join(job_url, API_PYTHON_URL_SUFFIX)
    try:
        data = eval(get_url_contents(api_url))
    except SyntaxError, error:
        raise JenkinsError("Error parsing Jenkins data: %s" % error)
    return (job_url, data)


def get_url_contents(url):
    '''Fetches the contents of `url`.
    Returns - Returns the url contents as a string.
    Raises  - JenkinsError if it fails to fetch the data.'''
    try:
        response = urllib2.urlopen(url)
        return response.read()
    except urllib2.URLError, error:
        raise JenkinsError("Error fetching url contents: %s" % error)


class Jenkins(object):
    '''Class to wrap the api/xml data of all jobs configured in a
    Jenkins server'''
    def __init__(self, server=DEFAULT_SERVER):
        self.server = server
        self.jobs = []
        self.url = ""
        self.data = {}
        self._get_current_data()

    def _get_current_data(self):
        '''Fetches the data from Jenkins server.'''
        (self.url, self.data) = get_apixml_dict(server=self.server)

    def get_jobs(self, force_update=False):
        '''Strips unwanted elements from api/xml data and returns a list of
        job name and its url.  If `force_update` is True this will fetch the
        latest data from the Jenkins server.
        Returns - A list containing the job names and its url.
        Raises - JenkinsError if it fails to fetch the data.'''
        if not self.jobs or force_update:
            self._get_current_data()
            jenkins_jobs = self.data.get('jobs')
            if jenkins_jobs:
                jobs = []
                for job in jenkins_jobs:
                    item = {}
                    url = job.get('url')
                    name = job.get('name')
                    if url and name:
                        # Store only the valid data
                        item['url'] = url
                        item['name'] = name
                        jobs.append(item)
                self.jobs = jobs
        return self.jobs


class JenkinsError(Exception):
    '''JenkinsError is raised when something goes wrong fetching data
    from Jenkins'''


class JenkinsBuild(object):
    '''Class to wrap the api/xml data of a Jenkins build'''
    def __init__(self, job, job_id=DEFAULT_JOB_ID, server=DEFAULT_SERVER):
        self.job = job
        self.job_id = job_id
        self.server = server
        self.artifact_urls = []
        self.timestamp = None
        (self.url, self.data) = get_apixml_dict(job, job_id=job_id,
                                                server=server)

    def get_artifact_contents(self, url):
        '''Fetches the contents of the given url.  The `url` should be a fully
        qualified url to the artifact.
        Returns - If successful, returns the url contents as string, else None.
        Raises - JenkinsError if it fails.'''
        return get_url_contents(url)

    def get_artifact_urls(self):
        '''Extracts the artifact urls from the api/xml data.
        Can return empty list if artifacts are not found.'''
        if not self.artifact_urls and 'artifacts' in self.data:
            artifacts = self.data.get('artifacts', [])
            if artifacts:
                for artifact in artifacts:
                    relpath = artifact.get('relativePath')
                    if relpath:
                        artifact_url = os.path.join(self.url, 'artifact',
                                                    relpath)
                        self.artifact_urls.append(artifact_url)
        return self.artifact_urls

    def get_build_timestamp(self, epoch=False):
        '''Returns the build start timestamp.  If 'timestamp' is not
        available and `epoch` is set to True, returns the epoch time.
        The epoch time can be used by the 'avoid build' check to proceed with
        new build.'''
        if not self.timestamp:
            timestamp = self.data.get('timestamp')
            if timestamp:
                start_time = str(timestamp)
                if start_time and len(start_time) > 10:
                    # If the timestamp is in milliseconds,
                    # convert it to seconds
                    start_time = start_time[:10]
                self.timestamp = datetime.fromtimestamp(int(start_time))
            elif epoch:
                # If for some reason timestamp is not found in the data
                # assign epoch time to let the avoid build check to proceed.
                timestamp = gmtime(0)
                self.timestamp = datetime(timestamp.tm_year, timestamp.tm_mon,
                                          timestamp.tm_mday)
        return self.timestamp

    def is_triggered_by_user(self):
        '''Returns True if the build was triggered by user else False'''
        actions = self.data.get('actions')
        if actions:
            for action in actions:
                if 'causes' in action.keys():
                    causes = action.get('causes')
                    for cause in causes:
                        if 'userName' in cause.keys():
                            # If the build was triggered by user, causes will
                            # have 2 entries: `shortDescription` & `userName`.
                            # If it was triggered by timer, causes will have
                            # only the `shortDescription`.
                            return True
        return False

    def is_time_lapsed(self, duration=30, check_epoch=False):
        '''Checks the difference between current time and its build timestamp
        in minutes.  If `check_epoch` is set to True, checks the difference
        between current time and epoch time if build timestamp is not available.
        Returns - True if the difference is greater than or equal to `duration`
                  minutes else False.
        Raises - ValueError if `duration` is less than or equal to zero'''
        if duration <= 0:
            raise ValueError('Duration should be a positive integer greater '
                             'then zero.')
        if datetime.now() - self.get_build_timestamp(epoch=check_epoch) >= \
                timedelta(minutes=duration):
            return True
        return False


class JenkinsJob(object):
    '''Class to wrap the api/xml data of a Jenkins job'''
    def __init__(self, job, server=DEFAULT_SERVER):
        self.job = job
        self.server = server
        (self.url, self.data) = get_apixml_dict(job, server=server)

    def get_lastsuccessful_url(self):
        '''Returns the url of the last successful build in this job.
        None if there is no successful build yet.'''
        last_successful_build = self.data.get(DEFAULT_JOB_ID)
        if last_successful_build:
            return last_successful_build.get('url')
        return None

    def get_lastbuild_number(self):
        '''Returns the last build number (running/completed) in this job.'''
        last_build = self.data.get('lastBuild')
        if last_build:
            return last_build.get('number')
        return None
