# -*- coding: utf-8 -*-
"""Parent class for _PrPipeReader and _PrPipeWriter"""
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import logging
import random

from multiprocessing import Event, Lock, Process

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from .queuelink import QueueLink
from .exceptionhandler import HandleAlreadySet

class _PrPipe(object):
    def __init__(self,
                 queue,
                 subclass_name,
                 queue_direction,
                 name=None,
                 pipe_handle=None,
                 log_name=None):
        """PrPipe abstract implementation

        :argument string queue_direction: Indicate direction relative to pipe;
            e.g. for PrPipeReader from stdout, the flow is (PIPE => QUEUE) =>
             CLIENT QUEUES (from pipe/queue into client queues), and therefore
             queue_direction would be "source".
        """

        # Unique ID for this PrPipe
        self.id = \
            ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

        # Name for this instance, typically stdin/stdout/stderr
        self.name = name

        # Name of the subclass (PrPipeReader, PrPipeWriter)
        self.subclass_name = subclass_name

        # Additional naming for differentiating multiple instances
        self.log_name = log_name

        # Initialize the logger
        self._initializeLogging()

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
        self.queue_link.registerQueue(queue_proxy=self.queue,
                                      direction=self.queue_direction)

        # Lock to notify readers/writers that a read/write is in progress
        self.queue_lock = Lock()

        # Keep track of the last client ID we used. Monotonically increasing
        # across all queues related to this PrPipe.
        self.lastClientId = 0

        self.process = None
        self.pipeHandle = None
        if pipe_handle is not None:
            self.setPipeHandle(pipe_handle)

    # Class contains Locks and Queues which cannot be pickled
    def __getstate__(self):
        """Prevent _PrPipe from being pickled across Processes

        Raises:
            Exception
        """
        raise Exception("Don't pickle me!")

    def _initializeLogging(self):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Make a helpful log name
        log_name = "{}-{}".format(self.subclass_name, self.id)

        if self.log_name is not None:
            log_name = "{}.{}".format(log_name, self.log_name)

        if self.name is None:
            log_name = "{}.{}".format(log_name, self.name)

        # Logging
        self._log = logging.getLogger(log_name)
        self.addLoggingHandler(logging.NullHandler())

    def addLoggingHandler(self, handler):
        self._log.addHandler(handler)

    def setPipeHandle(self, pipeHandle):
        """Set the pipe handle to use

        Args:
            pipeHandle (pipe): An open pipe (subclasses of file, IO.IOBase)

        Raises:
            HandleAlreadySet
        """
        if self.process is not None:
            raise HandleAlreadySet

        # Store the pipehandle
        self.pipeHandle = pipeHandle

        # Process name
        process_name = "{}-{}".format(self.subclass_name, self.name)

        if self.log_name is not None:
            process_name = "{}-{}".format(process_name, self.log_name)

        self._log.debug("Setting {} adapter process for {} pipe handle"
                        .format(self.subclass_name, self.name))
        self.process = Process(target=self.queue_pipe_adapter,
                               name=process_name,
                               kwargs={"pipe_name": self.name,
                                       "pipe_handle": pipeHandle,
                                       "queue": self.queue,
                                       "queue_lock": self.queue_lock,
                                       "stop_event": self.stop_event})
        self.process.daemon = True
        self.process.start()
        self.started.set()
        self._log.debug("Kicked off {} adapter process for {} pipe handle"
                        .format(self.subclass_name, self.name))

    @staticmethod
    def queue_pipe_adapter(pipe_name,
                           pipe_handle,
                           queue,
                           queue_lock,
                           stop_event):
        """Override me in a subclass to do something useful"""
        pass

    def getQueue(self, clientId):
        """Retrieve a client's Queue proxy object

        Args:
            clientId (string): ID of the client

        Returns:
            QueueProxy
        """
        return self.queue_link.getQueue(clientId)

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

    def isEmpty(self, clientId=None):
        """Checks whether the primary Queue or any clients' Queues are empty

        Returns True ONLY if ALL queues are empty if clientId is None
        Returns True ONLY if both main queue and specified client queue are
            empty when clientId is provided

        Args:
            clientId (string): ID of the client

        Returns:
            bool
        """
        with self.queue_lock:
            if clientId is not None:
                empty = self.queue.empty() \
                        and self.queue_link.isEmpty(clientId)

                self._log.debug("Reporting pipe empty for client {}: {}"
                                .format(clientId, empty))

            else:
                empty = self.queue.empty() \
                        and self.queue_link.isEmpty()

                self._log.debug("Reporting pipe empty: {}".format(empty))

            return empty

    def is_alive(self):
        """Check whether the thread managing the pipe > Queue movement
        is still active

        Returns:
            bool
        """
        return self.process.is_alive()

    def is_drained(self, clientId=None):
        """Check alive and empty

        Attempts clean semantic response to "is there, or will there be, data
        to read?"

        :returns bool"""
        drained = True

        # If we aren't started, we have to stop here. The process isn't ready
        # to call is_alive()
        if not self.started.is_set():
            return False

        # Alive (True) means we are not drained
        drained = drained and not self.is_alive()

        # Checks a similar function on the queue_link
        drained = drained and self.queue_link.is_drained(queue_id=clientId)

        # Not checking self.isEmpty because that is effectively done by
        # running self.queue_link.is_drained()

        return drained

    def registerClientQueue(self, queueProxy):
        return self.queue_link.registerQueue(queue_proxy=queueProxy,
                                             direction=self.client_direction)

    def unRegisterClientQueue(self, clientId):
        return self.queue_link.unRegisterQueue(queue_id=clientId,
                                               direction=self.client_direction)

    def destructiveAudit(self):
        return self.queue_link.destructiveAudit(direction=
                                                self.client_direction)
