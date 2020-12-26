# -*- coding: utf-8 -*-
from builtins import str as text
from builtins import dict
from subprocess import PIPE, Popen

import logging
import time

from . import settings
from .prpipe import _PrPipe


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
        self._initializeLogging()

        self.command = command

        # Start the process with subprocess.Popen
        # 1. stdout and stderr are captured via pipes
        # 2. Output from stdout and stderr buffered per line
        # 3. File handles are closed automatically when the process exits
        ON_POSIX = settings.config["ON_POSIX"]
        self.proc = Popen(self.command, stdout=PIPE, stderr=PIPE, bufsize=1, close_fds=ON_POSIX, cwd=cwd)

        # Initialize readers to transfer output from the Popen pipes to local queues
        self.pipes = dict(stdout=_PrPipe(self.proc.stdout), stderr=_PrPipe(self.proc.stderr))


    def _initializeLogging(self):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Logging
        self._log = logging.getLogger(__name__)
        self.addLoggingHandler(logging.NullHandler())


    def addLoggingHandler(self, handler):
        self._log.addHandler(handler)


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
        """Retrieve a _PrPipe manager instance by pipe name

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
        for pipe in list(self.pipes.values()):
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


    @property
    def areAllQueuesEmpty(self):
        """Check that all queues are empty

        A bit dangerous to use, will block if any client has stopped pulling from
        their queue. Better to use isQueueEmpty() for the dedicated client queue.
        Sometimes (especially externally) that's not possible.

        Returns:
            bool
        """
        empty = True

        for pipename, pipe in list(self.pipes.items()):
            self._log.info(pipename + " is " + ("empty" if pipe.isEmpty() == True else "not empty"))
            empty = empty and pipe.isEmpty()

        return empty


    def isAlive(self):
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
            for pipe in list(self.pipes.values()):
                alive = alive or pipe.is_alive()
            return alive

        while self.poll() is None or isAliveLocal() is True:
            time.sleep(0.01)

        return None


    def terminate(self):
        """Proxy call for Popen.terminate

        Returns:
            None
        """
        return self.proc.terminate()


    def kill(self):
        """Proxy call for Popen.kill

        Returns:
            None
        """
        return self.proc.kill()


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
        for pipe in list(self.pipes.values()):
            pipe.destructiveAudit()
