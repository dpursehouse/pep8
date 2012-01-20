#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

import retry


# Number of times to try the "failing" test function.
_TRIES = 3

# Value to be returned by the "successful" test function.
_SUCCESS = 123


class DummyException(Exception):
    """Dummy exception class.
    """


class TestRetryDecorator(unittest.TestCase):
    """Test that the retry decorator behaves correctly.
    """

    _try_count = 0

    @retry.retry(DummyException, tries=_TRIES)
    def fail(self, e):
        self._try_count += 1
        raise e

    @retry.retry(Exception, tries=_TRIES, backoff=2, delay=1)
    def success(self):
        return _SUCCESS

    def test_fail(self):
        """Tests that the retry decorator works correctly when the
        called method is not successful and raises the expected
        exception.
        """
        self._try_count = 0
        self.assertRaises(DummyException, self.fail, DummyException("Fail"))
        self.assertEquals(self._try_count, _TRIES)

    def test_fail_different_exception(self):
        """Tests that the retry decorator works correctly when the
        called method is not successful and does not raise the
        expected exception.
        """
        self._try_count = 0
        self.assertRaises(Exception, self.fail, Exception("Fail"))
        self.assertEquals(self._try_count, 1)

    def test_success(self):
        """Tests that the retry decorator works correctly when the
        called method is successful.
        """
        self.assertEquals(self.success(), _SUCCESS)

    def test_invalid_delay(self):
        """Tests that the retry decorator raises ValueError when an
        invalid `delay` parameter is given.
        """
        try:
            @retry.retry(Exception, tries=_TRIES, delay=-1)
            def decorated():
                self.fail("retry decorator did not raise exception")
        except ValueError:
            pass

    def test_invalid_tries(self):
        """Tests that the retry decorator raises ValueError when an
        invalid `tries` parameter is given.
        """
        try:
            @retry.retry(Exception, tries=-1)
            def decorated():
                self.fail("retry decorator did not raise exception")
        except ValueError:
            pass

        try:
            @retry.retry(Exception, tries=0)
            def decorated():
                self.fail("retry decorator did not raise exception")
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
            @retry.retry(Exception, tries=_TRIES, backoff=-1)
            def decorated():
                # If it reaches this point, something went wrong.
                # Force a test failure.
                self.fail("retry decorator did not raise exception")
        except ValueError:
            # Expected result, continue to the next test.
            pass

        try:
            @retry.retry(Exception, tries=_TRIES, backoff=0)
            def decorated():
                self.fail("retry decorator did not raise exception")
        except ValueError:
            pass

        try:
            @retry.retry(Exception, tries=_TRIES, backoff=1)
            def decorated():
                self.fail("retry decorator did not raise exception")
        except ValueError:
            pass

if __name__ == '__main__':
    unittest.main()
