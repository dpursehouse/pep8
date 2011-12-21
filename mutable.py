class Immutable(object):
    """An immutable class.

    Make the attributes immutable. Overriding only the
    __setattr__ and __delattr__ functions.

    Loop Hole: Still be able to modify varibles inside the
    attributes.
    e.g:
        arg = {}
        arg.update({key: value}) -- throws exception
        arg[key] = value -- no exception

    """
    def __init__(self):
        """Initialize function.

        Initializes base class and sets '_mutable' to False.

        """
        super(Immutable, self).__init__()
        self._mutable = False

    def __setattr__(self, name, value):
        """Overriding '__setattr__' function.

        Overriding the default '__setattr__ function to set the
        attribute value only if :
            - attribute name is '_mutable' or
            - object instance is mutable.

        """
        if name == '_mutable' or self._mutable:
            super(Immutable, self).__setattr__(name, value)
        else:
            raise TypeError("Can't modify immutable instance")

    def __delattr__(self, name):
        """Overriding '__delattr__' function.

        Delete attribute only if the object instance is mutable.

        """
        if self._mutable:
            super(Immutable, self).__delattr__(name)
        else:
            raise TypeError("Can't modify immutable instance")

    def set_mutable(self, value):
        """Sets the object as mutable/immutable.

        With respect to the value passed either True or False,
        class object is made mutable or immutable.

        """
        self._mutable = value


def make_mutable(f):
    """Decorator to make function mutable. """
    def func(self, *args, **kwargs):
        if hasattr(self, '_mutable'):
            old_mutable = self._mutable
            try:
                self._mutable = True
                res = f(self, *args, **kwargs)
            finally:
                self._mutable = old_mutable
        else:
            res = f(self, *args, **kwargs)
        return res
    return func


def require_mutable(f):
    """Decorator to check whether function is mutable or not."""
    def func(self, *args, **kwargs):
        if hasattr(self, '_mutable') and not self._mutable:
            raise TypeError("Can't modify immutable instance")
        return f(self, *args, **kwargs)
    return func
