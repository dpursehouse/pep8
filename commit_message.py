import re

import processes


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
        m = re.match(pattern, data)
        if m:
            self.type = m.group(1)
            self.name = m.group(2)
            self.email = m.group(3)
        else:
            raise CommitMessageError("Invalid author or committer header")


class CommitMessage:
    '''Wrapper for the commit message data that is output from
    the "git cat-file -p <object>" command.
    '''

    def get_fixed_issues(self):
        '''Get a list of fixed issues that are recorded in the commit message.
        Return list of issues, or empty list if no issues were found.
        Raise CommitMessageError if any error occurs.
        '''
        try:
            errcode, rawlist, err = processes.run_cmd("./dmsquery", "--show",
                                                      input=self.message)

            if rawlist == "No DMS Issues found":
                issuelist = []
            else:
                # The output is one issue per line, but there may be
                # leading and trailing whitespace. Clean this up.
                issuelist = [s.strip() for s in rawlist.splitlines()]
        except:
            raise CommitMessageError("Error extracting issue information")

        return issuelist

    def __init__(self, data):
        '''Initialize the class with the commit mesage in `data`.
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
