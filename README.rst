.. _Documentation: https://processrunner.readthedocs.io/en/latest/
.. _Convenience Functions: https://processrunner.readthedocs.io/en/latest/convenience.html

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

Output can be sent to multiple locations. E.g. the stdout and stderr of an
external process can be written to one or multiple files, AND also to the
pipes of the local process.

Several convenience functions simplify common use cases. All the classes and
functions take the command to execute in the subprocess.Popen/.call format,
a list of strings starting with the command name, followed by any arguments
for that command.

See the full `documentation`_ for complete details.


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
A number of convenience functions are available to quickly run a command
with common options, run a command via SSH, and other activities. These are
referenced on the Convenience Functions documentation page: `Convenience
Functions`_.

Examples
==============
A larger set of examples is available on the Examples page in the
documentation.

Simple
------
Use SCP to copy a local file to a remote host, using SSH key-based authentication.

::

  # Run a command, wait for it to complete, and gather its return code
  command = ["scp", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "/path/to/local/file", clientAddress+":/tmp/"]
  result = ProcessRunner(command).wait().poll()

Complex
-------
While an external command runs, write the external process' ``stdout`` and
``stderr`` to the corresponding local pipes, as well as corresponding files.
Further, prefix the local pipe output with dedicated notes, and prefix the
file output with timestamps.

::

    # Imports
    import os
    import sys
    from datetime import datetime
    from processrunner import ProcessRunner, WriteOut

    if __name__ == "__main__":
        # Logging files
        working_dir = os.path.dirname(os.path.realpath(__file__))
        stdoutFile = open(working_dir+'/stdout.txt', 'a')
        stderrFile = open(working_dir+'/stderr.txt', 'a')

        # Date/time notation for output lines in files
        class DateNote:
            def init(self):
                pass
            def __repr__(self):
                return datetime.now().isoformat() + " "

        # Prep the process
        # Script available in the ProcessRunner source:
        # https://github.com/arobb/python-processrunner/blob/main/tests/test-output-script.py
        command = ["tests/test-output-script.py",
                   "--lines", "5",
                   "--out-pipe", "both"]
        proc = ProcessRunner(command, autostart=False)

        # Attach output mechanisms to the process's output pipes. These are
        # handled asynchronously, so you can see the output while it is happening
        # Write to the console's stdout and stderr, with custom prefixes for each
        proc.mapLines(WriteOut(pipe=sys.stdout,
                               outputPrefix="validation-stdout> "),
                      procPipeName="stdout")
        proc.mapLines(WriteOut(pipe=sys.stderr,
                               outputPrefix="validation-stderr> "),
                      procPipeName="stderr")

        # Write to the log files, prepending each line with a date/time stamp
        proc.mapLines(WriteOut(pipe=stdoutFile, outputPrefix=DateNote()),
                      procPipeName="stdout")
        proc.mapLines(WriteOut(pipe=stderrFile, outputPrefix=DateNote()),
                      procPipeName="stderr")

        # Start the process, then block regular execution until the
        # process finishes
        proc.start().wait()

        stdoutFile.close()
        stderrFile.close()
