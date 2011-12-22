#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest

from mutable import *


class ImmutableChild(Immutable):
    """Inherit the Immutable class

    Creating separate class because 'TestRetryDecorator' class
    inherit 'TestCase' from 'unittest' and internally sets
    the current module name as test method name, which will
    fail as the class is immutable by default.

    """
    def __init__(self):
        """Initialize function.

        Initialize the 'Immutable' base class.

        """
        super(ImmutableChild, self).__init__()
        self.initialize_attribute()

    @make_mutable
    def initialize_attribute(self):
        """Initialize the instance attribute."""
        self._attribute = 0

    @make_mutable
    def check_make_mutable(self):
        """Test 'make_mutable' decorator.

        By default the instance attributes are immutable.
        'make_mutable' decorator make the class temporarily
        mutable and it is possible to set attribute value.

        """
        self._attribute = 1
        return True

    @require_mutable
    def check_require_mutable(self):
        """Test 'require_mutable' decorator.

        Raises 'TypeError' if the class in immutable. Else
        it is possible to assign value to the attribute.

        """
        self._attribute = 2
        return True

    def set_attribute(self, value):
        """Sets the attribute value in 'ImmutableChild' class"""
        self._attribute = value
        return True


class TestRetryDecorator(unittest.TestCase):
    """Test that the mutable decorator behaves correctly."""

    def setUp(self):
        """Creates an instance of 'ImmutableChild' class."""
        self._handler = ImmutableChild()

    def test_immutable_by_default(self):
        """Check whether the class is immutable by default."""
        self.assertRaises(TypeError, self._handler.set_attribute, 1)

    def test_set_attribute(self):
        """Test 'set_attribute' function

        'set_attribute' raises 'TypeError' when class is immutable and
        if class is mutable, function set the attribute value and
        returns 'True'.

        """
        self._handler.set_mutable(False)
        self.assertRaises(TypeError, self._handler.set_attribute, 1)
        self._handler.set_mutable(True)
        self.assertEquals(self._handler.set_attribute(2), True)
        self._handler.set_mutable(False)

    def test_make_mutable(self):
        """Test 'make_mutable' decorator.

        Check whether the funciton is made mutable by
        'make_mutable' decorator.

        """
        self.assertEquals(self._handler.check_make_mutable(), True)

    def test_require_mutable(self):
        """Test 'require_mutable' decorator.

        Check whether the mutable checking done by
        'require_mutable' is working properly.

        """
        self._handler.set_mutable(False)
        self.assertRaises(TypeError, self._handler.check_require_mutable)
        self._handler.set_mutable(True)
        self.assertEquals(self._handler.check_require_mutable(), True)
        self._handler.set_mutable(False)


if __name__ == '__main__':
    unittest.main()
