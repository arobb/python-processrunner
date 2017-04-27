# -*- coding: utf-8 -*-
'''
Wrapper for process invocation, and some convenience functions
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

# Block regular execution until the process finishes
result = proc.wait().poll()

# Wait until the queues are emptied to close the files
while not proc.areAllQueuesEmpty():
    time.sleep(0.01)

stdoutFile.close()
stderrFile.close()
'''
import os
import sys
import time
from subprocess import PIPE, Popen, STDOUT
from threading  import Thread, Lock

try:
    from Queue import Queue, Empty
except ImportError:
    from queue import Queue, Empty  # python 3.x


# Exception in case the command to execute isn't available
class CommandNotFound(OSError):
    def __init__(self, value, command):
        self.errno = 2
        self.value = value
        self.command = command

    def __str__(self):
        return repr(self.value)


ON_POSIX = 'posix' in sys.builtin_module_names

PROCESSRUNNER_PROCESSES = []


# Easy invocation of a command with default IO streams
#
# @param REQUIRED [string,] command Array of strings to pass to subprocess.Popen
# @param OPTIONAL string outputPrefix tring to prepend to all output lines. Defaults to 'ProcessRunner> '
# @returns the command exit code
def runCommand(command, outputPrefix="ProcessRunner> "):
    proc = ProcessRunner(command)
    proc.mapLines(WriteOut(sys.stdout, outputPrefix=outputPrefix), procPipeName="stdout")
    proc.mapLines(WriteOut(sys.stderr, outputPrefix=outputPrefix), procPipeName="stderr")
    proc.wait()

    return proc.poll()


# Easy invocation of SSH.
#
# @param REQUIRED string remoteAddress IP or hostname for target system
# @param REQUIRED string remotecommand The command to run on the target system
# @param OPTIONAL string outputPrefix String to prepend to all output lines. Defaults to 'ssh> '
# @returns the SSH exit code (usually the exit code of the executed command)
def ssh(remoteAddress, remoteCommand, outputPrefix="ssh> "):
    command = ["ssh", remoteAddress, "-t", "-o", "StrictHostKeyChecking=no", remoteCommand]

    proc = ProcessRunner(command)
    proc.mapLines(WriteOut(sys.stdout, outputPrefix=outputPrefix), procPipeName="stdout")
    proc.mapLines(WriteOut(sys.stderr, outputPrefix=outputPrefix), procPipeName="stderr")
    proc.wait()

    return proc.poll()


# Use with ProcessRunner.mapLines to easily write to your favorite pipe
# or handle
# @param REQUIRED pipe pipe A system pipe to write the output to
# @param REQUIRED string outputPrefix A string to prepend to each line
# @returns function
def WriteOut(pipe, outputPrefix):
    # TODO Validate the pipe somehow

    def func(line):
        try:
            pipe.write(str(outputPrefix)+str(line))
            pipe.flush()

        except ValueError as e:
            print "WriteOut caught odd error: " + str(e)

    return func


# Retrieve a list of running processes started by ProcessRunner
#
# @returns [ProcessRunner]
def getActiveProcesses():
    active = []

    for p in PROCESSRUNNER_PROCESSES:
        if p.isAlive():
            active.append(p)

    return active


MAX_QUEUE_LENGTH = 0

# Custom pipe manager to capture the output of processes and store them in
#   dedicated thread-safe queues. Readers register for their own queue.
# @private
# @param REQUIRED pipe pipeHandle Pipe to monitor for records
class _PrPipe:
    def __init__(self, pipeHandle):
        self.queue = Queue(MAX_QUEUE_LENGTH)

        self.thread = Thread(target=self.enqueue_output, kwargs={"out":pipeHandle})
        self.thread.daemon = True
        self.thread.start()

        self.clientQueuesLock = Lock()
        self.clientQueues = {}
        self.lastClientId = 0

    def enqueue_output(self, out):
        for line in iter(out.readline, b''):
            self.queue.put(line)
        out.close()

    # Push messages from the main queue to all client queues
    # Must be triggered by an external mechanism (defaulting to
    # a call of getLine)
    def publish(self):
        try:
            while not self.queue.empty():

                try:
                    self.clientQueuesLock.acquire()
                    line = self.queue.get_nowait()
                    for q in self.clientQueues.itervalues():
                        q.put(line)
                finally:
                    self.clientQueuesLock.release()

                self.queue.task_done()

        except Empty:
            pass

    def getQueue(self, clientId):
        return self.clientQueues[str(clientId)]

    def isEmpty(self, clientId=None):
        if clientId is not None:
            return self.queue.empty() and self.clientQueues[str(clientId)].empty()

        else:
            empty = self.queue.empty()
            try:
                self.clientQueuesLock.acquire()
                for cid, q in self.clientQueues.iteritems():
                    empty = empty and q.empty()
            finally:
                self.clientQueuesLock.release()

            return empty

    def isAlive(self):
        return self.thread.isAlive()

    def getLine(self, clientId):
        # Pull any newer lines
        self.publish()

        # Throws Empty
        line = self.clientQueues[str(clientId)].get_nowait()
        self.clientQueues[str(clientId)].task_done()
        return line

    def registerForClientQueue(self):
        clientId = self.lastClientId + 1
        self.lastClientId = clientId

        try:
            self.clientQueuesLock.acquire()
            self.clientQueues[str(clientId)] = Queue(MAX_QUEUE_LENGTH)
        finally:
            self.clientQueuesLock.release()

        return str(clientId)

    def unRegisterClientQueue(self, clientId):
        try:
            self.clientQueuesLock.acquire()
            value = self.clientQueues.pop(clientId)
        finally:
            self.clientQueuesLock.release()

        return value


# Easily execute external processes
# Can be used in a blocking or non-blocking manner
# Uses threads to monitor stdout and stderr of started processes
#
# @param REQUIRED [string,] command Array of strings to pass to subprocess.Popen
# @param OPTONAL string cwd Directory to change to before execution. Passed to subprocess.Popen
class ProcessRunner:
    def __init__(self, command, cwd=None):

        # Verify the command is a list of strings
        if not isinstance(command, list):
            raise TypeError("ProcessRunner command must be a list of strings. "
                            + type(command) + " given.")

        for i, param in enumerate(command):
            if not isinstance(param, basestring):
                raise TypeError("ProcessRunner command must be a list of strings. "
                                +"Parameter "+str(i)+" is "+type(command)+".")

        # Verify the command exists
        if self.which(command[0]) is None:
            raise CommandNotFound(command[0] + " not found or not executable", command[0])

        # Process to run
        self.command = command

        # Start the process with subprocess.Popen
        # 1. stdout and stderr are captured via pipes
        # 2. Output from stdout and stderr buffered per line
        # 3. File handles are closed automatically when the process exits
        self.proc = Popen(self.command, stdout=PIPE, stderr=PIPE, bufsize=1, close_fds=ON_POSIX, cwd=cwd)

        # Create pipe managers for stdout and stderr coming from the process
        self.pipes = {"stdout":_PrPipe(self.proc.stdout), "stderr":_PrPipe(self.proc.stderr)}

        # Register this ProcessRunner
        PROCESSRUNNER_PROCESSES.append(self)


    # Retreive the Popen instance
    #
    # @public
    # @returns object subprocess.Popen
    def getPopen(self):
        return self.proc


    # Retrieve the command
    #
    # @public
    # @returns [string]
    def getCommand(self):
        return self.command


    # Retreive a pipe manager by name
    #
    # @private
    # @throws KeyError
    # @param REQUIRED string procPipeName One of "stdout" or "stderr"
    # @returns object _PrPipe instance
    def getPipe(self, procPipeName):
        if procPipeName not in self.pipes:
            raise KeyError(procPipeName+" is not an available pipe")

        return self.pipes[procPipeName]


    # Verify command exists
    # Returns absolute path to exec as a string, or None if not found
    # http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    #
    # @param string program The name or full path to desired executable
    # @returns string or None
    @staticmethod
    def which(program):
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


    # Check whether the pipe manager queues report empty
    #
    # @public
    # @param REQUIRED string Pipe manager client queue ID
    # @param REQUIRED string procPipeName One of "stdout" or "stderr"
    # @returns bool
    def isQueueEmpty(self, clientId, procPipeName):
        return self.getPipe(procPipeName).isEmpty(clientId)


    # Check that all queues are empty
    # A bit dangerous to use, will block if any client has stopped pulling from
    # their queue. Better to use isQueueEmpty() for the dedicated client queue.
    # Sometimes (especially externally) that's not possible.
    #
    # @public
    # @returns bool
    def areAllQueuesEmpty(self):
        empty = True

        for pipe in self.pipes.itervalues():
            empty = empty and pipe.isEmpty()

        return empty


    # Check whether the process reports alive
    #
    # @public
    # @returns bool
    def isAlive(self):
        state = True if self.proc.poll() is None else False

        return state


    # Invoke the subprocess.Popen.poll() method
    #
    # @public
    # @returns NoneType if alive, or int with exit code if dead
    def poll(self):
        return self.proc.poll()


    # Block until the process exits
    # Does some extra checking to make sure the pipe managers have finished reading
    # Blocking
    #
    # @public
    # @returns object ProcessRunner instance (self)
    def wait(self):
        def isAliveLocal():
            alive = True
            for pipe in self.pipes.itervalues():
                alive = alive and pipe.isAlive()
            return alive

        while self.poll() is None or isAliveLocal() is True:
            time.sleep(0.01)

        return self


    # Register to get a client queue on a pipe manager. The ID for the queue is
    # returned from the method as a string.
    # Blocking
    #
    # @public
    # @param REQUIRED string procPipeName One of "stdout" or "stderr"
    # @returns string
    def registerForClientQueue(self, procPipeName):
        return self.getPipe(procPipeName).registerForClientQueue()


    # Unregister a client queue from a pipe manager. Prevents other clients from waiting
    # on other clients that will never be read
    # Blocking
    #
    # @public
    # @param REQUIRED string procPipeName One of "stdout" or "stderr"
    # @param REQUIRED string clientId ID of the client queue on this pipe manager
    # @returns Queue
    def unRegisterClientQueue(self, procPipeName, clientId):
        return self.getPipe(procPipeName).unRegisterClientQueue(clientId)


    # Retrieve a line from a pipe manager. Throws Empty if no lines are available.
    # Blocking
    #
    # @public
    # @throws Empty
    # @param REQUIRED string Pipe manager client queue ID
    # @param REQUIRED string procPipeName One of "stdout" or "stderr"
    # @returns string
    def getLineFromPipe(self, clientId, procPipeName):
        line = self.getPipe(procPipeName).getLine(clientId)
        return line


    # Run a function against each line presented by one pipe manager.
    # Returns a reference to a dict that can be used to monitor the status of
    # the function. When the process is dead, the queues are empty, and all lines
    # are processed, the dict will be updated. This can be used as a blocking
    # mechanism by functions invoking mapLines.
    # Status dict format: {"complete":bool}
    # Non-blocking
    #
    # @public
    # @param REQUIRED function func A function that takes one parameter, the line from the pipe
    # @param REQUIRED string procPipeName One of "stdout" or "stderr"
    # @returns dict
    def mapLines(self, func, procPipeName):
        clientId = self.registerForClientQueue(procPipeName)
        status = {'complete':False}

        def doWrite(context, func, status, procPipeName):

            # Make sure we unregister
            try:
                # Continue while there MIGHT be data to read
                while context.isAlive() or not context.isQueueEmpty(clientId, procPipeName):

                    # Continue while we KNOW THERE IS data to read
                    while True:
                        try:
                            line = context.getLineFromPipe(clientId, procPipeName)
                            func(line)
                        except Empty:
                            break

                    time.sleep(0.01)

                status['complete'] = True

            finally:
                context.unRegisterClientQueue(procPipeName, clientId)

        thread = Thread(target=doWrite, kwargs={"context":self, "func":func, "status":status, "procPipeName":procPipeName})
        thread.daemon = True
        thread.start()

        return status



    # Retrieve output lines as a list for one or all pipes from the process
    # Blocking
    #
    # @public
    # @param OPTIONAL string procPipeName One of "stdout" or "stderr"
    # @returns [string,]
    def collectLines(self, procPipeName=None):
        outputList = []

        # Register for client IDs from all appropriate pipe managers
        clientIds = {}
        if procPipeName is None:
            for pipeName in self.pipes.iterkeys():
                clientIds[pipeName] = self.registerForClientQueue(pipeName)

        else:
            clientIds[procPipeName] = self.registerForClientQueue(procPipeName)

        # Internal function to check whether we are done reading
        def checkComplete(self, clientIds):
            complete = True
            complete = complete and not self.isAlive()

            for pipeName, clientId in clientIds.iteritems():
                complete = complete and self.isQueueEmpty(clientId, pipeName)

            return complete

        # Main loop to pull everything off our queues
        while not checkComplete(self, clientIds):
            for pipeName, clientId in clientIds.iteritems():
                while True:
                    try:
                        line = self.getLineFromPipe(clientId, pipeName).rstrip('\n')
                        outputList.append(line)
                    except Empty:
                        break

            time.sleep(0.01)

        return outputList
