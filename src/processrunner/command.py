# -*- coding: utf-8 -*-
"""Internal Command class that proxies all interaction with Popen"""
from __future__ import unicode_literals

import codecs
import random
import signal
import time
from subprocess import PIPE  # nosec
from subprocess import Popen  # nosec

from . import settings
from .classtemplate import PRTemplate
from .exceptionhandler import ProcessAlreadyStarted
from .exceptionhandler import ProcessNotStarted
from .exceptionhandler import Timeout
from .kitchenpatch import getwriter
from .prpipereader import _PrPipeReader
from .prpipewriter import _PrPipeWriter
from .timer import Timer


# Private class only intended to be used by ProcessRunner
class _Command(PRTemplate):
    """Custom wrapper for Popen that manages the interaction with Popen and any
    client objects that have requested output

    Runs in a separate process and is managed via multiprocessing.BaseManager,
    which provides proxy access to class methods

    """
    # TODO: Consider managing optional arguments differently to reduce count
    def __init__(self,
                 command,
                 cwd=None,
                 autostart=True,
                 std_queues=None,
                 log_name=None,
                 global_config=None):
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
        # Not used for cryptographic purposes, so excluding from Bandit
        self.id = \
            ''.join([random.choice(  # nosec
                '0123456789ABCDEF') for x in range(6)])

        settings.init()
        if global_config is None:
            settings.config = {}
        else:
            settings.config = global_config

        self._initialize_logging_with_id(__name__)

        # Identify this Command on the log feed
        self.log_name = log_name
        if self.log_name is not None:
            self._log.info("log_name is %s", self.log_name)

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
            self.enable_stdin(queue=std_queues['stdin'])

        # Start running if we would like
        if autostart:
            self.start()

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

    def get_command(self):
        """Retrieve the command that Popen is running

        Returns:
            list. List of strings
        """
        return self.command

    def enable_stdin(self, queue):
        """Enable the stdin pipe"""
        self.pipes['stdin'] = _PrPipeWriter(queue=queue,
                                            name="stdin",
                                            log_name=self.log_name)

    def start(self):
        """Begin running the target process"""
        if self.started:  # pylint: disable=no-else-raise
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
        on_posix = settings.config["ON_POSIX"]
        popen_kwargs = {
            "stdout": PIPE,
            "stderr": PIPE,
            "universal_newlines": False,
            "close_fds": on_posix,
            "cwd": self.cwd
        }

        if "stdin" in self.pipes:
            self.stdin_handle = PIPE
            popen_kwargs['stdin'] = self.stdin_handle

        # pylint: disable=consider-using-with
        self.proc = Popen(self.command, **popen_kwargs)
        # pylint: enable=consider-using-with

        # Init readers to transfer output from the Popen pipes to local queues
        wrapped_stdout = codecs.getreader("utf-8")(self.proc.stdout)
        wrapped_stderr = codecs.getreader("utf-8")(self.proc.stderr)
        self.pipes["stdout"].set_pipe_handle(wrapped_stdout)
        self.pipes["stderr"].set_pipe_handle(wrapped_stderr)

        if "stdin" in self.pipes:
            wrapped_stdin = getwriter("utf-8")(self.proc.stdin)
            self.pipes["stdin"].set_pipe_handle(wrapped_stdin)

        return self.started

    def stop(self, timeout=0.5):
        """Attempt a graceful shutdown

        :argument string timeout: How long to wait for the process to exit in
                                  seconds
        """
        # Send a SIGINT to the process
        if self.is_alive():
            self._log.info("Process is running, sending SIGINT")
            self.send_signal(signal.SIGINT)

        timer = Timer(timeout)
        while self.is_alive():
            self._log.info("Waiting for process to exit")
            time.sleep(0.001)

            # When we've crossed the timeout, terminate the process
            if timer.interval():
                self._log.info("Process took too long, terminating after %.1f"
                               " seconds", timeout)
                self.terminate()

        # Send a shutdown request to all the pipes
        for pipe_name, pipe in self.pipes.items():
            self._log.debug("Stopping pipe manager for %s", pipe_name)
            pipe.stop()

    def send_signal(self, signal_value):
        """Send a signal to the process"""
        return self.proc.send_signal(signal_value)

    def get_pipe(self, pipe_name):
        """Retrieve a _PrPipe manager instance by pipe name

        :param string pipe_name: One of "stdout" or "stderr"

        :return: _PrPipe[Reader|Writer]

        :raises: KeyError
        """
        if pipe_name not in self.pipes:
            raise KeyError(pipe_name + " is not an available pipe")

        return self.pipes[pipe_name]

    def is_queue_empty(self, pipe_name, client_id):
        """Check whether the _PrPipe* queues report empty for a given pipe
        and client

        Args:
            client_id (string): ID of the client queue
            pipe_name (string): One of "stdout" or  "stderr"

        Returns:
            bool
        """
        return self.get_pipe(pipe_name).is_empty(client_id)

    def are_all_queues_empty(self):
        """Check that all queues are empty

        A bit dangerous to use, will block if any client has stopped pulling
        from their queue. Better to use is_queue_empty() for the dedicated
        client queue. Sometimes (especially externally) that's not possible.

        Returns:
            bool
        """
        empty = True

        for pipename, pipe in list(self.pipes.items()):
            log_str = "{} is {}".format(pipename,
                                        ("empty" if pipe.is_empty()
                                         else "not empty"))
            self._log.info(log_str)
            empty = empty and pipe.is_empty()

            # empty_pipe = pipe.is_empty()
            # empty_pipe_str = "empty" if empty_pipe else "not empty"
            # self._log.info("%s is %s", pipename, empty_pipe_str)
            #
            # empty = empty and empty_pipe

        return empty

    def is_queue_alive(self, pipe_name):
        """Check if a queue is still running

        :arg string pipe_name: One of "stdout" or  "stderr"
        :return bool
        """
        return self.get_pipe(pipe_name).is_alive()

    def is_queue_drained(self, pipe_name, client_id=None):
        """Check if a queue could contain data

        :param string pipe_name: One of "stdout" or  "stderr"
        :param int client_id: Identifier of a client
        :return bool
        """
        return self.get_pipe(pipe_name).is_drained(client_id=client_id)

    def is_alive(self):
        """Check whether the Popen process reports alive

        Returns:
            bool
        """
        # try:
        #     state = bool(self.proc.poll())  # None is False
        #
        # except AttributeError:  # Proc may not be available yet
        #     state = False

        if self.proc is None:
            state = False
        else:
            # pylint: disable=R1719
            # This statement doesn't decompose to a simple "test"
            state = True if self.proc.poll() is None else False

        return state

    def poll(self):
        """Invoke the subprocess.Popen.poll() method

        Returns:
            NoneType, int. NoneType if alive, or int with exit code if dead
        """
        if self.proc is None:  # pylint: disable=no-else-raise
            raise ProcessNotStarted("_Command.poll called before process "
                                    "started")
        else:
            return self.proc.poll()

    def wait(self, timeout=None):
        """Block until the process exits

        Does some extra checking to make sure the pipe managers have finished
        reading

        :param float timeout: Timeout in seconds

        :returns: None
        """
        if timeout is not None:
            timeout_obj = Timer(timeout)

        def is_alive_local():
            """Checks whether output pipes are finished

            :return: bool
            """
            # Force down any unprocessed messages
            alive = False

            # Iterate through the list of pipes
            for pipe_name in list(self.pipes.keys()):
                pipe = self.get_pipe(pipe_name)

                # Skip writers
                if isinstance(pipe, _PrPipeWriter):
                    continue

                # pipe_alive = pipe.is_alive()
                pipe_drained = pipe.is_drained()
                self._log.debug("Pipe %s is_drained is %s",
                                # pipe_name, pipe_alive)
                                pipe_name, pipe_drained)

                # Check if the pipe is alive
                # Any pipe alive will cause us to return True
                # alive = alive or pipe_alive
                alive = alive and not pipe_drained

            return alive

        timer = Timer(interval=settings.config["NOTIFICATION_DELAY"])
        while self.poll() is None or is_alive_local() is True:
            if timer.interval():
                self._log.info("Waiting patiently: poll is %s, is_alive_local"
                               " is %s", self.poll(), is_alive_local())

            # If we've reached the timeout, exit
            if timeout is not None:
                if timeout_obj.interval():
                    message = "wait() has timed out " \
                              "at {} seconds".format(timeout)
                    self._log.error(message)
                    raise Timeout(message)

            time.sleep(0.005)

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

    def close_stdin(self):
        """Flush and close the stdin pipe"""
        if self.proc.stdin.closed:
            self._log.debug("close_stdin called, but the stdin pipe"
                            " isn't available")
            return False

        # Close the stdin _PrPipeWriter by stopping the _PrPipe
        try:
            stdin = self.get_pipe("stdin")
            stdin.stop()

        # Stdin isn't available
        except KeyError:
            self._log.debug("Close called, but the stdin pipe isn't available")

        self._log.debug("Closing the stdin pipe")
        self.proc.stdin.flush()
        self.proc.stdin.close()

        return True

    def register_client_queue(self, pipe_name, queue_proxy):
        """Register to get a client queue on a pipe manager

        The ID for the queue is returned from the method as a string

        Args:
            pipe_name (string): One of "stdout" or "stderr"
            queue_proxy (queueProxy): Proxy object to a Queue we should populate

        Returns:
            string Client queue ID, unique only when combined with pipe_name

        """
        return self.get_pipe(pipe_name).register_client_queue(queue_proxy)

    def unregister_client_queue(self, pipe_name, client_id):
        """Unregister a client queue from a pipe manager

        Prevents other clients from waiting on queues that will never be read

        Args:
            pipe_name (string): One of "stdout" or "stderr"
            client_id (string): ID of the client queue on this pipe manager
        """
        self.get_pipe(pipe_name).unregister_client_queue(client_id)

    def get_line_from_pipe(self, pipe_name, client_id, timeout=-1):
        """Retrieve a line from a pipe manager

        Throws Empty if no lines are available.

        Args:
            pipe_name (string): One of "stdout" or "stderr"
            client_id (string): ID of the client queue on this pipe manager
            timeout (float): <0 for get_nowait behavior, otherwise use
                           get(timeout=timeout); in seconds; default -1

        Returns:
            string. Line from specified client queue

        Raises:
            Empty
        """
        line = self.get_pipe(pipe_name).get_line(client_id=client_id,
                                                 timeout=timeout)
        return line

    def destructive_audit(self):
        """Force one line of output each from attached pipes

        Used for debugging issues that might relate to data stuck in the
        queues. Triggers the pipes' destructive_audit function which prints
        the last line of the queue or an 'empty' message.
        """
        for pipe in list(self.pipes.values()):
            pipe.destructive_audit()
