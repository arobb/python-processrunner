# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .runcommand import runCommand


def ssh(remoteAddress, remoteCommand, outputPrefix="ssh> "):
    """Easy invocation of SSH.

    Note: Sets StrictHostKeyChecking to "no".

    Args:
        remoteAddress (string): IP or hostname for target system
        remoteCommand (string): The command to run on the target system
        outputPrefix (string): String to prepend to all output lines.
            Defaults to 'ssh> '

    Returns:
        int. The SSH exit code (usually the exit code of the executed command)
    """
    command = ["ssh", remoteAddress, "-t", "-o", "StrictHostKeyChecking=no",
               remoteCommand]

    returnCode = runCommand(command, outputPrefix)

    return returnCode
