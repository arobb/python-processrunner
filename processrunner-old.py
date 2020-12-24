# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import os
import random
import sys
import time
from subprocess import PIPE, Popen, STDOUT

import multiprocessing
from multiprocessing import Process, Lock, JoinableQueue
from multiprocessing.managers import BaseManager

try:
    from Queue import Empty
except ImportError:
    from queue import Empty  # python 3.x


"""
Wrapper for process invocation, and some convenience functions. Allows for
multiple readers to consume output from each of the invoked process' output
pipes. (Makes it possible to write output to the applications' stdout/stderr,
as well as to a file.)
Original reference http://stackoverflow.com/questions/375427/non-blocking-read-on-a-subprocess-pipe-in-python


ssh function returns the SSH exit code. Takes the following parameters
- REQUIRED string remoteAddress IP or hostname for target system
- REQUIRED string remotecommand The command to run on the target system
- OPTIONAL string outputPrefix String to prepend to all output lines. Defaults to 'ssh> '


WriteOut function returns a function that accepts a line and writes that line
to the provided pipe, prepended with a user provided string. Useful when handling
output from processes directly. See example use in the ssh function.
Takes the following parameters
- REQUIRED pipe pipe A system pipe to write the output to
- REQUIRED string outputPrefix A string to prepend to each line
-- This can also be any object that can be cast to a string


getActiveProcesses function returns a list of ProcessRunner instances that are
currently alive. Takes no parameters.


ProcessRunner class uses subprocess.Popen. It does not use the shell=True flag.
All processes started by the class are saved in PROCESSRUNNER_PROCESSES. A list
of currently active processes started by the class can be retrieved by calling
getActiveProcesses(), which IS NOT a class member.
Takes these parameters:
- REQUIRED [string,] command The command to execute along with all parameters
- OPTIONAL string cwd Directory to switch into before execution. CWD does not
                      apply to the _location_ of the process, which must be on
                      PATH


Simple example:
# Run a command, wait for it to complete, and gather its return code
command = ["scp", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "/path/to/local/file", clientAddress+":/tmp/"]
result = ProcessRunner(command).wait().poll()


Complex example:
# Logging files
stdoutFile = open(workingDir+'/stdout.txt', 'a')
stderrFile = open(workingDir+'/stderr.txt', 'a')

# Date/time notation for output lines in files
class DateNote:
    def init(self):
        pass
    def __repr__(self):
        return datetime.now().isoformat() + " "

# Start the process
proc = ProcessRunner(command)

# Attach output mechanisms to the process's output pipes. These are handled asynchronously, so you can see the output while it is happening
# Write to the console's stdout and stderr, with custom prefixes for each
proc.mapLines(WriteOut(pipe=sys.stdout, outputPrefix="validation-stdout> "), procPipeName="stdout")
proc.mapLines(WriteOut(pipe=sys.stderr, outputPrefix="validation-stderr> "), procPipeName="stderr")

# Write to the log files, prepending each line with a date/time stamp
proc.mapLines(WriteOut(pipe=stdoutFile, outputPrefix=DateNote()), procPipeName="stdout")
proc.mapLines(WriteOut(pipe=stderrFile, outputPrefix=DateNote()), procPipeName="stderr")

# Block regular execution until the process finishes and get return code
result = proc.wait().poll()

# Wait until the queues are emptied to close the files
while not proc.areAllQueuesEmpty():
    time.sleep(0.01)

stdoutFile.close()
stderrFile.close()


Example running a background process with output mappers
# Logging files
stdoutFile = open(workingDir+'/stdout.txt', 'a')
stderrFile = open(workingDir+'/stderr.txt', 'a')

# Date/time notation for output lines in files
class DateNote:
    def init(self):
        pass
    def __repr__(self):
        return datetime.now().isoformat() + " "

# Start the process
proc = ProcessRunner(command)

# Attach output mechanisms to the process's output pipes. These are handled asynchronously, so you can see the output while it is happening
# Write to the console's stdout and stderr, with custom prefixes for each
proc.mapLines(WriteOut(pipe=sys.stdout, outputPrefix="validation-stdout> "), procPipeName="stdout")
proc.mapLines(WriteOut(pipe=sys.stderr, outputPrefix="validation-stderr> "), procPipeName="stderr")

# Write to the log files, prepending each line with a date/time stamp
proc.mapLines(WriteOut(pipe=stdoutFile, outputPrefix=DateNote()), procPipeName="stdout")
proc.mapLines(WriteOut(pipe=stderrFile, outputPrefix=DateNote()), procPipeName="stderr")

# Start the mapper processes
# Only required if you use mapLines()
proc.startMapLines()

# Everything is now running
# Do other stuff here

# Synchronously stop the process and all mappers
proc.terminate() # Kill the command and queue processes
proc.shutdown() # Destroy the process manager and clean up the OS process
"""


class CommandNotFound(OSError):
    """Exception in case the command to execute isn't available"""
    def __init__(self, value, command):
        self.errno = 2
        self.value = value
        self.command = command

    def __str__(self):
        return repr(self.value)


ON_POSIX = 'posix' in sys.builtin_module_names
PROCESSRUNNER_PROCESSES = [] # Holding list for instances of ProcessRunner
MAX_QUEUE_LENGTH = 0 # Maximum length for Queues
AUTHKEY = ''.join([random.choice('0123456789ABCDEF') for x in range(256)])


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
    proc.mapLines(WriteOut(sys.stdout, outputPrefix=outputPrefix), procPipeName="stdout")
    proc.mapLines(WriteOut(sys.stderr, outputPrefix=outputPrefix), procPipeName="stderr")
    proc.wait()
    returnCode = proc.poll()

    # proc.terminate()
    # proc.shutdown()

    return returnCode


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
    proc.mapLines(WriteOut(sys.stdout, outputPrefix=outputPrefix), procPipeName="stdout")
    proc.mapLines(WriteOut(sys.stderr, outputPrefix=outputPrefix), procPipeName="stderr")
    proc.wait()
    returnCode = proc.poll()

    # proc.terminate()
    # proc.shutdown()

    return returnCode



# Moved
def WriteOut(pipe, outputPrefix):
    """Use with ProcessRunner.mapLines to easily write to your favorite pipe
       or handle

    Args:
        pipe (pipe): A system pipe/file handle to write output to
        outputPrefix (string): A string to prepend to each line

    Returns:
        function
    """
    # TODO Validate the pipe somehow

    def func(line):
        try:
            pipe.write(text(outputPrefix)+text(line))
            pipe.flush()

        except ValueError as e:
            print("WriteOut caught odd error: " + text(e))

    return func


# Moved
def getActiveProcesses():
    """Retrieve a list of running processes started by ProcessRunner

    Returns:
        list. List of ProcessRunner instances
    """
    active = []

    for p in PROCESSRUNNER_PROCESSES:
        if p.is_alive():
            active.append(p)

    return active


#
# Original _PrPipe location
#


#
# Original _Command location
#


#
# Original _CommandManager location
#

#
# Original ProcessRunner location
#
