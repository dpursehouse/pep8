""" Retry decorator with exponential backoff.
"""

import math
import time


def retry(exception, tries, delay=3, backoff=2):
    '''Calls a function which may throw an exception. On an exception, waits,
    and tries the function again. On repeated failures, waits longer between
    each successive attempt. If the number of attempts runs out, gives up and
    raises the last exception that was given by the decorated function.

    Parameters:
    `exception` sets the type of exception to be caught by the decorator.
    `delay` sets the initial delay in seconds. Must be greater than 0.
    `backoff` sets the factor by which the `delay` should lengthen after each
    failure. Must be greater than 1, or else it isn't really a backoff.
    `tries` sets the number of times to attempt calling the function. Must be
    at least 1, but ideally should be at least 2.
    '''

    if not exception:
        raise ValueError("exception must be specified")

    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")

    tries = math.floor(tries)
    if tries < 1:
        raise ValueError("tries must be at least 1")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")

    def deco_retry(method):
        '''  @retry(arg[, ...]) -> true decorator
        '''
        def f_retry(*args, **kwargs):
            ''' true decorator -> decorated function
            '''
            mtries, mdelay = tries, delay  # make mutable

            while mtries > 0:
                try:
                    return method(*args, **kwargs)

                except exception, last_exception:
                    # Consume an attempt
                    mtries -= 1

                    # Only need to wait when more tries are remaining,
                    # otherwise we just delay raising the exception.
                    if mtries > 0:
                        time.sleep(mdelay)

                        # Increment delay
                        mdelay *= backoff

            # Last caught exception will be raised to the caller
            # when there are no more tries remaining
            raise last_exception

        return f_retry
    return deco_retry
