# -*- coding: utf-8 -*-
import sys

from .processrunner import ProcessRunner
from .writeout import writeOut


def runCommand(command, outputPrefix="ProcessRunner> "):
    """Easy invocation of a command with default IO streams

    Args:
        command (list): List of strings to pass to subprocess.Popen

    Kwargs:
        outputPrefix(str): String to prepend to all output lines. Defaults to 'ProcessRunner> '

    Returns:
        int The return code from the command
    """
    proc = ProcessRunner(command)
    proc.mapLines(writeOut(sys.stdout, outputPrefix=outputPrefix), procPipeName="stdout")
    proc.mapLines(writeOut(sys.stderr, outputPrefix=outputPrefix), procPipeName="stderr")
    proc.wait()
    returnCode = proc.poll()

    proc.terminate()
    proc.shutdown()

    return returnCode
