# -*- coding: utf-8 -*-
"""Easy invocation of a command with default IO streams"""
from __future__ import unicode_literals

import sys

from .processrunner import ProcessRunner
from .writeout import writeOut


def runCommand(command,
               outputPrefix="ProcessRunner> ",
               returnAllContent=False):
    """Easy invocation of a command with default IO streams

    returnAllContent as False (default):

    :param list command: List of strings to pass to subprocess.Popen
    :param str outputPrefix: String to prepend to all output lines.
           Defaults to 'ProcessRunner> '
    :param bool returnAllContent: False (default) sends command stdout/stderr
           to regular interfaces, True collects and returns them

    Returns:
    int The return code from the command (returnAllContent as False (default))
    tuple (return code, list of output) The return code and any output
    content (returnAllContent as True)
    """
    with ProcessRunner(command) as proc:
        if returnAllContent:
            content = proc.collectLines()
        else:
            proc.mapLines(writeOut(sys.stdout, outputPrefix=outputPrefix),
                          procPipeName="stdout")
            proc.mapLines(writeOut(sys.stderr, outputPrefix=outputPrefix),
                          procPipeName="stderr")

        return_code = proc.wait().poll()

    if returnAllContent:  # pylint: disable=no-else-return
        return return_code, content
    else:
        return return_code
