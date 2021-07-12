# -*- coding: utf-8 -*-
"""
Representation of content for a queue where the values may exceed the native
pipe size.
"""
import logging
import os
import sys
import tempfile

from codecs import getreader

from .enum import enum
from .kitchenpatch import getwriter
from kitchen.text.converters import to_bytes
from .timer import Timer

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
        log = object.__getattribute__(self, "_log")

        if attr == "value" \
                and object.__getattribute__(self, "type") == \
                ContentWrapper.TYPES.FILE:
            log.debug("Pulling value from buffer file")
            return self._getValueFromFile()
        else:
            log.debug("Pulling value from memory")
            return object.__getattribute__(self, attr)

    def __setattr__(self, attr, val):
        """When necessary, save the 'value' to a buffer file"""
        if attr == "value":
            # Within the threshold size limit
            if len(to_bytes(val)) < ContentWrapper.THRESHOLD:
                self._log.debug("Storing value to memory")
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

                self._log.info("Writing value into buffer file {}".format(
                    handle.name
                ))
                stopwatch = Timer()
                writer.write(val)
                writer.flush()
                lap = stopwatch.lap()
                self._log.info("Finished writing value into buffer file in {}"
                               " seconds".format(lap / 1000))

        # Not assigning to self.value
        else:
            object.__setattr__(self, attr, val)

    def __getstate__(self):
        """Being Pickled"""
        self._log.debug("Being pickled")

        # Close the buffer file if needed
        if isinstance(self.locationHandle, file):
            self.locationHandle.close()

        state = self.__dict__.copy()
        del state['locationHandle']
        del state['_log']  # Delete the logger instance

        # Prevent __del__ from deleting the buffer file
        # Needs to come after we've created the state copy so
        # this doesn't persist after un-pickling
        self.beingSerialized = True

        return state

    def __setstate__(self, state):
        """Being un-Pickled, need to restore state"""

        self.__dict__.update(state)
        self.locationHandle = None

        # Reestablish the logger
        self._initializeLogging()
        self._log.debug("Being un-pickled")

        if self.locationName is not None:
            self.locationHandle = open(self.locationName, "r+b")

    def __del__(self):
        """When used, close any open file handles on object destruction"""
        self._log.debug("Object being deleted")
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
        self._initializeLogging()

        self.type = ContentWrapper.TYPES.DIRECT

        # Used only if this is stored in a file
        self.locationHandle = None
        self.locationName = None
        self.beingSerialized = False

        # Store the initial value
        self.value = val

    def _initializeLogging(self):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Logging
        self._log = logging.getLogger(__name__)
        self.addLoggingHandler(logging.NullHandler())

    def addLoggingHandler(self, handler):
        self._log.addHandler(handler)

    def _createBuffer(self):
        pass

    def _getValueFromFile(self):
        handle = object.__getattribute__(self, "locationHandle")
        reader = getreader("utf-8")(handle)
        handle.seek(0)

        stopwatch = Timer()
        content = reader.read()
        lap = stopwatch.lap()
        self._log.info("Finished reading value into buffer file in {}"
                       " seconds".format(lap / 1000))

        return content
