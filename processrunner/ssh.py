# -*- coding: utf-8 -*-
import sys

from .processrunner import ProcessRunner
from .writeout import writeOut


def ssh(remoteAddress, remoteCommand, outputPrefix="ssh> "):
    """Easy invocation of SSH.

    Args:
        remoteAddress (string): IP or hostname for target system
        remoteCommand (string): The command to run on the target system

    Kwargs:
        outputPrefix (string): String to prepend to all output lines. Defaults to 'ssh> '

    Returns:
        int. The SSH exit code (usually the exit code of the executed command)
    """
    command = ["ssh", remoteAddress, "-t", "-o", "StrictHostKeyChecking=no", remoteCommand]

    proc = ProcessRunner(command)
    proc.mapLines(writeOut(sys.stdout, outputPrefix=outputPrefix), procPipeName="stdout")
    proc.mapLines(writeOut(sys.stderr, outputPrefix=outputPrefix), procPipeName="stderr")
    proc.wait()
    returnCode = proc.poll()

    proc.terminate()
    proc.shutdown()

    return returnCode
