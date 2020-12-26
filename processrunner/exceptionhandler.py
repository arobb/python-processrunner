# -*- coding: utf-8 -*-
import os
import sys
import traceback

import logging


class SIGINTException(Exception):
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


def ExceptionHandler(error, message=None):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    err_type = type(error).__name__
    error_text = str(error)

    log = logging.getLogger(__name__)
    log.addHandler(logging.NullHandler())

    if message is not None:
        log.error(message)

    template = "An exception of type {0} occurred. Error message:\n{1}"
    errmsg  = template.format(err_type, error_text)
    errmsg += "\n"
    log.error(errmsg)

    errargmsg  = err_type+" arguments:\n{0!r}".format(type(error).__name__, error.args)
    errargmsg += "\n"
    log.error(errargmsg)

    tbmsg  = err_type+" traceback (most recent call last):"
    log.error(tbmsg)
    traceback.print_tb(exc_tb)
