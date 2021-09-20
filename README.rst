Python ProcessRunner
====================

.. image:: https://badge.fury.io/py/processrunner.svg
   :target: https://pypi.org/project/processrunner
   :alt: Pypi Version
.. image:: https://readthedocs.org/projects/processrunner/badge/?version=latest
   :target: https://processrunner.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

Designed to make reading from external processes easier. While targeted for
use cases like processing log output, it also allows multiple writers to
send text to the stdin of external processes.

Output can be sent to multiple locations. E.g. the stdout and stderr of anexternal process can be written to one or multiple files, AND also to the pipes of the local process.

Several convenience functions simplify common use cases. All the classes and functions take the command to execute in the subprocess.Popen/.call format, a list of strings starting with the command name, followed by any arguments for that command.

See https://processrunner.readthedocs.io/en/latest/ for the full documentation.


Chain commands together
=======================
Connect the stdout of one command to the stdin of another. Just use the "or"
function, similar to how this is done in a shell.

This is not all purpose. Commands often do not end when you expect them to,
and require use of watchers to stop them independently. (collectLines, for
instance, will hang.)

See the tests directory "processrunner_chaining_test.py" for examples.


Provided classes
================
ProcessRunner
  The ProcessRunner class uses subprocess.Popen. It does not use the
  ``shell=True`` flag. All instances of the class are saved in
  ``PROCESSRUNNER_PROCESSES``. A list of currently active processes started
  by the class can be retrieved by calling ``getActiveProcesses()``, which
  IS NOT a class member.

  *Properties*
    - Non-blocking: Returns immediately; the external process is managed in a new thread
    - Output can be read by iterating over ``ProcessRunner.[stdout|stderr|output]``
    - Supports ``with`` context manager syntax


Convenience functions
==============================
runCommand
  The runCommand function returns the process exit code, and stdout and stderr are connected to local stdout and stderr.

  *Parameters*
    - **command** REQUIRED ``[string,]`` The command to execute along with all parameters.
    - **outputPrefix** OPTIONAL ``string`` String to prepend to all output lines. Defaults to 'ProcessRunner> '.

  *Properties*
    - Blocking: Returns once the external command exits.

ssh
  The ssh function runs a command on a remote host, and returns the SSH exit code. stdout and stderr are connected to local stdout and stderr.

  *Parameters*
    - **remoteAddress** REQUIRED ``string`` IP or hostname for target system.
    - **remotecommand** REQUIRED ``string`` The command to run on the target system.
    - **outputPrefix** OPTIONAL ``string`` String to prepend to all output lines. Defaults to 'ssh> '.

  *Properties*
    - Blocking: Returns once the external command exits.

writeOut
  The writeOut function is used to prepend lines from the external process with a given string. Given a pipe and a string, it returns a function that accepts a line of text, then writes that line to the provided pipe, prepended with a user provided string. Useful when handling output from processes directly. See example use below.

  *Parameters*
    - **pipe** REQUIRED ``pipe`` A system pipe to write the output to.
    - **outputPrefix** REQUIRED ``string`` A string to prepend to each line.
      - This can also be any object that can be cast to a string.

  *Properties*
    - Return type is a function.

getActiveProcesses
  The getActiveProcesses function returns a list of ``ProcessRunner`` instances that are currently alive.

  *Takes no parameters*


Examples
==============

Simple
------
Use SCP to copy a local file to a remote host, using SSH key-based authentication.

::

  # Run a command, wait for it to complete, and gather its return code
  command = ["scp", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "/path/to/local/file", clientAddress+":/tmp/"]
  result = ProcessRunner(command).wait().poll()

Complex
-------
Execute a command and while it runs write lines from the external process stdout and stderr to both the corresponding local pipes, as well as corresponding files. Further, prefix the local pipe output with dedicated notes, and prefix the file output with timestamps.

::

  # Imports
  from processrunner import ProcessRunner, writeOut

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
  proc.mapLines(writeOut(pipe=sys.stdout, outputPrefix="validation-stdout> "), procPipeName="stdout")
  proc.mapLines(writeOut(pipe=sys.stderr, outputPrefix="validation-stderr> "), procPipeName="stderr")

  # Write to the log files, prepending each line with a date/time stamp
  proc.mapLines(writeOut(pipe=stdoutFile, outputPrefix=DateNote()), procPipeName="stdout")
  proc.mapLines(writeOut(pipe=stderrFile, outputPrefix=DateNote()), procPipeName="stderr")

  # Block regular execution until the process finishes
  result = proc.wait().poll()

  # Wait until the queues are emptied to close the files
  while not proc.areAllQueuesEmpty():
      time.sleep(0.01)

  stdoutFile.close()
  stderrFile.close()
