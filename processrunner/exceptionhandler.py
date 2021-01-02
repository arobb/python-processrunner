# -*- coding: utf-8 -*-
"""
Exception management classes
"""
from __future__ import unicode_literals
import sys
import traceback

import logging


class SIGINTException(Exception):
    """Represents a ctrl-c interrupt"""
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class CommandNotFound(OSError):
    """Exception in case the command to execute isn't available"""
    def __init__(self, value, command):
        self.errno = 2
        self.value = value
        self.command = command

    def __str__(self):
        return repr(self.value)


class ExceptionHandler(Exception):
    """Exception management

    TODO: Add additional detail
    """
    def __repr__(self):
        return self.errmsg

    def __str__(self):
        return self.errmsg

    def __init__(self, error, message=None):
        self.exc_type, self.exc_obj, self.exc_tb = sys.exc_info()
        # fname = os.path.split(self.exc_tb.tb_frame.f_code.co_filename)[1]
        self.err_type = type(error).__name__
        self.error_text = str(error)

        log = logging.getLogger(__name__)
        log.addHandler(logging.NullHandler())

        if message is not None:
            log.error(message)

        template = "An exception of type {0} occurred. Error message:\n{1}"
        self.errmsg = template.format(self.err_type, self.error_text)
        self.errmsg += "\n"
        log.error(self.errmsg)

        errargmsg = "{0} {1} arguments:\n{2!r}".format(self.err_type,
                                                       type(error).__name__,
                                                       error.args)
        errargmsg += "\n"
        log.error(errargmsg)

        tbmsg = self.err_type+" traceback (most recent call last):"
        log.error(tbmsg)
        traceback.print_tb(self.exc_tb)
