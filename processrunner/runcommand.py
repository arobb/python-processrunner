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

    Args:
        command (list): List of strings to pass to subprocess.Popen
        outputPrefix(str): String to prepend to all output lines.
            Defaults to 'ProcessRunner> '
        returnAllContent(bool): False (default) sends command stdout/stderr to
            regular interfaces, True collects and returns them

    Returns:
        int The return code from the command
            (returnAllContent as False (default))
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

        returnCode = proc.wait().poll()

    if returnAllContent:
        return returnCode, content
    else:
        return returnCode
