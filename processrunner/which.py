# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os


def which(program):
    """Verify command exists

    Returns absolute path to exec as a string, or None if not found
    http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python

    Args:
        program (string): The name or full path to desired executable

    Returns:
        string, None
    """

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None
