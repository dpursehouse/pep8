""" Classes for handling git commit messages.
"""

import os

import processes


# Filename of the query script
_QUERY_SCRIPT = "dmsquery"

# This file's location
_MY_DIR = os.path.abspath(os.path.dirname(__file__))


def _find_query_script():
    '''Attempt to find the script that will be used to parse the commit
    message for fixed issues.
    Return the absolute path to the script.
    Raise CommitMessageError if the script could not be found.
    '''
    query_file = os.path.join(_MY_DIR, _QUERY_SCRIPT)
    if os.path.exists(query_file):
        return query_file

    raise CommitMessageError("Could not find %s" % _QUERY_SCRIPT)


def _sanitise_string(string):
    '''Return `string` with all non-ascii characters removed.
    '''
    return "".join(i for i in string if ord(i) < 128)


class CommitMessageError(Exception):
    '''CommitMessageError is raised when there is an error
    when performing an operation on the commit message.
    '''


class CommitMessage(object):
    '''Wrapper for the commit message.
    '''

    def __init__(self, message_body):
        '''Initialize the class with the commit message in `message_body`.
        '''

        # Split the body into subject and message parts.  The message
        # is separated from the subject by two newlines.
        length_of_body = len(message_body)
        end_of_subject = message_body.find('\n\n')

        # If two newlines are not found, it means there is no message,
        # only a subject.  The subject can however be multiple lines.
        if end_of_subject < 0:
            self.subject = message_body
            self.message = ""
        else:
            self.subject = message_body[0:end_of_subject]
            self.message = message_body[end_of_subject + 2:length_of_body]

        # Strip trailing whitespace and newlines off the subject and message.
        self.subject = self.subject.rstrip()
        self.message = self.message.rstrip()

    def get_fixed_issues(self):
        '''Get the fixed issues that are listed in the commit message.
        Return a list of issues, or an empty list if no issues were found.
        Raise CommitMessageError if any error occurs.
        '''
        try:
            result = processes.run_cmd(_find_query_script(),
                                       "--show",
                                       "--quiet",
                                       input=_sanitise_string(self.message))
            rawlist = str(result[1])

            # The output is one issue per line, but there may be
            # leading and trailing whitespace. Clean this up.
            return [s.strip() for s in rawlist.splitlines()]
        except processes.ChildExecutionError, err:
            raise CommitMessageError("Error extracting issues: %s" % err)
