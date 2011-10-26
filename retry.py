import math
import time


# Retry decorator with exponential backoff
def retry(exception, tries, delay=3, backoff=2):
    """Calls a function which may throw an exception. On an exception, waits,
    and tries the function again. On repeated failures, waits longer between
    each successive attempt. If the number of attempts runs out, gives up and
    raises the last exception that was given by the decorated function.

    Parameters:
    `exception` sets the type of exception to be caught by the decorator.
    `delay` sets the initial delay in seconds. Must be greater than 0.
    `backoff` sets the factor by which the `delay` should lengthen after each
    failure. Must be greater than 1, or else it isn't really a backoff.
    `tries` sets the number of reties to attempt. Must be at least 0.
    """

    if not exception:
        raise ValueError("exception must be specified")

    if backoff <= 1:
        raise ValueError("backoff must be greater than 1")

    tries = math.floor(tries)
    if tries < 0:
        raise ValueError("tries must be 0 or greater")

    if delay <= 0:
        raise ValueError("delay must be greater than 0")

    def deco_retry(f):
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay  # make mutable

            while mtries > 0:
                try:
                    return f(*args, **kwargs)

                except exception, e:
                    mtries -= 1         # consume an attempt
                    time.sleep(mdelay)  # wait...
                    mdelay *= backoff   # make future wait longer
                    last_exception = e

            raise last_exception

        return f_retry  # true decorator -> decorated function
    return deco_retry  # @retry(arg[, ...]) -> true decorator
