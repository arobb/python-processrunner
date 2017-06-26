# -*- coding: utf-8 -*-
'''
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
'''
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
    from queue import Empty # python 3.x


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

    return proc.poll()


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

    return proc.poll()


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
            pipe.write(str(outputPrefix)+str(line))
            pipe.flush()

        except ValueError as e:
            print "WriteOut caught odd error: " + str(e)

    return func


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


# Private class only intended to be used by ProcessRunner
class _PrPipe(object):
    """Custom pipe manager to capture the output of processes and store them in
       dedicated thread-safe queues.

       Clients register their own queues.
    """
    def __init__(self, pipeHandle):
        """
        Args:
            pipeHandle (pipe): Pipe to monitor for records
        """
        self.id = ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

        self.queue = JoinableQueue(MAX_QUEUE_LENGTH)

        self.process = Process(target=self.enqueue_output, kwargs={"out":pipeHandle,"queue":self.queue})
        self.process.daemon = True
        self.process.start()

        self.clientQueuesLock = Lock()
        self.clientQueues = {}
        self.lastClientId = 0


    # Class contains Locks and Queues which cannot be pickled
    def __getstate__(self):
        """Prevent _PrPipe from being pickled across Processes

        Raises:
            Exception
        """
        raise Exception("Don't pickle me!")


    def enqueue_output(self, out, queue):
        """Copy lines from a given pipe handle into a local threading.Queue

        Runs in a separate process, started by __init__

        Args:
            out (pipe): Pipe to read from
            queue (Queue): Queue to write to
        """
        for line in iter(out.readline, b''):
            queue.put(line)
        out.close()


    def publish(self):
        """Push messages from the main queue to all client queues

        Must be triggered by an external mechanism
        Typically triggered by getLine or wait

        """
        try:
            while not self.queue.empty():

                with self.clientQueuesLock:
                    line = self.queue.get_nowait()
                    for q in self.clientQueues.itervalues():
                        q.put(line)

                self.queue.task_done()

        except Empty:
            pass


    def getQueue(self, clientId):
        """Retrieve a client's Queue proxy object

        Args:
            clientId (string): ID of the client

        Returns:
            QueueProxy
        """
        return self.clientQueues[str(clientId)]


    def isEmpty(self, clientId=None):
        """Checks whether the primary Queue or any clients' Queues are empty

        Returns True ONLY if ALL queues are empty if clientId is None
        Returns True ONLY if both main queue and specfied client queue are empty
        when clientId is provided

        Args:
            clientId (string): ID of the client

        Returns:
            bool
        """
        if clientId is not None:
            return self.queue.empty() \
                and self.getQueue(clientId).empty()

        else:
            empty = self.queue.empty()

            with self.clientQueuesLock:
                for q in self.clientQueues.itervalues():
                    empty = empty and q.empty()

            return empty


    def is_alive(self):
        """Check whether the thread managing the pipe > Queue movement
        is still active

        Returns:
            bool
        """
        return self.process.is_alive()


    def getLine(self, clientId):
        """Retrieve a line from a given client's Queue

        Args:
            clientId (string): ID of the client

        Returns:
            <element from Queue>

        Raises:
            Empty
        """
        # Pull any newer lines
        self.publish()

        # Throws Empty
        q = self.getQueue(clientId)
        line = q.get_nowait()
        q.task_done()

        return line


    def registerClientQueue(self, queueProxy):
        """Attach an additional Queue proxy to this _PrPipe

        All elements published() from now on will also be added to this Queue
        Returns the clientId for the new client, which must be used in all
        future interaction with this _PrPipe

        Args:
            queueProxy (QueueProxy): Proxy object to a Queue we should populate

        Returns:
            string. The client's ID for acccess to this queue

        """
        # Make sure we don't re-use a clientId
        clientId = self.lastClientId + 1
        self.lastClientId = clientId

        with self.clientQueuesLock:
            self.clientQueues[str(clientId)] = queueProxy

        return str(clientId)


    def unRegisterClientQueue(self, clientId):
        """Detach a Queue proxy from this _PrPipe

        Returns the clientId that was removed

        Args:
            clientId (string): ID of the client

        Returns:
            string. ID of the client queue

        """
        with self.clientQueuesLock:
            self.clientQueues.pop(clientId)

        return str(clientId)


    def destructiveAudit(self):
        """Print a line from each client Queue attached to this _PrPipe

        This is a destructive operation, as it *removes* a line from each Queue
        """
        with self.clientQueuesLock:
            for clientId in self.clientQueues.iterkeys():
                try:
                    print "clientId " + str(clientId) + ": " + self.getLine(clientId)
                except:
                    print "clientId " + str(clientId) + " is empty"


# Private class only intended to be used by ProcessRunner
class _Command(object):
    """Custom wrapper for Popen that manages the interaction with Popen and any
    client objects that have requested output

    Runs in a separate process and is managed via multiprocessing.BaseManager,
    which provides proxy access to class methods

    """
    def __init__(self, command, cwd=None):
        """
        Args:
            command (list): List of strings to pass to subprocess.Popen

        Kwargs:
            cwd (string): Directory to change to before execution. Passed to subprocess.Popen
        """
        self.command = command

        # Start the process with subprocess.Popen
        # 1. stdout and stderr are captured via pipes
        # 2. Output from stdout and stderr buffered per line
        # 3. File handles are closed automatically when the process exits
        self.proc = Popen(self.command, stdout=PIPE, stderr=PIPE, bufsize=1, close_fds=ON_POSIX, cwd=cwd)

        # Initalize readers to transfer output from the Popen pipes to local queues
        self.pipes = {"stdout":_PrPipe(self.proc.stdout), "stderr":_PrPipe(self.proc.stderr)}


    def get(self, parameter):
        """Retrieve the value of a local parameter

        Allows access to local parameters when an instance is proxied via
        multiprocessing.BaseManager (which only provides access to methods, not
        parameters)

        Args:
            parameter (string): Name of the parameter on this object to read

        Returns:
            <parameter value>
        """
        return getattr(self, parameter)


    def getCommand(self):
        """Retrieve the command that Popen is running

        Returns:
            list. List of strings
        """
        return self.command


    def getPipe(self, procPipeName):
        """Retreive a _PrPipe manager instance by pipe name

        Args:
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            _PrPipe

        Raises:
            KeyError
        """
        if procPipeName not in self.pipes:
            raise KeyError(procPipeName+" is not an available pipe")

        return self.pipes[procPipeName]


    def publish(self):
        """Force publishing of any pending messages"""
        for pipe in self.pipes.itervalues():
            pipe.publish()


    def isQueueEmpty(self, procPipeName, clientId):
        """Check whether the _PrPipe queues report empty for a given pipe and client

        Args:
            clientId (string): ID of the client queue
            procPipeName (string): One of "stdout" or  "stderr"

        Returns:
            bool
        """
        return self.getPipe(procPipeName).isEmpty(clientId)


    def areAllQueuesEmpty(self):
        """Check that all queues are empty

        A bit dangerous to use, will block if any client has stopped pulling from
        their queue. Better to use isQueueEmpty() for the dedicated client queue.
        Sometimes (especially externally) that's not possible.

        Returns:
            bool
        """
        empty = True

        for pipename, pipe in self.pipes.iteritems():
            print pipename + " is " + ("empty" if pipe.isEmpty() == True else "not empty")
            empty = empty and pipe.isEmpty()

        return empty


    def is_alive(self):
        """Check whether the Popen process reports alive

        Returns:
            bool
        """
        state = True if self.proc.poll() is None else False

        return state


    def poll(self):
        """Invoke the subprocess.Popen.poll() method

        Returns:
            NoneType, int. NoneType if alive, or int with exit code if dead
        """
        return self.proc.poll()


    def wait(self):
        """Block until the process exits

        Does some extra checking to make sure the pipe managers have finished reading

        Returns:
            None
        """
        def isAliveLocal():
            self.publish() # Force down any unprocessed messages
            alive = False
            for pipe in self.pipes.itervalues():
                alive = alive or pipe.is_alive()
            return alive

        while self.poll() is None or isAliveLocal() is True:
            time.sleep(0.01)

        return None


    def registerClientQueue(self, procPipeName, queueProxy):
        """Register to get a client queue on a pipe manager

        The ID for the queue is returned from the method as a string

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            queueProxy (queueProxy): Proxy object to a Queue we should populate

        Returns:
            string. Client queue ID (unique only when combined with procPipeName)

        """
        return self.getPipe(procPipeName).registerClientQueue(queueProxy)


    def unRegisterClientQueue(self, procPipeName, clientId):
        """Unregister a client queue from a pipe manager

        Prevents other clients from waiting on queues that will never be read

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager

        Returns:
            None
        """
        self.getPipe(procPipeName).unRegisterClientQueue(clientId)

        return None


    def getLineFromPipe(self, procPipeName, clientId):
        """Retrieve a line from a pipe manager

        Throws Empty if no lines are available.

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager

        Returns:
            string. Line from specified client queue

        Raises:
            Empty
        """
        line = self.getPipe(procPipeName).getLine(clientId)
        return line


    def destructiveAudit(self):
        """Force one line of output each from attached pipes

        Used for debugging issues that might relate to data stuck in the queues.
        Triggers the pipes' destructiveAudit function which prints the last
        line of the queue or an 'empty' message.
        """
        for pipe in self.pipes.itervalues():
            pipe.destructiveAudit()


# Configure a multiprocessing.BaseManager to allow for proxy access
#   to the _Command class.
# This allows us to decouple the main application process from
#   the process that runs Popen and publishes output from Popen
#   into the client queues.
class _CommandManager(BaseManager): pass
_CommandManager.register("_Command", _Command)


class ProcessRunner:
    """Easily execute external processes"""
    def __init__(self, command, cwd=None):
        """Easily execute external processes

        Can be used in a blocking or non-blocking manner
        Uses separate processes to monitor stdout and stderr of started processes

        Args:
            command (list): A list of strings, making up the command to pass to Popen

        Kwargs:
            cwd (string): Directory to change to before execution. Passed to subprocess.Popen
        """
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

        # Multiprocessing instance used to start process-safe Queues
        self.manager = multiprocessing.Manager()

        # Storage for multiprocessing.Queues started on behalf of clients
        self.pipeClients = {"stdout":{}, "stderr":{}}
        self.pipeClientProcesses = {"stdout":{}, "stderr":{}}

        # Instantiate the Popen wrapper
        self.runManager = _CommandManager()
        self.runManager.start()

        # Trigger execution
        self.run = self.runManager._Command(command, cwd)

        # Register this ProcessRunner
        PROCESSRUNNER_PROCESSES.append(self)

        # Whether we've started the child mapLines processes
        self.mapLinesStarted = False


    def getCommand(self):
        """Retrieve the command list

        Returns:
            list. The list of strings passed to Popen
        """
        return self.command


    def publish(self):
        """Force publishing of any pending messages on attached pipes
        """
        self.run.publish()


    @staticmethod
    def which(program):
        """Verify command exists

        Returns absolute path to exec as a string, or None if not found
        http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python

        Args:
            program (string): The name or full path to desired executable

        Returns:
            string, None
        """
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


    def isQueueEmpty(self, procPipeName, clientId):
        """Check whether the pipe manager queues report empty

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager

        Returns:
            bool.
        """
        return self.run.isQueueEmpty(procPipeName, clientId)


    def areAllQueuesEmpty(self):
        """Check that all queues are empty

        A bit dangerous to use, will block if any client has stopped pulling from
        their queue. Better to use isQueueEmpty() for the dedicated client queue.
        Sometimes (especially externally) that's not possible.

        Returns:
            bool
        """
        return self.run.areAllQueuesEmpty()


    def is_alive(self):
        """Check whether the Popen process reports alive

        Returns:
            bool
        """
        return self.run.is_alive()


    # @deprecated
    def isAlive(self):
        return self.is_alive()


    def poll(self):
        """Invoke the subprocess.Popen.poll() method

        Returns:
            None, int. NoneType if alive, or int with exit code if dead
        """
        return self.run.poll()


    def join(self):
        """Join any client processes, waiting for them to exit

        .wait() calls this, so not necessary to use separately
        """
        for procPipeName in self.pipeClientProcesses.iterkeys():
            for clientId, clientProcess in self.pipeClientProcesses[procPipeName].iteritems():
                # print "Joining " + procPipeName + " client " + str(clientId) + "..."
                self.pipeClientProcesses[procPipeName][str(clientId)].join()


    def wait(self):
        """Block until the Popen process exits

        Does some extra checking to make sure the pipe managers have finished reading
        """
        self.startMapLines()
        self.run.wait()
        self.join()

        return self


    def terminate(self):
        """Clean up straggling processes that might still be running"""
        # Clean up readers
        for procPipeName in self.pipeClientProcesses.iterkeys():
            for clientId, clientProcess in self.pipeClientProcesses[procPipeName].iteritems():
                # Close any remaining client readers
                self.pipeClientProcesses[procPipeName][str(clientId)].terminate()
                # Remove references to client queues
                self.unRegisterClientQueue(procPipeName, clientId)

        self.manager.shutdown()
        self.runManager.shutdown()


    def registerForClientQueue(self, procPipeName):
        """Register to get a client queue on a pipe manager

        The ID for the queue is returned from the method as a string.

        Args:
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            string. Client's queue ID on this pipe
        """
        q = self.manager.Queue(MAX_QUEUE_LENGTH)
        clientId = self.run.registerClientQueue(procPipeName, q)
        self.pipeClients[procPipeName][clientId] = q

        return clientId


    def unRegisterClientQueue(self, procPipeName, clientId):
        """Unregister a client queue from a pipe manager

        Keeps other clients from waiting on other clients that will never be read

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager

        Returns:
            string. Client's queue ID that was unregistered
        """
        self.run.unRegisterClientQueue(procPipeName, clientId)

        if str(clientId) in self.pipeClientProcesses:
            self.pipeClientProcesses.pop(str(clientId))


    def getLineFromPipe(self, procPipeName, clientId):
        """Retrieve a line from a pipe manager

        Throws Empty if no lines are available.

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager

        Returns:
            string. Line from specified client queue

        Raises:
            Empty
        """
        line = self.run.getLineFromPipe(procPipeName, clientId)
        return line


    def destructiveAudit(self):
        """Force one line of output each from attached pipes

        Used for debugging issues that might relate to data stuck in the queues.
        Triggers the pipes' destructiveAudit function which prints the last
        line of the queue or an 'empty' message.
        """
        return self.run.destructiveAudit()


    def mapLines(self, func, procPipeName):
        """Run a function against each line presented by one pipe manager

        Returns a reference to a dict that can be used to monitor the status of
        the function. When the process is dead, the queues are empty, and all lines
        are processed, the dict will be updated. This can be used as a blocking
        mechanism by functions invoking mapLines.
        Status dict format: {"complete":bool}

        Args:
            func (function): A function that takes one parameter, the line from the pipe
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            dict
        """
        clientId = self.registerForClientQueue(procPipeName)
        status = {'complete':False}

        def doWrite(run, func, status, clientId, procPipeName):
            # print "starting doWrite for " + procPipeName

            try:
                # Continue while there MIGHT be data to read
                while run.is_alive() \
                    or not run.isQueueEmpty(procPipeName, clientId):
                    # print "might be data to read in " + procPipeName

                    # Continue while we KNOW THERE IS data to read
                    while True:
                        try:
                            line = run.getLineFromPipe(procPipeName, clientId)
                            func(line)
                        except Empty:
                            break

                    time.sleep(0.01)

                status['complete'] = True

            finally:
                pass

        client = Process(target=doWrite, kwargs={"run":self.run, "func":func, "status":status, "clientId":clientId, "procPipeName":procPipeName})
        client.daemon = True

        # Store the process so it can potentially be re-joined
        self.pipeClientProcesses[procPipeName][str(clientId)] = client

        return status


    # Eliminates a potential race condition in mapLines if two are started on
    #   the same pipe
    # All client queues are regiestered at the beginning of the call to
    #   mapLines, so we can now start the clients sequentially without any
    #   possible message loss
    def startMapLines(self):
        """Start mapLines child processes

        Triggered by wait(), so almost never needs to be called directly.
        """
        if self.mapLinesStarted == False:
            self.mapLinesStarted = True
            for pipeClientProcesses in self.pipeClientProcesses.itervalues():
                for client in pipeClientProcesses.itervalues():
                    client.start()


    def collectLines(self, procPipeName=None):
        """Retrieve output lines as a list for one or all pipes from the process

        Kwargs:
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            list. List of strings that are the output lines from selected pipes
        """
        outputList = []

        # Register for client IDs from all appropriate pipe managers
        clientIds = {}
        if procPipeName is None:
            for pipeName in self.pipeClients.iterkeys():
                clientIds[pipeName] = self.registerForClientQueue(pipeName)

        else:
            clientIds[procPipeName] = self.registerForClientQueue(procPipeName)

        # Internal function to check whether we are done reading
        def checkComplete(self, clientIds):
            complete = True
            complete = complete and not self.is_alive()

            for pipeName, clientId in clientIds.iteritems():
                complete = complete and self.isQueueEmpty(pipeName, clientId)

            return complete

        # Main loop to pull everything off our queues
        while not checkComplete(self, clientIds):
            for pipeName, clientId in clientIds.iteritems():
                while True:
                    try:
                        line = self.getLineFromPipe(pipeName, clientId).rstrip('\n')
                        outputList.append(line)
                    except Empty:
                        break

            time.sleep(0.01)

        return outputList
