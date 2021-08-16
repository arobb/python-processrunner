# -*- coding: utf-8 -*-
"""
Representation of content for a queue where the values may exceed the native
pipe size.
"""
import os
import sys
import tempfile
from codecs import getreader
from enum import Enum

from kitchen.text.converters import to_bytes

from .classtemplate import PRTemplate
from .kitchenpatch import getwriter
from .timer import Timer

# Py2 uses "file" as the base class for IO
# Used for an isinstance comparison
if sys.version_info[0] == 3:
    from io import IOBase as file


class TYPES(Enum):
    """Enum indicating whether a wrapped item is in memory or a file"""
    DIRECT = 0
    FILE = 1


class ContentWrapper(PRTemplate):
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

    # Need to figure out a way to do this automatically
    THRESHOLD = 2**14  # 2**14 = 16,384

    def __getattr__(self, attr):
        """When necessary pull the 'value' from a buffer file"""
        log = object.__getattribute__(self, "_log")

        # pylint: disable=no-else-return
        # The 'else' can be hit, so it is not superfluous
        if attr == "value" \
                and object.__getattribute__(self, "type") == TYPES.FILE:
            log.debug("Pulling value from buffer file")
            return self._get_value_from_file()
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
                # pylint: disable=consider-using-with
                # We explicitly do not want to close the tempfile automatically
                object.__setattr__(self, "type", TYPES.FILE)
                object.__setattr__(self, "location_handle",
                                   tempfile.NamedTemporaryFile(delete=False))
                handle = object.__getattribute__(self, "location_handle")
                object.__setattr__(self, "location_name", handle.name)
                writer = getwriter("utf-8")(handle)

                self._log.info("Writing value into buffer file %s",
                               handle.name)
                stopwatch = Timer()
                writer.write(val)
                writer.flush()
                lap = stopwatch.lap()
                self._log.info("Finished writing value into buffer file in "
                               "%.1f seconds", lap)

        # Not assigning to self.value
        else:
            object.__setattr__(self, attr, val)

    def __getstate__(self):
        """Being Pickled"""
        self._log.debug("Being pickled")

        # Close the buffer file if needed
        if isinstance(self.location_handle, file):
            self.location_handle.close()

        state = self.__dict__.copy()
        del state['location_handle']
        del state['_log']  # Delete the logger instance

        # Prevent __del__ from deleting the buffer file
        # Needs to come after we've created the state copy so
        # this doesn't persist after un-pickling
        self.being_serialized = True

        return state

    def __setstate__(self, state):
        """Being un-Pickled, need to restore state"""

        self.__dict__.update(state)
        self.location_handle = None

        # Reestablish the logger
        self._initialize_logging(__name__)
        self._log.debug("Being un-pickled")

        if self.location_name is not None:
            # pylint: disable=consider-using-with
            # We explicitly do not want to close the file automatically
            self.location_handle = open(self.location_name, "r+b")

    def __del__(self):
        """When used, close any open file handles on object destruction"""
        self._log.debug("Object being deleted")
        if isinstance(self.location_handle, file):
            self.location_handle.close()

        # Delete any files on disk
        if self.location_name is not None and not self.being_serialized:
            os.remove(self.location_name)

    def __len__(self):
        return len(self.value)

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, self.value)

    def __str__(self):
        return self.value

    def __eq__(self, other):
        return self.value == other

    def __init__(self, val):
        self._log = None
        self._initialize_logging(__name__)

        self.type = TYPES.DIRECT

        # Used only if this is stored in a file
        self.location_handle = None
        self.location_name = None
        self.being_serialized = False

        # Store the initial value
        self.value = val

    def _create_buffer(self):
        pass

    def _get_value_from_file(self):
        handle = object.__getattribute__(self, "location_handle")
        reader = getreader("utf-8")(handle)
        handle.seek(0)

        stopwatch = Timer()
        content = reader.read()
        lap = stopwatch.lap()
        self._log.info("Finished reading value into buffer file in %.1f "
                       "seconds", lap)

        return content
