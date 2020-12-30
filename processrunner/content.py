# -*- coding: utf-8 -*-
"""
Representation of content for a queue where the values may exceed the native pipe size.
"""
import tempfile

class Content(object):
    DIRECT = 0
    FILE = 1

    # Need to figure out a way to do this automatically
    THRESHOLD = 2**14  # 2**14 = 16,384

    def __get__(self, instance, owner):
        if instance == "value" and self.type == Content.FILE:
            return file.locationHandle.read()
        else:
            return getattr(self, instance)

    def __set__(self, instance, val):
        if instance == "value":
            # Within the threshold size limit
            if len(value.__repr__) < Content.THRESHOLD:
                self.value = val

            # Larger than what a queue value can hold
            # due to pipe limits, store value in a temp file
            else:
                self.type = Content.FILE
                self.locationHandle = tempfile.SpooledTemporaryFile()
                self.locationHandle.write(val)

        # Not assigning to self.value
        else:
            setattr(self, instance, val)

    def __len__(self):
        return len(self.value)

    def __repr__(self):
        return self.value

    def __init__(self, val):
        self.type = Content.DIRECT
        self.value = val

        # Used only if this is stored in a file
        self.locationHandle = None