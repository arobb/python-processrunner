# -*- coding: utf-8 -*-
"""Easily execute external processes"""
from __future__ import unicode_literals
from past.builtins import basestring
from builtins import str as text
from builtins import dict

import errno
import logging
import random
import socket
import sys
import time
import traceback

import multiprocessing
from multiprocessing import Process
from deprecated import deprecated

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from . import settings
from .timer import Timer
from .which import which
from .commandmanager import _CommandManager
from .exceptionhandler import CommandNotFound
from .exceptionhandler import ProcessAlreadyStarted
from .exceptionhandler import ProcessNotStarted
from .exceptionhandler import ExceptionHandler
from .exceptionhandler import HandleNotSet

# Global values when using ProcessRunner
PROCESSRUNNER_PROCESSES = []  # Holding list for instances of ProcessRunner


def getActiveProcesses():
    """Retrieve a list of running processes started by ProcessRunner

    Returns:
        list. List of ProcessRunner instances
    """
    active = []

    for p in PROCESSRUNNER_PROCESSES:
        if p.is_alive():
            active.append(p)

    print("Active: {}".format(len(active)))

    return active


class ProcessRunner:
    """Easily execute external processes"""

    def __init__(self,
                 command,
                 cwd=None,
                 autostart=True,
                 stdin=None):
        """Easily execute external processes

        Can be used in a blocking or non-blocking manner
        Uses separate processes to monitor stdout and stderr of started
        processes

        Args:
            command (list): A list of strings, making up the command to pass
                to Popen
            cwd (string): Directory to change to before execution. Passed to
                subprocess.Popen
            autostart (bool): Whether to automatically start the target
                process or wait for the user to call start()
            stdin (pipe): File-like object to read from
        """
        self._initializeLogging()
        log = self._log

        # Shared settings
        settings.init()
        settings.config["AUTHKEY"] = ''.join([random.choice('0123456789ABCDEF')
                                              for x in range(256)])
        settings.config["MAX_QUEUE_LENGTH"] = 0  # Maximum length for Queues
        settings.config["ON_POSIX"] = 'posix' in sys.builtin_module_names

        # Verify the command is a list of strings
        # Throws a TypeError if this validation fails
        self.validateCommandFormat(command)

        # Verify the command exists
        if which(command[0]) is None:
            raise CommandNotFound(command[0] + " not found or not executable",
                                  command[0])

        # Place to store return code in case we stop the child process
        self.returncode = None

        # Process to run
        self.command = command
        self.cwd = cwd
        self.autostart = autostart
        self.stdin = stdin
        self.run = None  # Will hold the proxied _Command instance

        # Multiprocessing instance used to start process-safe Queues
        self.queueManager = multiprocessing.Manager()

        # Storage for multiprocessing.Queues started on behalf of clients
        self.pipeClients = dict(stdout=dict(),
                                stderr=dict())
        self.pipeClientProcesses = dict(stdout=dict(),
                                        stderr=dict())
        if self.stdin is not None:
            self.enableStdin()

        # Instantiate the Popen wrapper
        log.debug("Instantiating the command execution manager subprocess")
        authkey = text(settings.config["AUTHKEY"])
        self.runManager = _CommandManager(authkey=authkey.encode())
        self.runManager.start()

        # Trigger execution if autostart is True (trigger Popen)
        log.info("Prepping the command")
        self.run = self.runManager._Command(self.command,
                                            cwd=self.cwd,
                                            autostart=self.autostart,
                                            stdin=self.stdin)

        # Register this ProcessRunner
        PROCESSRUNNER_PROCESSES.append(self)

        # Whether we've started the child mapLines processes
        self.mapLinesStarted = False

        # If we are connected to another instance, store a reference to
        # the next downstream process
        self.downstreamProcessRunner = None

        # Separate process to constantly flush
        # self.flush_lock = Lock()
        # self.autoFlushProcess = Process(target=self._flusher,
        #                                 name="AUTO-FLUSH",
        #                                 kwargs={"run": self.run})
        # self.autoFlushProcess.daemon = True

        # if autostart:
        #     self.autoFlushProcess.start()

    def __enter__(self):
        """Support 'with' syntax
        """
        return self

    def __exit__(self, *exc_details):
        """Support 'with' syntax
        """
        self.shutdown()

    def __or__(self, other):
        """Support ProcessRunner chaining

        Use the OR syntax ProcessRunner | ProcessRunner to connect output of
        one ProcessRunner instance to another.
        """
        if type(other) != type(self):
            raise TypeError("Cannot OR {} with {}".format(type(other),
                                                          type(self)))

        if other.stdin is None:
            try:
                other.enableStdin()
            except ProcessAlreadyStarted:
                raise ProcessAlreadyStarted("Cannot chain downstream processes"
                                            " after they have started")

        stdin_clientId, stdin_q = other.registerForClientQueue("stdin")
        self._linkClientQueues("stdout", stdin_q)

        self.downstreamProcessRunner = other

    def _initializeLogging(self):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Logging
        self._log = logging.getLogger(__name__)
        self.addLoggingHandler(logging.NullHandler())

    def addLoggingHandler(self, handler):
        """Pass-through for Logging's addHandler method"""
        self._log.addHandler(handler)

    def getCommand(self):
        """Retrieve the command list

        Returns:
            list. The list of strings passed to Popen
        """
        return self.command

    def validateCommandFormat(self, command):
        """Run validation against the command list argument

        Used for validation by ProcessRunner.__init__"""
        self._log.debug("Command as provided (commas separating parts): {}"
                        .format(", ".join(command)))
        self._log.debug("Validating command list")

        # Verify the command is a list
        if not isinstance(command, list):
            raise TypeError("ProcessRunner command must be a list of strings. "
                            + text(type(command)) + " given.")

        # Verify each part is a string
        if sys.version_info[0] == 2:
            stringComparator = basestring
        elif sys.version_info[0] == 3:
            stringComparator = str

        for i, param in enumerate(command):
            if not isinstance(param, stringComparator):
                raise TypeError(
                    "ProcessRunner command must be a list of strings. "
                    + "Parameter {0} is {1}.".format(text(i),
                                                     text(type(command))))

        # It's valid if we got this far
        return True

    def enableStdin(self):
        """Enable stdin on the target process before the process has started"""
        if self.run is None:
            pass

        elif not self.run.get("started"):
            self.run.enableStdin()

        elif self.run.get("started"):
            raise ProcessAlreadyStarted("Cannot enable stdin after the process"
                                        "has been started")

        if self.stdin is None:
            self.stdin = True

        self.pipeClients['stdin'] = dict()
        self.pipeClientProcesses['stdin'] = dict()

    def start(self):
        """Pass through to _Command.start

        :raises exceptionhandler.ProcessAlreadyStarted"""

        # Make sure all mapLines watchers are started
        self.startMapLines()

        # Start the flusher process
        # self.autoFlushProcess.start()

        return self.run.start()

    # def _flusher(self, run):
    #     """Runs automatically in a subprocess to flush new messages
    #     """
    #     timer = Timer(5000)
    #
    #     while True:
    #         try:
    #             if timer.interval():
    #                 self._log.warning("Flusher still running")
    #
    #             if run.get("started"):
    #                 run.publish(requireLock=False)
    #
    #         # https://stackoverflow.com/a/34718439
    #         except (socket.error, IOError) as e:
    #             if e.errno != errno.EPIPE:
    #                 # Not a broken pipe
    #                 raise
    #
    #             self._log.info("Flush received a BrokenPipeError. The command "
    #                            "has likely completed.")
    #
    #         except EOFError as e:
    #             self._log.info("Flush received an EOFError. The command "
    #                            "has likely completed.")
    #
    #         finally:
    #             time.sleep(0.1)

    # def flush(self):
    #     """Force publishing of any pending messages on attached pipes
    #
    #     This will run in a loop until areAllQueuesEmpty() reports True.
    #
    #     If this ProcessRunner instance has been piped to a downstream instance,
    #     flush() will also flush the downstream instance.
    #     """
    #     locked = self.flush_lock.acquire(block=False)
    #     if not locked:
    #         # self._log.debug("Flush did not acquire a lock:")
    #         # for line in traceback.format_stack():
    #         #     self._log.debug(line.strip())
    #         return
    #
    #     try:
    #         timer = Timer(5000)
    #         while not self.areAllQueuesEmpty():
    #             if timer.interval():
    #                 self._log.warning("Flusher still running")
    #
    #             self._publish(requireLock=False)
    #
    #             if self.downstreamProcessRunner is not None:
    #                 self.downstreamProcessRunner.flush()
    #
    #     # https://stackoverflow.com/a/34718439
    #     except (socket.error, IOError) as e:
    #         if e.errno != errno.EPIPE:
    #             # Not a broken pipe
    #             raise
    #
    #         self._log.info("Flush received a BrokenPipeError. The command "
    #                        "has likely completed.")
    #
    #     except EOFError as e:
    #         self._log.info("Flush received an EOFError. The command "
    #                        "has likely completed.")
    #
    #     finally:
    #         if locked:
    #             self.flush_lock.release()

    def _publish(self, requireLock):
        """Force publishing of any pending messages on attached pipes

        requireLock (bool): True to require a lock. Can deadlock. See
            _PrPipeReader.publish for more details.
        """
        self.run.publish(requireLock=requireLock)

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

        A bit dangerous to use, will block if any client has stopped pulling
        from their queue. Better to use isQueueEmpty() for the dedicated client
        queue. Sometimes (especially externally) that's not possible.

        Returns:
            bool
        """
        return self.run.areAllQueuesEmpty()

    def isAlive(self):
        """Check whether the Popen process reports alive

        Returns:
            bool
        """
        return self.run.isAlive()

    def poll(self):
        """Invoke the subprocess.Popen.poll() method

        Returns:
            None, int. NoneType if alive, or int with exit code if dead
        """
        try:
            self.returncode = self.run.poll()
            return self.returncode
        except Exception as e:
            raise e

    @deprecated
    def join(self):
        self._join()

    def _join(self):
        """Join any client processes, waiting for them to exit

        .wait() calls this, so not necessary to use separately
        """

        # Join queue processes
        timeout = 1
        for procPipeName in list(self.pipeClientProcesses):
            for clientId, clientProcess in \
                    list(self.pipeClientProcesses[procPipeName].items()):
                self._log.debug(
                    "Joining {} client {}...".format(procPipeName,
                                                     text(clientId)))
                self.pipeClientProcesses[procPipeName][text(clientId)]\
                    .join(timeout=timeout)
                exitcode = \
                    self.pipeClientProcesses[procPipeName][text(clientId)]\
                        .exitcode

                # If a join timeout occurs, try again
                while exitcode is None:
                    self._log.info("Joining {} client {} timed out".
                                   format(procPipeName, text(clientId)))
                    self.pipeClientProcesses[procPipeName][text(clientId)]\
                        .join(timeout=timeout)
                    exitcode = \
                        self.pipeClientProcesses[procPipeName][text(clientId)]\
                            .exitcode

    def closeStdin(self):
        """Proxy to call _Command.closeStdin"""
        try:
            self.run.closeStdin()

        except HandleNotSet:
            self._log.debug("Trying to close stdin, but the handle was never "
                           "set")

    def wait(self):
        """Block until the Popen process exits

        Does some extra checking to make sure the pipe managers have finished
        reading

        TODO: Check if this will deadlock if clients aren't finished reading
        (may only be internal maplines)
        """
        self.startMapLines()
        self.run.wait()
        self._join()

        return self

    def terminate(self, timeoutMs=3000):
        """Terminate both the target process (the command) and reader queues.

        Use terminate to gracefully stop the target process (the command) and
        readers once you're done reading. Use `shutdown` if you are just
        trying to clean up, as it will trigger `terminate`.

        Args:
            timeoutMs (int): Milliseconds terminate should wait for main
                process to exit before raising an error
        """
        # Close the stdin pipe
        if self.stdin is not None:
            self.closeStdin()

        # Kill the main process
        self.terminateCommand()

        # Timeout in case the process doesn't terminate
        timer = timeoutMs / 1000
        interval = 0.1
        while timer > 0 and self.isAlive():
            timer = timer - interval
            time.sleep(interval)

        if self.isAlive():
            raise Exception("Main process has not terminated")

        # Kill the queues
        self._terminateQueues()

    def _terminateQueues(self):
        """Clean up straggling processes that might still be running.

        Run once you've finished reading from the queues.
        """
        # Clean up readers
        for procPipeName in list(self.pipeClientProcesses):
            for clientId, clientProcess in \
                    list(self.pipeClientProcesses[procPipeName].items()):

                # Close any remaining client readers
                try:
                    clientProcess.terminate()

                except Exception as e:
                    raise Exception(
                        "Exception closing " + procPipeName + " client "
                        + text(clientId) + ": " + text(e) +
                        ". Did you trigger startMapLines first?")

                # Remove references to client queues
                self.unRegisterClientQueue(procPipeName, clientId)

    def terminateCommand(self):
        """Send SIGTERM to the main process (the command)"""
        try:
            self.run.terminate()

        except OSError as e:
            # 3 is "No such process", which probably means the process is
            # already terminated
            if e.errno == 3:
                pass
            else:
                raise e

        except ProcessNotStarted:
            self._log.warning("ProcessRunner.terminateCommand called without "
                              "the target process being instantiated")

        except Exception as e:
            ExceptionHandler(e)
            raise e

    def killCommand(self):
        """Send SIGKILL to the main process (the command)"""
        return self.run.kill()

    def shutdown(self):
        """Shutdown the process managers. Run after verifying terminate/kill
        has destroyed any child processes

        Runs `terminate` in case it hasn't already been run"""
        self.terminate()

        try:
            self.closeStdin()
        except HandleNotSet:
            pass  # If the handle wasn't set, this was a noop

        self.queueManager.shutdown()
        self.runManager.shutdown()

        PROCESSRUNNER_PROCESSES.remove(self)

    def registerForClientQueue(self, procPipeName):
        """Register to get a client queue on a pipe manager

        The ID for the queue is returned from the method as a string.

        Args:
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            string. Client's queue ID on this pipe
        """
        q = self.queueManager.Queue(settings.config["MAX_QUEUE_LENGTH"])
        clientId = self.run.registerClientQueue(procPipeName, q)
        self.pipeClients[procPipeName][clientId] = q

        return clientId, q

    def _linkClientQueues(self, procPipeName, queue):
        """Connect an existing registerForClientQueue queue to another queue

        Use an existing queue from registerForClientQueue and connect
        it to another queue. Used for process chaining, connecting stdout
        or stderr of one process to the stdin of the next.

        Args:
            queue (Queue proxy)
        """
        clientId = self.run.registerClientQueue(procPipeName, queue)
        self.pipeClients[procPipeName][clientId] = queue

    def unRegisterClientQueue(self, procPipeName, clientId):
        """Unregister a client queue from a pipe manager

        Keeps other clients from waiting on other clients that will never be
        read.

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

        Used for debugging issues that might relate to data stuck in the
        queues.  Triggers the pipes' destructiveAudit function which prints
        the last line of the queue or an 'empty' message.
        """
        return self.run.destructiveAudit()

    def mapLines(self, func, procPipeName):
        """Run a function against each line presented by one pipe manager

        Returns a reference to a dict that can be used to monitor the status of
        the function. When the process is dead, the queues are empty, and all
        lines are processed, the dict will be updated. This can be used as a
        blocking mechanism by functions invoking mapLines.
        Status dict format: {"complete":bool}

        Args:
            func (function): A function that takes one parameter, the line
                from the pipe
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            dict
        """

        """
        This needs a re-think. With these moving to separate processes, 
        status in particular needs to be communicated back in a more consistent
        way.
        """
        clientId, clientQ = self.registerForClientQueue(procPipeName)
        status = dict(complete=False)

        def doWrite(run, func, status, clientId, procPipeName):
            self._log.info("Starting doWrite for " + procPipeName)

            try:
                # Continue while there MIGHT be data to read
                while run.isAlive() \
                        or not run.isQueueEmpty(procPipeName, clientId):
                    self._log.debug(0, "might be data to read in " + procPipeName)

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

        client = Process(target=doWrite,
                         name="mapLines-{}".format(procPipeName),
                         kwargs=dict(run=self.run,
                                     func=func,
                                     status=status,
                                     clientId=clientId,
                                     procPipeName=procPipeName))
        client.daemon = True

        # Store the process so it can potentially be re-joined
        self.pipeClientProcesses[procPipeName][text(clientId)] = client

        return status

    # Eliminates a potential race condition in mapLines if two are started on
    #   the same pipe
    # All client queues are registered at the beginning of the call to
    #   mapLines, so we can now start the clients sequentially without any
    #   possible message loss
    def startMapLines(self):
        """Start mapLines child processes

        Triggered by wait(), so almost never needs to be called directly.
        """
        if self.mapLinesStarted is False:
            self.mapLinesStarted = True
            for pipeClientProcesses in list(self.pipeClientProcesses.values()):
                for client in list(pipeClientProcesses.values()):
                    client.start()

    def collectLines(self, procPipeName=None):
        """Retrieve output lines as a list for one or all pipes from the
        process

        Kwargs:
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            list. List of strings that are the output lines from selected pipes
        """
        outputList = []

        if not self.run.get("started"):
            raise ProcessNotStarted("Target command hasn't started yet; please"
                                    " call ProcessRunner.start() to start the "
                                    "target process")

        # Register for client IDs from all appropriate pipe managers
        clientIds = dict()
        if procPipeName is None:
            for pipeName in list(self.pipeClients):
                clientIds[pipeName], q = self.registerForClientQueue(pipeName)
                self._log.debug("Registered {} for client {}"
                                .format(pipeName, clientIds[pipeName]))

        else:
            clientIds[procPipeName], q = \
                self.registerForClientQueue(procPipeName)

            self._log.debug("Registered {} for client {}"
                            .format(procPipeName, clientIds[procPipeName]))

        # Internal function to check whether we are done reading
        def checkComplete(self, clientIds):
            complete = True

            # Incorporate status of target process
            # Target process alive:
            #   complete = True & !(True) == True & False == False
            # Target process stopped:
            #   complete = True & !(False) == True & True == True
            complete = complete and not self.isAlive()  # True & !

            for pipeName, clientId in list(clientIds.items()):
                # Check status of queues
                # Target alive, queues w content:
                #   complete = False & False == False
                # Target alive, queues empty:
                #   complete = False & True == False
                # Target stopped, queues w content:
                #   complete = True & False == False
                # Target stopped, queues empty:
                #   complete = True & True == True
                complete = complete and self.isQueueEmpty(pipeName, clientId)

            self._log.debug("Process complete status: {}".format(complete))

            return complete

        # Main loop to pull everything off our queues
        while not checkComplete(self, clientIds):
            for pipeName, clientId in list(clientIds.items()):
                while True:
                    try:
                        line = self.getLineFromPipe(pipeName, clientId) \
                            .rstrip('\n')
                        outputList.append(line)
                    except Empty:
                        break

            time.sleep(0.01)

        return outputList
