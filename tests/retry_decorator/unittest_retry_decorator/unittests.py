#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

import retry


# Number of times to retry the "failing" test function.
_RETRIES = 3

# Value to be returned by the "successful" test function.
_SUCCESS = 123


class TestRetryDecorator(unittest.TestCase):
    """Test that the retry decorator behaves correctly.
    """

    _retry_count = 0

    @retry.retry(Exception, tries=_RETRIES)
    def fail_method(self):
        self._retry_count += 1
        raise Exception("Fail")

    @retry.retry(Exception, tries=_RETRIES, backoff=2, delay=1)
    def success_method(self):
        return _SUCCESS

    def test_fail(self):
        """Tests that the retry decorator works correctly when the
        called method is not successful.
        """
        self._retry_count = 0
        self.assertRaises(Exception, self.fail_method)
        self.assertEquals(self._retry_count, _RETRIES)

    def test_success(self):
        """Tests that the retry decorator works correctly when the
        called method is successful.
        """
        self.assertEquals(self.success_method(), _SUCCESS)

    def test_invalid_delay(self):
        """Tests that the retry decorator raises ValueError when an
        invalid `delay` parameter is given.
        """
        try:
            @retry.retry(Exception, tries=_RETRIES, delay=-1)
            def decorated():
                self.assertTrue(False)
        except ValueError:
            pass

    def test_invalid_tries(self):
        """Tests that the retry decorator raises ValueError when an
        invalid `tries` parameter is given.
        """
        try:
            @retry.retry(Exception, tries=-1)
            def decorated():
                self.assertTrue(False)
        except ValueError:
            pass

    def test_invalid_backoff(self):
        """Tests that the retry decorator raises ValueError when an
        invalid `backoff` parameter is given.
        """

        # The standard pattern of calling self.assertRaises does not
        # seem to work properly when calling a decorator that raises
        # an exception.  In the tests below, the exceptions are
        # manually caught.
        try:
            @retry.retry(Exception, tries=_RETRIES, backoff=-1)
            def decorated():
                # If it reaches this point, something went wrong.
                # Force a test failure.
                self.assertTrue(False)
        except ValueError:
            # Expected result, continue to the next test.
            pass

        try:
            @retry.retry(Exception, tries=_RETRIES, backoff=0)
            def decorated():
                self.assertTrue(False)
        except ValueError:
            pass

        try:
            @retry.retry(Exception, tries=_RETRIES, backoff=1)
            def decorated():
                self.assertTrue(False)
        except ValueError:
            pass

if __name__ == '__main__':
    unittest.main()
