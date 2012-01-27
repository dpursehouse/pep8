""" Classes for handling git commit messages.
"""

import os
import re

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


class CommitMessageError(Exception):
    '''CommitMessageError is raised when there is an error
    in the formatting of the commit message header or body,
    or when an error occurs in one of the class methods.
    '''


class CommitMessageAuthor:
    '''Wrapper for the author/committer lines from the commit
    message header.
    '''

    def __init__(self, data):
        '''Initialise the class with the type, name, email and
        timestamp from the header in `data`.
        Raise CommitMessageError if the content of `data` does not
        match the expected pattern.
        '''
        pattern = "^(author|committer) (.*) <(.*@.*)> .*$"
        match = re.match(pattern, data)
        if match:
            self.type = match.group(1)
            self.name = match.group(2)
            self.email = match.group(3)
        else:
            raise CommitMessageError("Invalid author or committer header")


class CommitMessage:
    '''Wrapper for the commit message data that is output from
    the "git cat-file -p <object>" command.
    '''

    def get_fixed_issues(self):
        '''Get the fixed issues that are listed in the commit message.
        Return a list of issues, or an empty list if no issues were found.
        Raise CommitMessageError if any error occurs.
        '''
        try:
            result = processes.run_cmd(_find_query_script(),
                                       "--show",
                                       "--quiet",
                                       input=self.message)
            rawlist = str(result[1])

            # The output is one issue per line, but there may be
            # leading and trailing whitespace. Clean this up.
            return [s.strip() for s in rawlist.splitlines()]
        except processes.ChildExecutionError, err:
            raise CommitMessageError("Error extracting issues: %s" % err)

    def __init__(self, data):
        '''Initialize the class with the commit message in `data`.
        Raise CommitMessageError if the message header or body
        is badly formatted.
        '''

        self.committer = None
        self.author = None

        # Extract the header
        end_of_header = data.find('\n\n')
        if end_of_header < 0:
            raise CommitMessageError("Bad commit message header")
        header = data[0:end_of_header]

        # Parse the contents of the header.
        for line in header.split('\n'):
            if line.startswith("author"):
                if self.author:
                    raise CommitMessageError("Multiple author headers")
                self.author = CommitMessageAuthor(line)
            elif line.startswith("committer"):
                if self.committer:
                    raise CommitMessageError("Multiple committer headers")
                self.committer = CommitMessageAuthor(line)

        # Make sure author and committer have been found.
        if not self.author:
            raise CommitMessageError("author not found in header.")
        if not self.committer:
            raise CommitMessageError("committer not found in header.")

        # Get the mesage body.  The message body is separated from
        # the header by two newlines.
        message_body_position = data.find('\n\n')
        if message_body_position < 0:
            raise CommitMessageError("No message body")
        message_body = data[message_body_position + 2:].rstrip()

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
