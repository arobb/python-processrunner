from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import logging
import os
import sys
import time

import multiprocessing
from multiprocessing import Process
from multiprocessing.managers import BaseManager

try:
    from Queue import Empty
except ImportError:
    from queue import Empty # python 3.x


# Configure a multiprocessing.BaseManager to allow for proxy access
#   to the _Command class.
# This allows us to decouple the main application process from
#   the process that runs Popen and publishes output from Popen
#   into the client queues.
class _CommandManager(BaseManager): pass
if sys.version_info[0] == 2:
    _CommandManager.register(str("_Command"), _Command) # MUST remain str()
elif sys.version_info[0] == 3 :
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
        self._initializeLogging()

        # Verify the command is a list of strings
        if not isinstance(command, list):
            raise TypeError("ProcessRunner command must be a list of strings. "
                            + text(type(command)) + " given.")

        for i, param in enumerate(command):
            if not isinstance(param, str):
                raise TypeError("ProcessRunner command must be a list of strings. "
                                +"Parameter {0} is {1}.".format(text(i), text(type(command))))

        # Verify the command exists
        if self.which(command[0]) is None:
            raise CommandNotFound(command[0] + " not found or not executable", command[0])

        # Place to store return code in case we stop the child process
        self.returncode = None

        # Process to run
        self.command = command

        # Multiprocessing instance used to start process-safe Queues
        self.manager = multiprocessing.Manager()

        # Storage for multiprocessing.Queues started on behalf of clients
        self.pipeClients = dict(stdout=dict(), stderr=dict())
        self.pipeClientProcesses = dict(stdout=dict(), stderr=dict())

        # Instantiate the Popen wrapper
        self.runManager = _CommandManager()
        self.runManager.start()

        # Trigger execution
        self.run = self.runManager._Command(command, cwd)

        # Register this ProcessRunner
        PROCESSRUNNER_PROCESSES.append(self)

        # Whether we've started the child mapLines processes
        self.mapLinesStarted = False


    def _initializeLogging(self):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Logging
        self._log = logging.getLogger(__name__)
        self.addLoggingHandler(logging.NullHandler())


    def addLoggingHandler(self, handler):
        self._log.addHandler(handler)


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
        return self.run.areAllQueuesEmpty

    def is_alive(self):
        """Check whether the Popen process reports alive

        Returns:
            bool
        """
        try:
            status = self.run.is_alive()
        except:
            status = False
        return status


    # @deprecated
    def isAlive(self):
        return self.is_alive()


    def poll(self):
        """Invoke the subprocess.Popen.poll() method

        Returns:
            None, int. NoneType if alive, or int with exit code if dead
        """
        try:
            self.returncode = self.run.poll()
            return self.returncode
        except Exception as e:
            pass

        return self.returncode


    def join(self):
        """Join any client processes, waiting for them to exit

        .wait() calls this, so not necessary to use separately
        """
        # Join the main command first
        self.run.join()

        # Join queue processes
        for procPipeName in list(self.pipeClientProcesses):
            for clientId, clientProcess in list(self.pipeClientProcesses[procPipeName].items()):
                self._log.debug("Joining " + procPipeName + " client " + text(clientId) + "...")
                self.pipeClientProcesses[procPipeName][text(clientId)].join()


    def wait(self):
        """Block until the Popen process exits

        Does some extra checking to make sure the pipe managers have finished reading
        """
        self.startMapLines()

        try:
            self.run.wait()
            self.join()
        except Exception as e:
            pass

        return self


    def terminate(self,timeoutMs=3000):
        """Terminate both the main process and reader queues.

        Args:
            timeoutMs (int): Milliseconds terminate should wait for main process
                             to exit before raising an error
        """
        # Kill the main process
        try:
            self.terminateCommand()
        except:
            pass

        # Timeout in case the process doesn't terminate
        timer=timeoutMs/1000
        interval=0.1
        while(timer>0 and self.is_alive()):
            timer = timer - interval
            time.sleep(interval)

        if self.is_alive():
            raise Exception("Main process has not terminated")

        # Kill the queues
        self.terminateQueues()


    def terminateQueues(self):
        """Clean up straggling processes that might still be running"""
        # Clean up readers
        for procPipeName in list(self.pipeClientProcesses):
            for clientId, clientProcess in list(self.pipeClientProcesses[procPipeName].items()):
                # Close any remaining client readers
                try:
                    self.pipeClientProcesses[procPipeName][text(clientId)].terminate()
                except Exception as e:
                    raise Exception(
                        "Exception closing "+procPipeName+" client "\
                        +text(clientId)+": "+text(e)+ \
                        ". Did you trigger startMapLines first?")
                # Remove references to client queues
                self.unRegisterClientQueue(procPipeName, clientId)


    def terminateCommand(self):
        """Send SIGTERM to the main process (the command)"""
        try:
            self.run.get("proc").terminate()
        except Exception as e:
            raise Exception("Exception terminating process: "+text(e))


    def killCommand(self):
        """Send SIGKILL to the main process (the command)"""
        try:
            self.run.get("proc").kill()
        except Exception as e:
            raise Exception("Exception killing process: "+text(e))


    def shutdown(self):
        """Shutdown the process managers. Run after verifying terminate/kill has
        destroyed any child processes"""
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

        if text(clientId) in self.pipeClientProcesses:
            self.pipeClientProcesses.pop(text(clientId))


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
        status = dict(complete=False)

        def doWrite(run, func, status, clientId, procPipeName):
            self._log.debug("Starting doWrite for " + procPipeName)

            try:
                # Continue while there MIGHT be data to read
                while run.is_alive() \
                  or not run.isQueueEmpty(procPipeName, clientId):
                    self._log.debug("might be data to read in " + procPipeName)

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

        client = Process(target=doWrite, kwargs=dict(run=self.run, func=func, status=status, clientId=clientId, procPipeName=procPipeName))
        client.daemon = True

        # Store the process so it can potentially be re-joined
        self.pipeClientProcesses[procPipeName][text(clientId)] = client

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
            for pipeClientProcesses in list(self.pipeClientProcesses.values()):
                for client in list(pipeClientProcesses.values()):
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
        clientIds = dict()
        if procPipeName is None:
            for pipeName in list(self.pipeClients):
                clientIds[pipeName] = self.registerForClientQueue(pipeName)

        else:
            clientIds[procPipeName] = self.registerForClientQueue(procPipeName)

        # Internal function to check whether we are done reading
        def checkComplete(self, clientIds):
            complete = True
            complete = complete and not self.is_alive()

            for pipeName, clientId in list(clientIds.items()):
                complete = complete and self.isQueueEmpty(pipeName, clientId)

            return complete

        # Main loop to pull everything off our queues
        while not checkComplete(self, clientIds):
            for pipeName, clientId in list(clientIds.items()):
                while True:
                    try:
                        line = self.getLineFromPipe(pipeName, clientId).rstrip('\n')
                        outputList.append(line)
                    except Empty:
                        break

            time.sleep(0.01)

        return outputList
