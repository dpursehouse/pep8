import re


class IncludeExcludeMatcher():
    """Maintains two lists of regular expression patterns for matching
    strings against. Input strings are matched against all patterns in
    the list of inclusion patterns and thereafter all patterns in the
    exclusion pattern list. An input string must be matched by at
    least one of the patterns in the inclusion list and must not be
    matched by any of the patterns in the exclusion list (i.e. the
    exclusion list has precedence).
    """

    def __init__(self, include_patterns, exclude_patterns):
        """Initialize an IncludeExcludeFilter object with the given
        initial values for the inclusion and exclusion pattern
        lists. Each initial value may be None, in which case it counts
        as an empty list.
        """

        if include_patterns is not None:
            self.include_patterns = include_patterns
        else:
            self.include_patterns = []
        if exclude_patterns is not None:
            self.exclude_patterns = exclude_patterns
        else:
            self.exclude_patterns = []

    def match(self, string):
        """Match `string` against the inclusion and exclusion patterns
        and return True if there's a match and False otherwise. This
        function is suitable to pass to the filter() function.
        """

        matches = False
        for regexp in self.include_patterns:
            if re.search(regexp, string):
                matches = True
                break
        for regexp in self.exclude_patterns:
            if re.search(regexp, string):
                # Could return immediately here, but doing the
                # assignment for symmetry.
                matches = False
                break
        return matches
