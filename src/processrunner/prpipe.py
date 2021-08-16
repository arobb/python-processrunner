# -*- coding: utf-8 -*-
"""Parent class for _PrPipeReader and _PrPipeWriter"""
from __future__ import unicode_literals

import random
import sys
from multiprocessing import Event
from multiprocessing import Lock

from .classtemplate import PRTemplate
from .exceptionhandler import HandleAlreadySet
from .queuelink import QueueLink

if sys.version_info[0] == 2:
    from multiprocessing import Process
elif sys.version_info[0] == 3:
    import multiprocessing
    Process = multiprocessing.get_context("fork").Process


class _PrPipe(PRTemplate):
    def __init__(self,
                 queue,
                 subclass_name,
                 queue_direction,
                 name=None,
                 pipe_handle=None,
                 log_name=None):
        """PrPipe abstract implementation

        Args:
             queue_direction (string): Indicate direction relative to pipe;
                e.g. for PrPipeReader from stdout, the flow is (PIPE => QUEUE)
                => CLIENT QUEUES (from pipe/queue into client queues), and
                therefore queue_direction would be "source".
        """

        # Unique ID for this PrPipe
        # Not used for cryptographic purposes, so excluding from Bandit
        self.id = \
            ''.join([random.choice(  # nosec
                '0123456789ABCDEF') for x in range(6)])

        # Name for this instance, typically stdin/stdout/stderr
        self.name = name

        # Name of the subclass (PrPipeReader, PrPipeWriter)
        self.subclass_name = subclass_name

        # Additional naming for differentiating multiple instances
        self.log_name = log_name

        # Initialize the logger
        self._initialize_logging_with_log_name(self.subclass_name)

        # Which "direction" client queues will use in the queue_link
        self.queue_direction = queue_direction
        self.client_direction = "source" if queue_direction == "destination" \
            else "destination"

        # Whether we have ever been started
        self.started = Event()

        # Whether we have been asked to stop
        self.stopped = Event()

        # Whether the queue adapter process should stop
        self.stop_event = Event()

        # The queue proxy to be used as the main input or output buffer.
        # Attaching this to the queue link is the responsibility of subclasses.
        self.queue = queue

        # Mechanism to connect the baseline queue and client queues
        self.queue_link = QueueLink(self.name,
                                    log_name=self.log_name)

        # Store the queue in the correct orientation in the queue link
        self.queue_link.register_queue(queue_proxy=self.queue,
                                       direction=self.queue_direction)

        # Lock to notify readers/writers that a read/write is in progress
        self.queue_lock = Lock()

        self.process = None
        self.pipe_handle = None
        if pipe_handle is not None:
            self.set_pipe_handle(pipe_handle)

    # Class contains Locks and Queues which cannot be pickled
    def __getstate__(self):
        """Prevent _PrPipe from being pickled across Processes

        Raises:
            Exception
        """
        raise Exception("Don't pickle me!")

    def set_pipe_handle(self, pipe_handle):
        """Set the pipe handle to use

        Args:
            pipe_handle (io.IOBase): An open pipe (subclasses of file,
                IO.IOBase)

        Raises:
            HandleAlreadySet
        """
        if self.process is not None:
            raise HandleAlreadySet

        # Store the pipehandle
        self.pipe_handle = pipe_handle

        # Process name
        process_name = "{}-{}".format(self.subclass_name, self.name)

        if self.log_name is not None:
            process_name = "{}-{}".format(process_name, self.log_name)

        self._log.debug("Setting %s adapter process for %s pipe handle",
                        self.subclass_name, self.name)
        self.process = Process(target=self.queue_pipe_adapter,
                               name=process_name,
                               kwargs={"pipe_name": self.name,
                                       "pipe_handle": pipe_handle,
                                       "queue": self.queue,
                                       "queue_lock": self.queue_lock,
                                       "stop_event": self.stop_event})
        self.process.daemon = True
        self.process.start()
        self.started.set()
        self._log.debug("Kicked off %s adapter process for %s pipe handle",
                        self.subclass_name, self.name)

    @staticmethod
    def queue_pipe_adapter(pipe_name,
                           pipe_handle,
                           queue,
                           queue_lock,
                           stop_event):
        """Override me in a subclass to do something useful"""

    def get_queue(self, client_id):
        """Retrieve a client's Queue proxy object

        Args:
            client_id (string): ID of the client

        Returns:
            multiprocessing.JoinableQueue:
        """
        return self.queue_link.get_queue(client_id)

    def stop(self):
        """Stop the adapter and queue link.

        Does not force a drain of the queues.
        """
        # Mark that we have been asked to stop
        self.stopped.set()

        # Stop the adapter
        self.stop_event.set()

        while True:
            self.process.join(timeout=5)
            if self.process.exitcode is None:
                self._log.info("Waiting for adapter to stop")
            else:
                break

        # Stop the queue link
        self.queue_link.stop()

    def is_empty(self, client_id=None):
        """Checks whether the primary Queue or any clients' Queues are empty

        Returns True ONLY if ALL queues are empty if clientId is None
        Returns True ONLY if both main queue and specified client queue are
            empty when clientId is provided

        Args:
            client_id (string): ID of the client

        Returns:
            bool
        """
        with self.queue_lock:
            if client_id is not None:
                empty = self.queue.empty() \
                        and self.queue_link.is_empty(client_id)

                self._log.debug("Reporting pipe empty for client %s: %s",
                                client_id, empty)

            else:
                empty = self.queue.empty() \
                        and self.queue_link.is_empty()

                self._log.debug("Reporting pipe empty: %s", empty)

            return empty

    def is_alive(self):
        """Check whether the thread managing the pipe > Queue movement
        is still active

        Returns:
            bool
        """
        return self.process.is_alive()

    def is_drained(self, client_id=None):
        """Check alive and empty

        Attempts clean semantic response to "is there, or will there be, data
        to read?"

        Args:
            client_id (string): Registration ID to check

        Returns:
            bool: True if fully drained, False if not
        """
        drained = True

        # If we aren't started, we have to stop here. The process isn't ready
        # to call is_alive()
        if not self.started.is_set():
            return False

        # Alive (True) means we are not drained
        drained = drained and not self.is_alive()

        # Checks a similar function on the queue_link
        drained = drained and self.queue_link.is_drained(queue_id=client_id)

        # Not checking self.is_empty because that is effectively done by
        # running self.queue_link.is_drained()

        return drained

    def register_client_queue(self, queue_proxy):
        """Register an existing Queue proxy to obtain data from this pipe

        Args:
            queue_proxy (multiprocessing.JoinableQueue): Proxy reference to a
                JoinableQueue

        Returns:
            string: An integer Client ID, usually string encoded.
        """
        return self.queue_link.register_queue(queue_proxy=queue_proxy,
                                              direction=self.client_direction)

    def unregister_client_queue(self, client_id):
        """Remove a registration to stop content being added to a Queue

        Args:
            client_id (string): Registration ID to unlink

        Returns:
            None
        """
        return self.queue_link.unregister_queue(queue_id=client_id,
                                                direction=self.client_direction)

    def destructive_audit(self):
        """Remove a line from each attached queue and print it

        Returns:
            None
        """
        return self.queue_link.destructive_audit(direction=
                                                self.client_direction)
