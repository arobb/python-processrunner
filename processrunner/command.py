# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import dict
from subprocess import PIPE, Popen
from multiprocessing import Process
from multiprocessing.managers import BaseManager

import codecs
import logging
import random
import signal
import time

from .kitchenpatch import getwriter

from . import settings
from .prpipewriter import _PrPipeWriter
from .prpipereader import _PrPipeReader
from .exceptionhandler import ProcessAlreadyStarted
from .exceptionhandler import ProcessNotStarted
from .exceptionhandler import Timeout
from .timer import Timer

# Private class only intended to be used by ProcessRunner
class _Command(object):
    """Custom wrapper for Popen that manages the interaction with Popen and any
    client objects that have requested output

    Runs in a separate process and is managed via multiprocessing.BaseManager,
    which provides proxy access to class methods

    """
    def __init__(self,
                 command,
                 cwd=None,
                 autostart=True,
                 std_queues=None,
                 log_name=None):
        """
        Args:
            command (list): List of strings to pass to subprocess.Popen
            cwd (string): Directory to change to before execution. Passed to
                subprocess.Popen
            autostart (bool): Whether to automatically start the target
                process or wait for the user to call start()
            stdin (pipe): File-like object to read from
        """
        # Unique ID
        self.id = \
            ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

        self._initializeLogging()

        # Identify this Command on the log feed
        self.log_name = log_name
        if self.log_name is not None:
            self._log.info("log_name is {}".format(self.log_name))

        self.started = False
        self.command = command
        self.cwd = cwd
        self.proc = None  # Will hold a Popen instance
        self.pipes = {
            'stdout': _PrPipeReader(queue=std_queues['stdout'],
                                    name='stdout',
                                    log_name=self.log_name),
            'stderr': _PrPipeReader(queue=std_queues['stderr'],
                                    name='stderr',
                                    log_name=self.log_name)
        }

        # Only create the stdin pipe entry if we've been asked to set up stdin
        self.stdin_handle = None
        if "stdin" in std_queues:
            self.enableStdin(queue=std_queues['stdin'])

        # Start running if we would like
        if autostart:
            self.start()

    def _initializeLogging(self):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Logging
        self._log = logging.getLogger("{}-{}".format(__name__, self.id))
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

    def enableStdin(self, queue):
        """Enable the stdin pipe"""
        self.pipes['stdin'] = _PrPipeWriter(queue=queue,
                                            name="stdin",
                                            log_name=self.log_name)

    def start(self):
        """Begin running the target process"""
        if self.started:
            message = "_Command.start called after process has started"
            self._log.info(message)
            raise ProcessAlreadyStarted(message)
        else:
            self._log.info("Starting the command")
            self.started = True

        # Start the process with subprocess.Popen
        # 1. stdout and stderr are captured via pipes
        # 2. Output from stdout and stderr buffered per line
        # 3. File handles are closed automatically when the process exits
        ON_POSIX = settings.config["ON_POSIX"]
        popenKwargs = {
            "stdout": PIPE,
            "stderr": PIPE,
            "universal_newlines": False,
            "bufsize": 1,  # Line buffered
            "close_fds": ON_POSIX,
            "cwd": self.cwd
        }

        if "stdin" in self.pipes:
            self.stdin_handle = PIPE
            popenKwargs['stdin'] = self.stdin_handle

        self.proc = Popen(self.command, **popenKwargs)

        # Init readers to transfer output from the Popen pipes to local queues
        wrappedStdout = codecs.getreader("utf-8")(self.proc.stdout)
        wrappedStderr = codecs.getreader("utf-8")(self.proc.stderr)
        self.pipes["stdout"].setPipeHandle(wrappedStdout)
        self.pipes["stderr"].setPipeHandle(wrappedStderr)

        if "stdin" in self.pipes:
            wrappedStdin = getwriter("utf-8")(self.proc.stdin)
            self.pipes["stdin"].setPipeHandle(wrappedStdin)

        return self.started

    def stop(self, timeout=0.5):
        """Attempt a graceful shutdown

        :argument string timeout: How long to wait for the process to exit in
                                  seconds
        """
        # Send a SIGINT to the process
        if self.isAlive():
            self._log.info("Process is running, sending SIGINT")
            self.send_signal(signal.SIGINT)

        t = Timer(timeout)
        while self.isAlive():
            self._log.info("Waiting for process to exit")
            time.sleep(0.001)

            # When we've crossed the timeout, terminate the process
            if t.interval():
                self._log.info("Process took too long, terminating after {}"
                               " seconds".format(timeout))
                self.terminate()

        # Send a shutdown request to all the pipes
        for pipe_name, pipe in self.pipes.items():
            self._log.debug("Stopping pipe manager for {}".format(pipe_name))
            pipe.stop()

    def send_signal(self, signal_value):
        """Send a signal to the process"""
        return self.proc.send_signal(signal_value)

    def getPipe(self, procPipeName):
        """Retrieve a _PrPipe manager instance by pipe name

        Args:
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            _PrPipe[Reader|Writer]

        Raises:
            KeyError
        """
        if procPipeName not in self.pipes:
            raise KeyError(procPipeName+" is not an available pipe")

        return self.pipes[procPipeName]

    def isQueueEmpty(self, procPipeName, clientId):
        """Check whether the _PrPipe* queues report empty for a given pipe
        and client

        Args:
            clientId (string): ID of the client queue
            procPipeName (string): One of "stdout" or  "stderr"

        Returns:
            bool
        """
        return self.getPipe(procPipeName).isEmpty(clientId)

    def areAllQueuesEmpty(self):
        """Check that all queues are empty

        A bit dangerous to use, will block if any client has stopped pulling
        from their queue. Better to use isQueueEmpty() for the dedicated
        client queue. Sometimes (especially externally) that's not possible.

        Returns:
            bool
        """
        empty = True

        for pipename, pipe in list(self.pipes.items()):
            self._log.info(pipename + " is " +
                           ("empty" if
                            pipe.isEmpty() is True else "not empty"))
            empty = empty and pipe.isEmpty()

        return empty

    def is_queue_alive(self, procPipeName):
        """Check if a queue is still running

        :arg string procPipeName: One of "stdout" or  "stderr"
        :return bool
        """
        return self.getPipe(procPipeName).is_alive()

    def is_queue_drained(self, procPipeName, clientId=None):
        """Check if a queue could contain data

        :arg string procPipeName: One of "stdout" or  "stderr"
        :return bool
        """
        return self.getPipe(procPipeName).is_drained(clientId=clientId)

    def isAlive(self):
        """Check whether the Popen process reports alive

        Returns:
            bool
        """
        if self.proc is None:
            state = False
        else:
            state = True if self.proc.poll() is None else False

        return state

    def poll(self):
        """Invoke the subprocess.Popen.poll() method

        Returns:
            NoneType, int. NoneType if alive, or int with exit code if dead
        """
        if self.proc is None:
            raise ProcessNotStarted("_Command.poll called before process "
                                    "started")
        else:
            return self.proc.poll()

    def wait(self, timeout=None):
        """Block until the process exits

        Does some extra checking to make sure the pipe managers have finished
        reading

        Args:
            requirePublishLock (bool): True to require a lock during the wait()
                loop. Can cause a deadlock if used with an outside call to
                publish(requireLock=True)

            timeout (float): Timeout in seconds

        Returns:
            None
        """
        if timeout is not None:
            timeout_obj = Timer(timeout * 1000)

        def isAliveLocal():
            # Force down any unprocessed messages
            # self.publish(requirePublishLock)
            alive = False

            # Iterate through the list of pipes
            for pipeName in list(self.pipes.keys()):
                pipe = self.getPipe(pipeName)

                # Skip writers
                if type(pipe) == _PrPipeWriter:
                    continue

                pipe_alive = pipe.is_alive()
                self._log.debug("Pipe {} is_alive is {}"
                                .format(pipeName, pipe_alive))

                # Check if the pipe is alive
                # Any pipe alive will cause us to return True
                alive = alive or pipe_alive

            return alive

        t = Timer(interval_ms=1000)
        while self.poll() is None or isAliveLocal() is True:
            if t.interval():
                self._log.debug("Waiting patiently: poll is {}, isAliveLocal"
                                " is {}".format(self.poll(), isAliveLocal()))

            # If we've reached the timeout, exit
            if timeout is not None:
                if timeout_obj.interval():
                    message = "wait() has timed out " \
                              "at {} seconds".format(timeout)
                    self._log.debug(message)
                    raise Timeout(message)

            time.sleep(0.01)

        return None

    def terminate(self):
        """Proxy call for Popen.terminate

        Returns:
            None
        """
        if self.proc is None:
            raise ProcessNotStarted("_Command.terminate called but process "
                                    "not started")

        return self.proc.terminate()

    def kill(self):
        """Proxy call for Popen.kill

        Returns:
            None
        """
        return self.proc.kill()

    def closeStdin(self):
        if self.proc.stdin.closed:
            self._log.debug("closeStdin called, but the stdin pipe"
                            " isn't available")
            return False

        """Close the stdin _PrPipeWriter by stopping the _PrPipe"""
        try:
            stdin = self.getPipe("stdin")
            stdin.stop()

        # Stdin isn't available
        except KeyError:
            self._log.debug("Close called, but the stdin pipe isn't available")

        self._log.debug("Closing the stdin pipe")
        self.proc.stdin.flush()
        self.proc.stdin.close()

        return True

    def registerClientQueue(self, procPipeName, queueProxy):
        """Register to get a client queue on a pipe manager

        The ID for the queue is returned from the method as a string

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            queueProxy (queueProxy): Proxy object to a Queue we should populate

        Returns:
            string Client queue ID, unique only when combined with procPipeName

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

    def getLineFromPipe(self, procPipeName, clientId, timeout=-1):
        """Retrieve a line from a pipe manager

        Throws Empty if no lines are available.

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager
            timeout (float): <0 for get_nowait behavior, otherwise use
                           get(timeout=timeout); in seconds; default -1

        Returns:
            string. Line from specified client queue

        Raises:
            Empty
        """
        line = self.getPipe(procPipeName).getLine(clientId=clientId,
                                                  timeout=timeout)
        return line

    def destructiveAudit(self):
        """Force one line of output each from attached pipes

        Used for debugging issues that might relate to data stuck in the
        queues. Triggers the pipes' destructiveAudit function which prints
        the last line of the queue or an 'empty' message.
        """
        for pipe in list(self.pipes.values()):
            pipe.destructiveAudit()
