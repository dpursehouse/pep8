'''Classes and helper methods to access Jenkins data'''

from datetime import datetime, timedelta
from time import gmtime
import os
import urllib2
from urlparse import urlparse, urlunparse

# Suffix part of the api/xml url in python format
NET_SCHEME = 'http'
DEFAULT_SERVER = 'android-ci.sonyericsson.net'
API_PYTHON_URL_SUFFIX = 'api/python?depth=0'
DEFAULT_JOB_ID = 'lastSuccessfulBuild'


def get_apixml_dict(job, job_id=None, server=DEFAULT_SERVER):
    '''Constructs the Jenkins url with the given job name `job` and job id
    `job_id` and fetches the api/xml for the url.
    Returns - The constructed job url and a `dict` containing the api/xml
              data if successful.
    Raises - JenkinsError if it fails to fetch the data or the job is None.'''
    if not job:
        raise JenkinsError("Error: Job name can't be empty")

    path = os.path.join('job', job)
    if job_id:
        path = os.path.join(path, str(job_id))

    job_url = urlunparse([NET_SCHEME, server.strip('/'), path.strip('/'),
                          None, None, None])
    api_url = os.path.join(job_url, API_PYTHON_URL_SUFFIX)
    try:
        response = urllib2.urlopen(api_url)
        data = eval(response.read())
    except urllib2.URLError, e:
        raise JenkinsError("Error fetching api/xml: %s" % e)
    except SyntaxError, e:
        raise JenkinsError("Error parsing Jenkins data: %s" % e)
    return (job_url, data)


def get_url_contents(url):
    '''Fetches the contents of `url`.
    Returns - Returns the url contents as a string.
    Raises  - JenkinsError if it fails to fetch the data.'''
    try:
        response = urllib2.urlopen(url)
        return response.read()
    except urllib2.URLError, e:
        raise JenkinsError("Error fetching url contents: %s" % e)


class JenkinsError(Exception):
    ''' JenkinsError is raised when something goes wrong fetching data
    from Jenkins'''


class JenkinsBuild:
    ''' Class to wrap the api/xml data of a Jenkins build '''
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
            t = self.data.get('timestamp')
            if t:
                start_time = str(t)
                if start_time and len(start_time) > 10:
                    # If the timestamp is in milliseconds,
                    # convert it to seconds
                    start_time = start_time[:10]
                self.timestamp = datetime.fromtimestamp(int(start_time))
            elif epoch:
                # If for some reason timestamp is not found in the data
                # assign epoch time to let the avoid build check to proceed.
                t = gmtime(0)
                self.timestamp = datetime(t.tm_year, t.tm_mon, t.tm_mday)
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
            raise ValueError('Duration should be a positive integer greater ' \
                             'then zero.')
        if datetime.now() - self.get_build_timestamp(epoch=check_epoch) >= \
                timedelta(minutes=duration):
            return True
        return False


class JenkinsJob:
    ''' Class to wrap the api/xml data of a Jenkins job '''
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
