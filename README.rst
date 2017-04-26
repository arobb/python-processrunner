Python ProcessRunner
====================
Designed to make reading from external processes easier. Does not permit interactive communication with the process, but rather provides (usually) simplified consumption of process output, especially targeted at logging use cases.

Output can be sent to multiple locations. E.g. the stdout and stderr of an external process can be written to one or multiple files, AND also to the pipes of the local process.

Several convenience functions simplify common use cases. All the classes and functions take the command to execute in the subprocess.Popen/.call format, a list of strings starting with the command name, followed by any arguments for that command.


Provided classes
================
ProcessRunner
  The ProcessRunner class uses subprocess.Popen. It does not use the ``shell=True`` flag. All processes started by the class are saved in ``PROCESSRUNNER_PROCESSES``. A list of currently active processes started by the class can be retrieved by calling ``getActiveProcesses()``, which IS NOT a class member.

  *Parameters*
    - **command** REQUIRED ``[string,]`` The command to execute along with all parameters
    - **cwd** OPTIONAL ``string`` Directory to switch into before execution. CWD does not apply to the _location_ of the process, which must be on PATH.

ProcessRunner class methods
---------------------------
**getPopen**

**getCommand**

**getPipe**

**which**

**isQueueEmpty**

**isAlive**

**poll**

**wait**

**registerForClientQueue**

**unRegisterClientQueue**

**getLineFromPipe**

**mapLines**

**collectLines**


Provided convenience functions
==============================
runCommand
  The runCommand function returns the process exit code, and stdout and stderr are connected to local stdout and stderr.

ssh
  The ssh function runs a command on a remote host, and returns the SSH exit code. stdout and stderr are connected to local stdout and stderr.

  *Parameters*
    - **remoteAddress** REQUIRED ``string`` IP or hostname for target system
    - **remotecommand** REQUIRED ``string`` The command to run on the target system
    - **outputPrefix** OPTIONAL ``string`` String to prepend to all output lines. Defaults to 'ssh> '

WriteOut
  The WriteOut function is used to prepend lines from the external process with a given string. Given a pipe and a string, it returns a function that accepts a line of text, then writes that line to the provided pipe, prepended with a user provided string. Useful when handling output from processes directly. See example use below.

  *Parameters*
    - **pipe** REQUIRED ``pipe`` A system pipe to write the output to
    - **outputPrefix** REQUIRED ``string`` A string to prepend to each line
      - This can also be any object that can be cast to a string

getActiveProcesses
  The getActiveProcesses function returns a list of ProcessRunner instances that are currently alive.

  *Takes no parameters*


Exceptions
----------
CommandNotFound
  Exception thrown when the command to execute isn't available.


Examples
==============

Simple
------

::

  # Run a command, wait for it to complete, and gather its return code
  command = ["scp", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "/path/to/local/file", clientAddress+":/tmp/"]
  result = ProcessRunner(command).wait().poll()

Complex
-------

::

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

  # Block regular execution until the process finishes
  result = proc.wait().poll()

  # Wait until the queues are emptied to close the files
  while not proc.areAllQueuesEmpty():
      time.sleep(0.01)

  stdoutFile.close()
  stderrFile.close()
