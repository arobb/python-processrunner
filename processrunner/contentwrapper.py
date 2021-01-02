# -*- coding: utf-8 -*-
"""
Representation of content for a queue where the values may exceed the native
pipe size.
"""
import os
import sys
import tempfile

from codecs import getreader

from .enum import enum
from .kitchenpatch import getwriter
from kitchen.text.converters import to_bytes

# Py2 uses "file" as the base class for IO
# Used for an isinstance comparison
if sys.version_info[0] == 3:
    from io import IOBase as file


class ContentWrapper(object):
    """
    Representation of content for a queue where the values may exceed the
    native pipe size.

    Store data with
        cw = ContentWrapper("My text data")
        cw.value = "Updated text data"

    Access data with
        print("My data: {}".format(cw.value))

    TODO: Manage value updates that cross THRESHOLD
    """
    TYPES = enum(
        'DIRECT',
        'FILE')

    # Need to figure out a way to do this automatically
    THRESHOLD = 2**14  # 2**14 = 16,384

    def __getattr__(self, attr):
        """When necessary pull the 'value' from a buffer file"""
        if attr == "value" \
                and object.__getattribute__(self, "type") == \
                ContentWrapper.TYPES.FILE:
            return self._getValueFromFile()
        else:
            return object.__getattribute__(self, attr)

    def __setattr__(self, attr, val):
        """When necessary, save the 'value' to a buffer file"""
        if attr == "value":
            # Within the threshold size limit
            if len(to_bytes(val)) < ContentWrapper.THRESHOLD:
                object.__setattr__(self, attr, val)

            # Larger than what a queue value can hold
            # due to pipe limits, store value in a temp file
            else:
                object.__setattr__(self, "type", ContentWrapper.TYPES.FILE)
                object.__setattr__(self, "locationHandle",
                                   tempfile.NamedTemporaryFile(delete=False))
                handle = object.__getattribute__(self, "locationHandle")
                object.__setattr__(self, "locationName", handle.name)
                writer = getwriter("utf-8")(handle)
                writer.write(val)
                writer.flush()

        # Not assigning to self.value
        else:
            object.__setattr__(self, attr, val)

    def __getstate__(self):
        """Being Pickled"""
        if isinstance(self.locationHandle, file):
            self.locationHandle.close()

        state = self.__dict__.copy()
        del state['locationHandle']

        # Prevent __del__ from deleting the buffer file
        # Needs to come after we've created the state copy so
        # this doesn't persist after un-pickling
        self.beingSerialized = True

        return state

    def __setstate__(self, state):
        """Being un-Pickled, need to restore state"""
        self.__dict__.update(state)
        self.locationHandle = None

        if self.locationName is not None:
            self.locationHandle = open(self.locationName, "r+b")

    def __del__(self):
        """When used, close any open file handles on object destruction"""
        if isinstance(self.locationHandle, file):
            self.locationHandle.close()

        # Delete any files on disk
        if self.locationName is not None and not self.beingSerialized:
            os.remove(self.locationName)

    def __len__(self):
        return len(self.value)

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, self.value)

    def __str__(self):
        return self.value

    def __eq__(self, other):
        return self.value == other

    def __init__(self, val):
        self.type = ContentWrapper.TYPES.DIRECT

        # Used only if this is stored in a file
        self.locationHandle = None
        self.locationName = None
        self.beingSerialized = False

        # Store the initial value
        self.value = val

    def _createBuffer(self):
        pass

    def _getValueFromFile(self):
        handle = object.__getattribute__(self, "locationHandle")
        reader = getreader("utf-8")(handle)
        handle.seek(0)
        return reader.read()
