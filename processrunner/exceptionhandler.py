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


class ProcessAlreadyStarted(Exception):
    """Raise if _Command.start is called after the process is started"""
    def __init__(self, value=""):
        """Arguments must be option to prevent triggering
        https://bugs.python.org/issue15440 when raised in _Command"""
        self.errno = 3
        self.value = value

    def __str__(self):
        return repr(self.value)


class ProcessNotStarted(Exception):
    """Raise if _Command.start hasn't been called, but a method has been
    called that depends on the target process running.
    """
    def __init__(self, value=""):
        """Arguments must be option to prevent triggering
        https://bugs.python.org/issue15440 when raised in _Command"""
        self.errno = 4
        self.value = value

    def __str__(self):
        return repr(self.value)


class HandleAlreadySet(Exception):
    """Raise if a _PrPipe has already been configured with a pipe handle"""
    def __init__(self, value=""):
        """Arguments must be option to prevent triggering
        https://bugs.python.org/issue15440 when raised in _Command"""
        self.errno = 5
        self.value = value

    def __str__(self):
        return repr(self.value)


class HandleNotSet(Exception):
    """Raise if a _PrPipe has not been configured with a pipe handle, but
    a call requires one have been set
    """
    def __init__(self, value=""):
        """Arguments must be option to prevent triggering
        https://bugs.python.org/issue15440 when raised in _Command"""
        self.errno = 6
        self.value = value

    def __str__(self):
        return repr(self.value)


class Timeout(Exception):
    """Raise if ProcessRunner.wait times out
    """
    def __init__(self, value=""):
        """Arguments must be option to prevent triggering
        https://bugs.python.org/issue15440 when raised in _Command"""
        self.errno = 7
        self.value = value

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
