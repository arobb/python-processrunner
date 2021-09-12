# -*- coding: utf-8 -*-
"""Easily execute external processes"""
# pylint: disable=too-many-lines
from __future__ import unicode_literals

import logging
import multiprocessing
import os
import random
import sys
import time
from builtins import dict
from builtins import str as text
from multiprocessing import Event

from deprecated import deprecated
from past.builtins import basestring

try:  # Python 2.7
    from Queue import Empty
    from multiprocessing import Process
except ImportError:  # Python 3.x
    from queue import Empty
    Process = multiprocessing.get_context("fork").Process

from . import settings
from .classtemplate import PRTemplate
from .priterator import PrIterator
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
from .exceptionhandler import PotentialDataLoss

# Global values when using ProcessRunner
PROCESSRUNNER_PROCESSES = []  # Holding list for instances of ProcessRunner


def getActiveProcesses():
    """Retrieve a list of running processes started by ProcessRunner

    Returns:
        list. List of ProcessRunner instances
    """
    active = []

    for proc in PROCESSRUNNER_PROCESSES:
        if proc.is_alive():
            active.append(proc)

    print("Active: {}".format(len(active)))

    return active


# TODO: Rationalize the terminate/shutdown methods
class ProcessRunner(PRTemplate):
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
            log_name (string): Additional label to use in log records
        """
        # Unique ID
        # Not used for cryptographic purposes, so excluding from Bandit
        self.id = \
            ''.join([random.choice(  # nosec
                '0123456789ABCDEF') for x in range(6)])

        self.log_name = log_name
        self._initialize_logging_with_log_name(__name__)
        log = self._log

        # Shared settings
        settings.init()
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

        # Placeholders for iterable versions
        self.iterators = dict(output=None,  # Combination of stdout and stderr
                              stdout=None,
                              stderr=None)

        # Multiprocessing instance used to start process-safe Queues
        self.queue_manager = multiprocessing.Manager()

        # Baseline multiprocessing.JoinableQueues
        # These act as a buffer between the actual pipes and one or more
        # client queues. The QueueLink moves messages between them.
        stdout_q = self.queue_manager\
            .JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
        stderr_q = self.queue_manager\
            .JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
        self.std_queues = dict(stdout=stdout_q,
                               stderr=stderr_q)

        # Storage for multiprocessing.JoinableQueues started on behalf
        # of clients
        self.pipe_clients = dict(stdout=dict(),
                                 stderr=dict())
        self.pipe_clients_complete_events = dict(stdout=dict(),
                                                 stderr=dict())
        self.pipe_client_processes = dict(stdout=dict(),
                                          stderr=dict())

        # Storage for file handles opened on behalf of users who want output
        # directed to files
        self.output_file_handles = dict()  # [file path] = handle

        # Instantiate the Popen wrapper
        log.debug("Instantiating the command execution manager subprocess")
        self.run_manager = _CommandManager()
        self.run_manager.start()  # pylint: disable=consider-using-with

        # Trigger execution if autostart is True (trigger Popen)
        # _Command is added dynamically. pylint: disable=no-member
        log.info("Prepping the command")
        self.run = self.run_manager._Command(self.command,
                                             cwd=self.cwd,
                                             autostart=self.autostart,
                                             std_queues=self.std_queues,
                                             log_name=self.log_name,
                                             global_config=settings.config)

        # If stdin requested, enable it
        if self.stdin is not None:
            self.enableStdin()

        # Register this ProcessRunner
        PROCESSRUNNER_PROCESSES.append(self)

        # Whether we've started the child mapLines processes
        self.map_lines_started = False

        # If we are connected to another instance, store a reference to
        # the next downstream process
        self.downstream_processrunner = None
        self.linked_watcher_process = None

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

    def __getattr__(self, item):
        # Create iterator for stdout, stderr, and combined ("output")
        if item not in ['stdout', 'stderr', 'output']:
            message = "{} object as no attribute '{}'".format(__name__, item)
            raise AttributeError(message)

        # Get a list proxy for one or both outbound pipes
        if self.iterators[item] is None:
            if item == 'output':
                client_count = self.getClientCount()
                output, event = self.getExpandingList()
            else:
                client_count = self.getClientCount(item)
                output, event = self.getExpandingList(item)

            # Warn the user about potential loss
            if self.started() and client_count > 0:
                pipe_name = "stdout and stderr" if item == "output" else item

                self._log.warning("Potential for missing lines from %s! Other"
                                  " consumers are already attached and the"
                                  " process has started. Some data may have"
                                  " already been processed and will not be"
                                  " available from this method.", pipe_name)

            # Create an iterator over the list proxy and complete event
            iterator = PrIterator(output, event)
            self.iterators[item] = iterator

        return self.iterators[item]

    def __or__(self, other):
        """Support ProcessRunner chaining

        Use the OR syntax ProcessRunner | ProcessRunner to connect output of
        one ProcessRunner instance to another.
        """
        # if type(other) != type(self):
        if not isinstance(other, self.__class__):
            raise TypeError("Cannot OR {} with {}".format(type(other),
                                                          type(self)))

        # Queues to watch dict("stdout":
        watch_queues = dict()

        if other.stdin is None:
            try:
                other.enableStdin()
            except ProcessAlreadyStarted:
                message = "Cannot chain downstream processes after they " \
                          "have started"
                # pylint: disable=raise-missing-from
                raise ProcessAlreadyStarted(message)
                # pylint: enable=raise-missing-from

        stdin_clientid, stdin_q = other \
            .registerForClientQueue("stdin")  # pylint: disable=unused-variable
        clientid = self._link_client_queues("stdout", stdin_q)
        watch_queues["stdout"] = clientid

        self.downstream_processrunner = other

        # Start a watcher to close stdin when the local outputs drain
        linked_process_name = "LinkedWatcher-{}".format(self.id)
        proc = Process(target=self._linked_watcher,
                       name=linked_process_name,
                       kwargs={"run": self.run,
                               "downstream_pr": self.downstream_processrunner,
                               "out_queues": watch_queues})
        self.linked_watcher_process = proc

    @staticmethod
    def _linked_watcher(run, downstream_pr, out_queues):
        """Misnomer to better align with the correct section of the codebase.
        Watch the output process output(s). When they close and queues
        drain, close stdin on the downstream instance.

        Args:
            run (_Command): The "run" variable
            downstream_pr (ProcessRunner): The linked PR instance
            out_queues (dict): dict("stdout": clientId, "stderr": clientId)
        """
        logger_name = "{}".format(__name__)
        log = logging.getLogger(logger_name)
        log.addHandler(logging.NullHandler())

        log.info("Starting linked watcher process")

        # Iterate through the list of provided "output" queues
        notify_timer = Timer(interval=settings.config["NOTIFICATION_DELAY"])
        while True:
            # Log whether we are still running
            if notify_timer.interval():
                log.debug("Linked watcher process still running")

            # Check if the main process is still running
            if run.is_alive():
                continue

            complete = True
            for proc_pipe_name, client_id in list(out_queues.items()):

                # Check if the output queue still has data
                complete = complete and run.is_queue_drained(proc_pipe_name,
                                                             client_id)

            # If we are complete, then close the linked stdin, then exit
            if complete:
                log.info("Linked watcher closing linked stdin")
                downstream_pr.closeStdin()

                log.info("Linked watcher process exiting")
                return

    def getCommand(self):
        """Retrieve the command list originally passed in

        Returns:
            list: The list of strings passed to Popen
        """
        return self.command

    def validateCommandFormat(self, command):
        """Run validation against the command list argument

        Used for validation by ProcessRunner.__init__

        Args:
            command (list): A list of strings

        Returns:
            bool: Whether the command list is valid
        """
        self._log.debug("Command as provided (commas separating parts): %s",
                        ", ".join(command))
        self._log.debug("Validating command list")

        # Verify the command is a list
        if not isinstance(command, list):
            raise TypeError("ProcessRunner command must be a list of strings. "
                            + text(type(command)) + " given.")

        # Verify each part is a string
        if sys.version_info[0] == 2:
            string_comparator = basestring
        elif sys.version_info[0] == 3:
            string_comparator = str

        for i, param in enumerate(command):
            if not isinstance(param, string_comparator):
                raise TypeError(
                    "ProcessRunner command must be a list of strings. "
                    + "Parameter {0} is {1}.".format(text(i),
                                                     text(type(command))))

        # It's valid if we got this far
        return True

    def enableStdin(self):
        """Use to open the stdin pipe before starting the command

        Raises:
            KeyError: Stdin has already been enabled
            ProcessAlreadyStarted: Stdin cannot be enabled at this point
                because the command has already started
        """
        if self.run is None:
            pass

        elif self.run.get("started"):
            raise ProcessAlreadyStarted("Cannot enable stdin after the process"
                                        "has been started")

        # Queue for combined storage off the clients
        if "stdin" in self.std_queues:  # pylint: disable=no-else-raise
            raise KeyError("stdin already set")

        else:
            stdin_q = self.queue_manager\
                .JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
            self.std_queues['stdin'] = stdin_q

        # Dicts to hold any clients pushing to this process
        self.pipe_clients['stdin'] = dict()
        self.pipe_client_processes['stdin'] = dict()

        # Activate stdin
        self.run.enable_stdin(queue=stdin_q)

        # Mark stdin "flag" enabled
        if self.stdin is None:
            self.stdin = True

    def closeStdin(self):
        """Close the stdin pipe"""
        if self.stdin is None:
            return

        try:
            self.run.close_stdin()

        except HandleNotSet:
            self._log.debug("Trying to close stdin, but the handle was never "
                            "set")

        except IOError:
            self._log.debug("Trying to close stdin, but the process has"
                            " already stopped")

    def start(self):
        """Start the process

        Use when setting ``autostart=False`` to run the target command.

        DO NOT use when ``autostart=True`` (the default), as this will raise a
        :exc:`ProcessAlreadyStarted` exception.

        Raises:
            ProcessAlreadyStarted: The command has already been started

        Returns:
            ProcessRunner: Supports method chaining
        """

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
        self.run.start()

        return self

    def started(self):
        """Whether the command has started

        Returns:
            bool: Whether the command has been started
        """
        return self.run.get("started")

    def isQueueEmpty(self, procPipeName, clientId):
        """Check whether the pipe manager queues report empty

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager

        Returns:
            bool: True if the queue(s) is/are empty
        """
        return self.run.is_queue_empty(procPipeName, clientId)

    def areAllQueuesEmpty(self):
        """Check that all queues are empty

        A bit dangerous to use, will block if any client has stopped pulling
        from their queue. Better to use isQueueEmpty() for the dedicated client
        queue. Sometimes (especially externally) that's not possible.

        Returns:
            bool: True if all queues are empty
        """
        return self.run.are_all_queues_empty()

    def isAlive(self):
        """Check whether the Popen process reports alive

        Returns:
            bool: True if the command is still running
        """
        return self.run.is_alive()

    def poll(self):
        """Invoke the subprocess.Popen.poll() method

        Returns:
            Type depends on the status of the command

            - None: If the command is still running
            - int: Exit code of the command once stopped
        """
        try:
            self.returncode = self.run.poll()
            return self.returncode
        except Exception as exc:
            raise exc

    @deprecated
    def join(self):
        """Deprecated"""
        self._join()

    def _join(self):
        """Join any client processes, waiting for them to exit

        .wait() calls this, so not necessary to use separately
        """

        # Iterate over the set of named pipes
        timeout = 1
        for proc_pipe_name in list(self.pipe_client_processes):

            # Iterate over running queue clients
            for client_id, client_process in \
                    list(self.pipe_client_processes[proc_pipe_name].items()):
                client_id = text(client_id)
                self._log.debug(
                    "Joining %s client %s..", proc_pipe_name, client_id)
                client_process.join(timeout=timeout)
                exitcode = client_process.exitcode

                # If a join timeout occurs, try again
                while exitcode is None:
                    self._log.info("Joining %s client %s timed out",
                                   proc_pipe_name, client_id)
                    client_process.join(timeout=timeout)
                    exitcode = client_process.exitcode

    def wait(self, timeout=None):
        """Block until the Popen process exits and reader queues are drained

        Does some extra checking to make sure the pipe managers have finished
        reading, and consumers have read off all consumer queues.

        Supports a timeout argument to handle unexpected delays.

        Args:
            timeout (float): Max time in seconds before raising :exc:`Timeout`

        Raises:
            Timeout: When the command has run longer than ``timeout``

        Returns:
            ProcessRunner: Supports method chaining
        """
        # TODO: Check if this will deadlock if clients aren't finished
        #  reading (may only be internal maplines)
        self.startMapLines()
        local_wait_timer = Timer(timeout)

        # Check the _Command wait
        self.run.wait(timeout=timeout)

        self._log.info("Process complete, starting wait for consumers")
        interval_timer = Timer(settings.config["NOTIFICATION_DELAY"])

        # Check the mapLines complete events
        def check_complete(ctx, timer):
            log_flag = timer.interval()
            complete = True

            # Iterate through the list of pipes
            for pipe_name, clients in ctx.pipe_clients_complete_events.items():

                # Iterate through the list of clients in each pipe
                for client_id, client_complete in clients.items():
                    client_complete_bool = client_complete.is_set()
                    complete = complete and client_complete_bool

                    # Let the user know when we're "stuck" here
                    if log_flag:
                        ctx._log.info("%s client %s is %s",
                                      pipe_name,
                                      client_id,
                                      client_complete_bool)

            return complete

        while not check_complete(self, interval_timer):
            if timeout is not None and local_wait_timer.interval():
                raise Timeout("Wait timed out waiting for all maps to "
                              "complete")

            time.sleep(0.001)

        return self

    def terminate(self, timeoutMs=3000):
        """Terminate both the target process (the command) and reader queues.

        Use :meth:`terminate` to gracefully stop the target process (the
        command) and readers once you're done reading. Use :meth:`shutdown`
        if you are just trying to clean up, as it will trigger
        :meth:`terminate`.

        Args:
            timeoutMs (int): Milliseconds :meth:`terminate` should wait for
                main process to exit before raising a :exc:`Timeout` exception

        Raises:
            Timeout: If the command hasn't stopped within ``timeoutMs``
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
            raise Timeout("Main process has not terminated")

        # Kill the queues
        self._terminate_queues()

    def _terminate_queues(self):
        """Clean up straggling processes that might still be running.

        Run once you've finished reading from the queues.
        """
        # Clean up readers
        for proc_pipe_name in list(self.pipe_client_processes):
            for client_id, client_process in \
                    list(self.pipe_client_processes[proc_pipe_name].items()):

                # Close any remaining client readers
                try:
                    client_process.terminate()

                except Exception as exc:
                    message = "Exception closing {} client {}: {}. Did you " \
                              "trigger startMapLines first?"\
                        .format(proc_pipe_name, text(client_id), text(exc))
                    raise Exception(message)

                # Remove references to client queues
                self.unRegisterClientQueue(proc_pipe_name, client_id)

    def terminateCommand(self):
        """Send SIGTERM to the main process (the command)"""
        try:
            self.run.terminate()

        except OSError as exc:
            # 3 is "No such process", which probably means the process is
            # already terminated
            if exc.errno == 3:
                pass
            else:
                raise exc

        except ProcessNotStarted:
            self._log.warning("ProcessRunner.terminateCommand called without "
                              "the target process being instantiated")

        except Exception as exc:
            ExceptionHandler(exc)
            raise exc

    def killCommand(self):
        """Send SIGKILL to the main process (the command)"""
        return self.run.kill()

    def shutdown(self):
        """Shutdown the process managers. Run after verifying terminate/kill
        has destroyed any child processes

        Runs :meth:`terminate` in case it hasn't already been run
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

        self.queue_manager.shutdown()
        self.run_manager.shutdown()

        # Close any output handles (see write method)
        for file_path, handle in list(self.output_file_handles.items()):
            self._log.debug("Closing handle for output file %s", file_path)
            handle.flush()
            handle.close()

        try:
            # Throws a ValueError if the process isn't in the list (why?)
            PROCESSRUNNER_PROCESSES.remove(self)
        except ValueError as exc:
            self._log.debug("Exception during shutdown removing from list")
            ExceptionHandler(exc)

    def registerForClientQueue(self, procPipeName):
        """Register to get a client queue on a pipe manager

        The ID for the queue is returned from the method as a string.

        Args:
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            tuple: Client's queue ID (``string``) on this pipe and the new
            :class:`multiprocessing.JoinableQueue`
        """
        # TODO: Determine whether this should be a private class

        # Create a new queue
        joinable_q = self.queue_manager\
            .JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])

        # Connect this queue to receive records from procPipeName
        client_id = self.run.register_client_queue(procPipeName, joinable_q)

        # Store this queue for future reference
        self.pipe_clients[procPipeName][client_id] = joinable_q

        return client_id, joinable_q

    def _link_client_queues(self, procPipeName, queue):
        """Connect an existing :meth:`registerForClientQueue` queue to another
        queue

        Use an existing queue from :meth:`registerForClientQueue` and connect
        it to another queue. Used for process chaining, connecting stdout
        or stderr of one process to the stdin of the next.

        Example:
            # Connect a downstream stdin to the stdout of the current instance
            stdin_client_id, stdin_q = downstream_pr.registerForClientQueue(
            "stdin")
            self._link_client_queues("stdout", stdin_q)

        Args:
            procPipeName (string): Name of a pipe (e.g. stdout)
            queue (Queue): A queue proxy

        Returns:
            int
        """
        client_id = self.run.register_client_queue(procPipeName, queue)
        self.pipe_clients[procPipeName][client_id] = queue

        return client_id

    def unRegisterClientQueue(self, procPipeName, clientId):
        """Unregister a client queue from a pipe manager

        Keeps other clients from waiting on other clients that will never be
        read.

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager

        Returns:
            string: Client's queue ID that was unregistered
        """
        self.run.unregister_client_queue(procPipeName, clientId)

        if text(clientId) in self.pipe_client_processes:
            self.pipe_client_processes.pop(text(clientId))

    def getLineFromPipe(self, procPipeName, clientId, timeout=-1):
        """Retrieve a line from a pipe manager

        Throws :exc:`Empty` if no lines are available.

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            clientId (string): ID of the client queue on this pipe manager
            timeout (float): Less than 0 for get_nowait behavior, otherwise
                uses ``Queue.get(timeout=timeout)``; in seconds; default -1

        Returns:
            string: Line from specified client queue

        Raises:
            Empty: No lines are available
        """
        line = self.run.get_line_from_pipe(pipe_name=procPipeName,
                                           client_id=clientId,
                                           timeout=timeout)
        return line

    def destructiveAudit(self):
        """Force one line of output each from attached pipes

        Used for debugging issues that might relate to data stuck in the
        queues.  Triggers the pipes' destructive_audit function which prints
        the last line of the queue or an 'empty' message.
        """
        return self.run.destructive_audit()

    @deprecated("Replaced by map")
    def mapLines(self, func, procPipeName):
        """Run a function against each line presented by a pipe manager

        Returns a :class:`multiprocessing.Event` that can be used to monitor
        the status of the function. When the process is dead, the queues are
        empty, and all lines are processed, the :class:`multiprocessing.Event`
        will be set to ``True``. This can be used as a blocking mechanism by
        functions invoking :meth:`mapLines`, by using
        :meth:`multiprocessing.Event.wait`.

        Be careful to call startMapLines directly if invoking mapLines after
        start() has been called.

        Args:
            func (function): A function that takes one parameter, the line
                from the pipe
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            multiprocessing.Event
        """

        # This needs a re-think. With these moving to separate processes,
        # status in particular needs to be communicated back in a more
        # consistent way.
        client_id = self.registerForClientQueue(procPipeName)[0]
        complete = Event()
        self._log.info("Registering mapLines client %s for %s",
                       client_id, procPipeName)

        def do_write(run,
                     func,
                     complete,
                     client_id,
                     proc_pipe_name,
                     stop_event):
            """Call a function with each line from the pipe client

            Args:
                run (ProcessRunner): ProcessRunner instance
                func (function): Function that takes one string argument
                complete (multiprocessing.Event): An Event to set when this is
                    finished
                client_id (int): Client ID corresponding to proc_pipe_name
                proc_pipe_name (string): Name of a pipe
                stop_event (multiprocessing.Event): External indicator to exit

            Returns:
                multiprocessing.Event: The event sent in to the `complete`
                    argument
            """
            logger_name = "{}.mapLines.{}".format(__name__, client_id)
            log = logging.getLogger(logger_name)
            log.addHandler(logging.NullHandler())
            log.info("Starting doWrite client %s for %s",
                     client_id, proc_pipe_name)

            try:
                # Continue while there MIGHT be data to read
                while run.is_alive() \
                        or not run.is_queue_drained(proc_pipe_name, client_id):
                    log.debug("Trying to get line from %s for client %s",
                              proc_pipe_name, client_id)

                    # Continue while we KNOW THERE IS data to read
                    while True:
                        try:
                            line = run.get_line_from_pipe(proc_pipe_name,
                                                          client_id,
                                                          timeout=0.05)
                            log.debug("Writing line to user function")
                            func(line)
                        except Empty:
                            log.debug("No lines to get from %s for client %s",
                                      proc_pipe_name, client_id)
                            break

                        # Exit from the inner loop if the stop event is set
                        if stop_event.is_set():
                            break

                    # Exit from the inner loop if the stop event is set
                    if stop_event.is_set():
                        log.debug("Stopping doWrite")
                        break

            except Exception as exc:  # pylint: disable=broad-except
                # This is very broad. But there may be little we can do about
                # it, and we output as much information as possible when
                # these do occur.
                log.warning("Caught exception: %s", exc)
                ExceptionHandler(exc)

            finally:
                log.info("Ending doWrite client %s for %s",
                         client_id, proc_pipe_name)

                try:
                    # This will throw an EOFError when the run_manager has
                    # stopped already
                    run.unregister_client_queue(proc_pipe_name, client_id)

                except (BrokenPipeError, EOFError):
                    log.debug("Caught BrokenPipeError or EOFError while "
                              "stopping doWrite for client %s for %s",
                              client_id, proc_pipe_name)

                complete.set()

        # Name the process
        if self.log_name is not None:
            process_name = "mapLines-{}-{}".format(self.log_name,
                                                   procPipeName)
        else:
            process_name = "mapLines-{}".format(procPipeName)

        client = Process(target=do_write,
                         name=process_name,
                         kwargs=dict(run=self.run,
                                     func=func,
                                     complete=complete,
                                     client_id=client_id,
                                     proc_pipe_name=procPipeName,
                                     stop_event=self.stop_event))
        client.daemon = True

        # Store the process so it can potentially be re-joined
        self.pipe_client_processes[procPipeName][text(client_id)] = client

        # Store the complete event for wait to use
        self.pipe_clients_complete_events[procPipeName][text(client_id)] = \
            complete

        return complete

    def map(self, func, procPipeName):
        """Run a function against each line presented by a pipe manager

        Returns a :class:`multiprocessing.Event` that can be used to monitor
        the status of the function. When the process is dead, the queues are
        empty, and all lines are processed, the :class:`multiprocessing.Event`
        will be set to ``True``. This can be used as a blocking mechanism by
        functions invoking :meth:`ProcessRunner.map`, by using
        :meth:`~multiprocessing.Event.wait`.

        Be careful to call startMapLines directly if invoking map after
        start() has been called.

        Args:
            func (function): A function that takes one parameter, the line
                from the pipe
            procPipeName (string): One of "stdout" or "stderr"

        Returns:
            multiprocessing.Event
        """
        return self.mapLines(func, procPipeName)

    # Eliminates a potential race condition in mapLines if two are started on
    #   the same pipe
    # All client queues are registered at the beginning of the call to
    #   mapLines, so we can now start the clients sequentially without any
    #   possible message loss
    def startMapLines(self, force=False):
        """Start :meth:`mapLines` child processes

        Triggered by :meth:`wait`, so almost never needs to be called directly
        """
        self._log.info("Starting mapLines")

        if self.map_lines_started is False or force is True:
            self.map_lines_started = True

            # Keys are pipe names, values a sub-dict of clientIds and Process
            # instances
            for pipe_client_processes in \
                    list(self.pipe_client_processes.values()):

                # Keys are clientIds, values a list of Process instances
                for client in list(pipe_client_processes.values()):
                    try:
                        client.start()
                    except AssertionError:
                        pass

    def getExpandingList(self, procPipeName=None):
        """Get a shared ``list`` and one or more completion ``Events`` for
        lines from one or more output pipes (not stdin). Non-blocking in
        that it does not wait for the list to be populated.

        Args:
            procPipeName (string): Name of a pipe to read, or ``None`` to
                read all

        Returns:
            tuple: List of output lines and ``dict(pipename: Event,)``

        Returns a tuple of ``(list, dict)``. List of the output lines that
        expands as :meth:`mapLines` adds to it, and a ``dict`` of ``[pipeName:
        Event,]``. When an ``Event`` is "set", that means the given pipe has
        finished. The list is a :class:`multiprocessing.Manager.list`, shared
        with the :meth:`mapLines` process populating the content.

        The ``dict`` will have multiple values if ``procPipeName`` is
        ``None``, one for each output pipe.

        Used as a component of :meth:`collectLines`.
        """
        if procPipeName is not None:
            if procPipeName.lower() == "stdin":
                raise ValueError("Cannot get output from stdin")

        output_list = self.queue_manager.list()  # Final list of lines
        complete_events_dict = dict()  # "complete" Events from mapLines

        # Function for mapLines to write into the shared list
        def to_output(line):
            output_list.append(line.rstrip('\n'))

        # Register for a map of each appropriate pipe manager
        if procPipeName is None:
            # Go through the list of available pipes
            for pipe_name in list(self.pipe_clients):

                # Skip input pipes
                if pipe_name == "stdin":
                    continue

                # Register for the mapping
                complete_events_dict[pipe_name] = self.mapLines(to_output,
                                                                pipe_name)
                self._log.info("Registered %s", pipe_name)

        else:
            # Register for the mapping if we were given a specific one
            complete_events_dict[procPipeName] = self.mapLines(to_output,
                                                               procPipeName)
            self._log.info("Registered %s", procPipeName)

        # If these are new subscribers, make sure they are populated
        if self.started():
            self.startMapLines(force=True)

        return output_list, complete_events_dict

    def getClientCount(self, procPipeName=None):
        """Return the number of clients for a given pipe, or all pipes

        Args:
            procPipeName (string): Name of the pipe

        Returns:
            int: Number of clients of ``procPipeName`` or all pipes if
                ``procPipeName`` is None
        """
        current_client_count = 0

        if procPipeName is None:
            for client_dict in self.pipe_clients.values():
                current_client_count += len(client_dict)

        else:
            client_dict = self.pipe_clients[procPipeName]
            current_client_count = len(client_dict)

        return current_client_count

    @deprecated("Replaced by readlines")
    def collectLines(self,
                     procPipeName=None,
                     timeout=None,
                     suppress=None):
        """Retrieve output lines as a ``list`` for one or all pipes from the
        command.

        Blocks until the sources are finished and queues drained.

        .. admonition:: Please note

            - Will start the command if it is not already running
            - Removes trailing newlines

        If the command is already running, you will get a PotentialDataLoss
        exception. Catch the exception if the potenital data loss is
        acceptable in your situation.

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            timeout (float): Max time to stay in :meth:`collectLines`
            suppress (list or None): List of exceptions to not raise

        Raises:
            Timeout: If ``timeout`` is exceeded
            PotentialDataLoss: Command is started and other readers have
                already been registered

        Returns:
            list: List of strings that are the output lines from selected pipes
        """
        if suppress is None:
            suppress = []

        # Check if we've started, and already have registered clients
        if self.started():
            msg = "Potential for data loss when using collectLines after " \
                  "registering another client"
            if procPipeName is not None:
                msg = "{} for {}".format(msg, procPipeName)

            clients = self.getClientCount(procPipeName)
            if clients > 0:
                if PotentialDataLoss not in suppress:
                    raise PotentialDataLoss(msg)

        # Pick an appropriate pipe name
        pipe_name = "output" if procPipeName is None else procPipeName
        self._log.info("Collecting lines from %s", pipe_name)

        # Get a unique iterator over the pipe(s)
        output_iter = getattr(self, pipe_name)
        output_iter.settimeout(timeout=timeout)

        # Start the command if it hasn't been already
        if not self.started():
            self.start()

        # Use the iterator to build a concrete list
        output_list = list()
        for line in output_iter:
            output_list.append(line.rstrip('\n'))

        return output_list

    def readlines(self,
                     procPipeName=None,
                     timeout=None,
                     suppress=None):
        """Retrieve output lines as a ``list`` for one or all pipes from the
        command.

        Blocks until the sources are finished and queues drained.

        Alias of collectLines.

        Similar to IOBase.readlines, without the hint parameter.

        .. admonition:: Please note

            - Will start the command if it is not already running
            - Removes trailing newlines

        If the command is already running, you may get a

        Args:
            procPipeName (string): One of "stdout" or "stderr"
            timeout (float): Max time to stay in :meth:`collectLines`

        Raises:
            Timeout: If ``timeout`` is exceeded

        Returns:
            list: List of strings that are the output lines from selected pipes
        """
        return self.collectLines(procPipeName=procPipeName,
                                 timeout=timeout,
                                 suppress=suppress)

    def write(self, file_path, procPipeName=None, append=False):
        """Specify a file to direct output from the process. Does not block.

        Args:
            file_path (string): Path to a file that should receive output
            procPipeName (string): Outbound pipe to reference (stdout, stderr)
            append (bool): ``True`` to append to an existing file. Default
                (``False``) is to truncate the file

        Returns:
             ProcessRunner: Supports method chaining
        """
        # TODO: Figure out whether this should be refactored with Pr...Writer
        file_path = os.path.abspath(file_path)

        # Open a file handle with or without truncation
        # These are closed in the shutdown() method
        # pylint: disable=consider-using-with
        if append:
            file_handle = open(file_path, 'a')
            self._log.info("Opened for writing (append): %s", file_path)
        else:
            file_handle = open(file_path, 'w')
            file_handle.truncate()
            self._log.info("Opened for writing (truncate): %s", file_path)
        # pylint: enable=consider-using-with

        # Writer function
        func = writeOut(file_handle, outputPrefix="")

        # Generate a list of valid pipe names (e.g. skipping stdin)
        valid_names = list()
        for name in list(self.pipe_clients.keys()):
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
