# -*- coding: utf-8 -*-
"""Easily execute external processes"""
from __future__ import unicode_literals
from past.builtins import basestring
from builtins import str as text
from builtins import dict

import errno
import logging
import multiprocessing
import os
import random
import socket
import sys
import time
import traceback

from copy import deepcopy
from multiprocessing import Process, Event
from deprecated import deprecated

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from . import settings
from .timer import Timer
from .which import which
from .writeout import writeOut
from .commandmanager import _CommandManager
from .exceptionhandler import CommandNotFound
from .exceptionhandler import ProcessAlreadyStarted
from .exceptionhandler import ProcessNotStarted
from .exceptionhandler import ExceptionHandler
from .exceptionhandler import HandleNotSet
from .exceptionhandler import Timeout

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
                 stdin=None,
                 log_name=None):
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
        # Unique ID
        self.id = \
            ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

        self.log_name = log_name
        self._initializeLogging()
        log = self._log

        # Shared settings
        settings.init()
        settings.config["AUTHKEY"] = ''.join([random.choice('0123456789ABCDEF')
                                     for x in range(256)])
        settings.config["MAX_QUEUE_LENGTH"] = 0  # Maximum length for Queues
        settings.config["ON_POSIX"] = 'posix' in sys.builtin_module_names
        settings.config["NOTIFICATION_DELAY"] = 1  # Seconds for delay notices

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

        # Baseline multiprocessing.JoinableQueues
        # These act as a buffer between the actual pipes and one or more
        # client queues. The QueueLink moves messages between them.
        stdout_q = self.queueManager\
            .JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
        stderr_q = self.queueManager\
            .JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
        self.stdQueues = dict(stdout=stdout_q,
                              stderr=stderr_q)

        # Storage for multiprocessing.JoinableQueues started on behalf
        # of clients
        self.pipeClients = dict(stdout=dict(),
                                stderr=dict())
        self.pipeClientProcesses = dict(stdout=dict(),
                                        stderr=dict())
        # if self.stdin is not None:
        #     self.enableStdin()  # Comment out here, will happen in start()

        # Storage for file handles opened on behalf of users who want output
        # directed to files
        self.output_file_handles = dict()  # [file path] = handle

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
                                            std_queues=self.stdQueues,
                                            log_name=self.log_name)

        # If stdin requested, enable it
        if self.stdin is not None:
            self.enableStdin()

        # Register this ProcessRunner
        PROCESSRUNNER_PROCESSES.append(self)

        # Whether we've started the child mapLines processes
        self.mapLinesStarted = False

        # If we are connected to another instance, store a reference to
        # the next downstream process
        self.downstreamProcessRunner = None
        self.linkedWatcherProcess = None
        # self.stdin_stop_event = Event()  # Downstream stdin needs to watch

        # Event to help mapLines stop gracefully
        self.stop_event = Event()

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

        # Queues to watch dict("stdout":
        watch_queues = dict()

        if other.stdin is None:
            try:
                other.enableStdin()
            except ProcessAlreadyStarted:
                raise ProcessAlreadyStarted("Cannot chain downstream processes"
                                            " after they have started")

        stdin_clientId, stdin_q = other.registerForClientQueue("stdin")
        clientId = self._linkClientQueues("stdout", stdin_q)
        watch_queues["stdout"] = clientId

        self.downstreamProcessRunner = other

        # Start a watcher to close stdin when the local outputs drain
        linked_process_name = "LinkedWatcher-{}".format(self.id)
        proc = Process(target=self._linked_watcher,
                       name=linked_process_name,
                       kwargs={"run": self.run,
                               "downstream_pr": self.downstreamProcessRunner,
                               "out_queues": watch_queues})
        self.linkedWatcherProcess = proc

    @staticmethod
    def _linked_watcher(run, downstream_pr, out_queues):
        """Misnomer to better align with the correct section of the codebase.
        Watch the output process output(s). When they close and queues
        drain, close stdin on the downstream instance.

        :argument _Command run: The "run" variable
        :argument ProcessRunner downstream_pr: The linked PR instance
        :argument dict out_queues: dict("stdout": clientId, "stderr": clientId)
        """
        logger_name = "{}".format(__name__)
        log = logging.getLogger(logger_name)
        log.addHandler(logging.NullHandler())

        log.info("Starting linked watcher process")

        # Iterate through the list of provided "output" queues
        t = Timer(interval_ms=settings.config["NOTIFICATION_DELAY"] * 1000)
        while True:
            # Log whether we are still running
            if t.interval():
                log.debug("Linked watcher process still running")

            # Check if the main process is still running
            if run.isAlive():
                continue

            complete = True
            for procPipeName, clientId in list(out_queues.items()):

                # Check if the output queue still has data
                complete = complete and run.is_queue_drained(procPipeName,
                                                             clientId)

            # If we are complete, then close the linked stdin, then exit
            if complete:
                log.info("Linked watcher closing linked stdin")
                downstream_pr.closeStdin()

                log.info("Linked watcher process exiting")
                return

    def _initializeLogging(self):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Logger name
        log_name = "{}-{}".format(__name__, self.id)

        if self.log_name is not None:
            log_name = "{}.{}".format(log_name, self.log_name)

        # Logging
        self._log = logging.getLogger(log_name)
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

        elif self.run.get("started"):
            raise ProcessAlreadyStarted("Cannot enable stdin after the process"
                                        "has been started")

        # Queue for combined storage off the clients
        if "stdin" in self.stdQueues:
            raise KeyError("stdin already set")

        else:
            stdin_q = self.queueManager\
                .JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
            self.stdQueues['stdin'] = stdin_q

        # Dicts to hold any clients pushing to this process
        self.pipeClients['stdin'] = dict()
        self.pipeClientProcesses['stdin'] = dict()

        # Activate stdin
        self.run.enableStdin(queue=stdin_q)

        # Mark stdin "flag" enabled
        if self.stdin is None:
            self.stdin = True

    def closeStdin(self):
        """Proxy to call _Command.closeStdin"""
        if self.stdin is None:
            return

        try:
            self.run.closeStdin()

        except HandleNotSet:
            self._log.debug("Trying to close stdin, but the handle was never "
                           "set")

        except IOError:
            self._log.debug("Trying to close stdin, but the process has"
                            " already stopped")

    def start(self):
        """Pass through to _Command.start

        :raises exceptionhandler.ProcessAlreadyStarted"""

        # Make sure all mapLines watchers are started
        self.startMapLines()

        # Enable stdin
        if self.stdin is not None:
            try:
                self.enableStdin()
            except KeyError:
                self._log.debug("start method trying to enable stdin, but"
                                " it is already enabled")

        # Start the target process
        ret_val = self.run.start()

        return ret_val

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

    def wait(self, timeout=None):
        """Block until the Popen process exits

        Does some extra checking to make sure the pipe managers have finished
        reading

        :argument float timeout: Max time in seconds before raising Timeout

        TODO: Check if this will deadlock if clients aren't finished reading
        (may only be internal maplines)
        """
        self.startMapLines()

        try:
            self.run.wait(timeout=timeout)
        except Timeout as e:
            raise e

        # self._join()

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

        Runs `terminate` in case it hasn't already been run
        """
        # Tell mapLines to stop
        self.stop_event.set()

        # self.terminate()
        try:
            self._log.debug("Calling self.run.stop()")
            self.run.stop()
        except IOError:
            self._log.debug("Running shutdown on self.run.stop() but run is"
                            " already gone.")
        except EOFError:
            self._log.debug("Running shutdown on self.run.stop() but run is"
                            " already gone.")

        try:
            if self.stdin is not None:
                self.closeStdin()
        except HandleNotSet:
            pass  # If the handle wasn't set, this was a noop

        self.queueManager.shutdown()
        self.runManager.shutdown()

        # Close any output handles (see write method)
        for file_path, handle in list(self.output_file_handles.items()):
            self._log.debug("Closing handle for output file {}"
                            .format(file_path))
            handle.flush()
            handle.close()

        try:
            # Throws a ValueError if the process isn't in the list (why?)
            PROCESSRUNNER_PROCESSES.remove(self)
        except ValueError as e:
            self._log.debug("Exception during shutdown, removing from list: "
                            .format(e))
            ExceptionHandler(e)

    def registerForClientQueue(self, procPipeName):
        """Register to get a client queue on a pipe manager

        The ID for the queue is returned from the method as a string.

        Args:
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            string. Client's queue ID on this pipe
        """
        q = self.queueManager\
            .JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
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

        Returns:
            int
        """
        clientId = self.run.registerClientQueue(procPipeName, queue)
        self.pipeClients[procPipeName][clientId] = queue

        return clientId

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
        line = self.run.getLineFromPipe(procPipeName=procPipeName,
                                        clientId=clientId,
                                        timeout=timeout)
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

        Returns a multiprocessing.Event that can be used to monitor the status
        of the function. When the process is dead, the queues are empty, and
        all lines are processed, the Event will be set to True. This can be
        used as a blocking mechanism by functions invoking mapLines, by using
        Event.wait().

        Args:
            func (function): A function that takes one parameter, the line
                from the pipe
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            multiprocessing.Event
        """

        """
        This needs a re-think. With these moving to separate processes, 
        status in particular needs to be communicated back in a more consistent
        way.
        """
        clientId, clientQ = self.registerForClientQueue(procPipeName)
        complete = Event()
        self._log.info("Registering mapLines client {} for {}"
                       .format(clientId, procPipeName))

        def doWrite(run, func, complete, clientId, procPipeName, stop_event):
            logger_name = "{}.mapLines.{}".format(__name__, clientId)
            log = logging.getLogger(logger_name)
            log.addHandler(logging.NullHandler())
            log.info("Starting doWrite client {} for {}"
                     .format(clientId, procPipeName))

            try:
                # Continue while there MIGHT be data to read
                while run.isAlive() \
                        or not run.is_queue_drained(procPipeName, clientId):
                    log.debug("Trying to get line from {} for client {}"
                              .format(procPipeName, clientId))

                    # Continue while we KNOW THERE IS data to read
                    while True:
                        try:
                            line = run.getLineFromPipe(procPipeName,
                                                       clientId,
                                                       timeout=0.05)
                            log.debug("Writing line to user function")
                            func(line)
                        except Empty:
                            log.debug("No lines to get from {} for client {}"
                                      .format(procPipeName, clientId))
                            break

                        # Exit from the inner loop if the stop event is set
                        if stop_event.is_set():
                            break

                    # Exit from the inner loop if the stop event is set
                    if stop_event.is_set():
                        log.debug("Stopping doWrite")
                        break

            except Exception as e:
                log.warning("Caught exception: {}".format(e))
                ExceptionHandler(e)

            finally:
                log.info("Ending doWrite client {} for {}"
                         .format(clientId, procPipeName))

                try:
                    # This will throw an EOFError when the runManager has
                    # stopped already
                    run.unRegisterClientQueue(procPipeName, clientId)

                except EOFError:
                    log.debug("Caught EOFError while stopping doWrite for"
                              " client {} for {}"
                              .format(clientId, procPipeName))

                complete.set()

        # Name the process
        if self.log_name is not None:
            process_name = "mapLines-{}-{}".format(self.log_name,
                                                   procPipeName)
        else:
            process_name = "mapLines-{}".format(procPipeName)

        client = Process(target=doWrite,
                         name=process_name,
                         kwargs=dict(run=self.run,
                                     func=func,
                                     complete=complete,
                                     clientId=clientId,
                                     procPipeName=procPipeName,
                                     stop_event=self.stop_event))
        client.daemon = True

        # Store the process so it can potentially be re-joined
        self.pipeClientProcesses[procPipeName][text(clientId)] = client

        return complete

    # Eliminates a potential race condition in mapLines if two are started on
    #   the same pipe
    # All client queues are registered at the beginning of the call to
    #   mapLines, so we can now start the clients sequentially without any
    #   possible message loss
    def startMapLines(self, force=False):
        """Start mapLines child processes

        Triggered by wait(), so almost never needs to be called directly.
        """
        self._log.info("Starting mapLines")

        if self.mapLinesStarted is False or force is True:
            self.mapLinesStarted = True
            for pipeClientProcesses in list(self.pipeClientProcesses.values()):
                for client in list(pipeClientProcesses.values()):
                    client.start()

    def collectLines(self, procPipeName=None, timeout=None):
        """Retrieve output lines as a list for one or all pipes from the
        process. Will start the process if it is not already running!

        Kwargs:
            procPipeName (string): One of "stdout" or "stderr"
            timeout (float): Max length to stay in collectLines, raises Timeout

        Raises:
            ProcessRunner.Timeout

        Returns:
            list. List of strings that are the output lines from selected pipes
        """
        manager = multiprocessing.Manager()
        output_list = manager.list()  # Final list of lines to be returned
        complete_events_dict = dict()  # Dict of the "complete" Events from
                                       # mapLines

        # Count existing clients
        current_client_count = 0
        for pipe_name, client_dict in list(self.pipeClientProcesses.items()):
            # Skip inputs
            if pipe_name == "stdin":
                continue

            if len(client_dict) > 0:
                current_client_count += len(client_dict)

        # Warn if we've started with other clients attached; we can't reliably
        # get output from the process if output has started flowing to other
        # consumers.
        if self.run.get("started") and current_client_count > 0:
            self._log.warning("Other consumers are already attached and the"
                              " process has started. Some data may have"
                              " already been processed and will not be"
                              " available from this method.")

        # Function for mapLines to write into the shared list
        def to_output(line):
            output_list.append(line.rstrip('\n'))

        # Register for a map of each appropriate pipe manager
        if procPipeName is None:
            # Go through the list of available pipes
            for pipeName in list(self.pipeClients):

                # Skip input pipes
                if pipeName == "stdin":
                    continue

                # Register for the mapping
                complete_events_dict[pipeName] = self.mapLines(to_output,
                                                               pipeName)
                self._log.info("Registered {}".format(pipeName))

        else:
            # Register for the mapping if we were given a specific one
            complete_events_dict[procPipeName] = self.mapLines(to_output,
                                                               procPipeName)
            self._log.info("Registered {}".format(procPipeName))

        # Start the process if it hasn't been already
        if not self.run.get("started"):
            self.start()

        # Make sure this gets called again to trigger the maps we just added
        else:
            self.startMapLines(force=True)

        # Internal function to check whether we are done reading
        def checkComplete(log, events_dict):
            complete = True

            for pipe_name, complete_event in list(events_dict.items()):
                # Check if the mapLines have completed
                log.debug("Checking if {} client has finished"
                          .format(pipe_name))
                complete = complete and complete_event.is_set()

            log.debug("Process complete status: {}".format(complete))

            return complete

        # Main loop to check completeness
        interval_delay = settings.config["NOTIFICATION_DELAY"] * 1000
        timer = Timer(interval_ms=interval_delay)

        # Start timeout timer
        if timeout is not None:
            timeout_obj = Timer(timeout * 1000)

        while True:
            # Check for a timeout
            if timeout is not None:
                if timeout_obj.interval():
                    message = "collectLines() has timed out " \
                              "at {} seconds".format(timeout)
                    self._log.debug(message)
                    raise Timeout(message)

            # If everyone is complete, finish!
            if checkComplete(self._log, complete_events_dict):
                break

            # If not, wait a moment then check again
            else:
                # Let the user know what's happening if we're delayed
                if timer.interval():
                    self._log.info("Not complete for {:.1f} seconds"
                                   .format(timer.lap() / 1000))

                time.sleep(0.005)

        # Convert the ListProxy to a "real" list before returning it
        output_list_final = list(output_list)

        # Stop the Manager
        manager.shutdown()

        return output_list_final

    def write(self, file_path, procPipeName=None, append=False):
        """Specify a file to direct output from the process

        :argument string file_path: Path to a file that should receive output
        :argument string procPipeName: Outbound pipe to reference (stdout,
                                       stderr)
        :argument bool append: Whether to append to an existing file. Default
                               is to truncate the file

        :return ProcessRunner
        """
        file_path = os.path.abspath(file_path)

        # Open a file handle with or without truncation
        if append:
            file_handle = open(file_path, 'a')
            self._log.info("Opened for writing (append): {}".format(file_path))
        else:
            file_handle = open(file_path, 'w')
            file_handle.truncate()
            self._log.info("Opened for writing (truncate): {}"
                           .format(file_path))

        # Writer function
        func = writeOut(file_handle, outputPrefix="")

        # Generate a list of valid pipe names (e.g. skipping stdin)
        valid_names = list()
        for name in list(self.pipeClients.keys()):
            if name == "stdin":
                continue

            valid_names.append(name)

        # Register only for the requested pipe
        if procPipeName:
            if procPipeName not in valid_names:
                raise KeyError("{} is not a valid output pipe name. ({})"
                               .format(procPipeName, ", ".join(valid_names)))

            # Register to have lines written directly to the file
            self.mapLines(func, procPipeName)

        # Register for all available valid pipes
        else:
            for pipe_name in valid_names:
                self.mapLines(func, pipe_name)

        # Register the file handle in self.output_file_handles
        self.output_file_handles[file_path] = file_handle

        return self
