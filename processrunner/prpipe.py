# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import logging
import random
import time

from multiprocessing import Process, Lock, JoinableQueue

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from . import settings
from .contentwrapper import ContentWrapper


# Private class only intended to be used by ProcessRunner
# Suffers from https://bryceboe.com/2011/01/28/
# the-python-multiprocessing-queue-and-large-objects/ with large objects
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
        self._initializeLogging()

        self.id = \
            ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

        self.queue = JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
        self.inboundQueueLock = Lock()

        self.process = Process(target=self.enqueue_output,
                               kwargs={"out": pipeHandle, "queue": self.queue})
        self.process.daemon = True
        self.process.start()

        self.clientQueuesLock = Lock()
        self.clientQueues = dict()
        self.lastClientId = 0

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

        # Logging
        self._log = logging.getLogger(__name__)
        self.addLoggingHandler(logging.NullHandler())

    def addLoggingHandler(self, handler):
        self._log.addHandler(handler)

    def enqueue_output(self, out, queue):
        """Copy lines from a given pipe handle into a local threading.Queue

        Runs in a separate process, started by __init__. Closes pipe when done
        reading.

        Args:
            out (pipe): Pipe to read from
            queue (Queue): Queue to write to
        """
        with self.inboundQueueLock:
            for line in iter(out.readline, ''):
                self._log.debug("Enqueing line of length {}".format(len(line)))
                lineContent = ContentWrapper(line)
                queue.put(lineContent)

                queueStatus = queue.empty()
                self._log.debug("Queue reporting empty as '{}' after adding "
                                "line of length {}".format(queueStatus,
                                                           len(lineContent)))

                # Wait until the queue reports the added content
                while queue.empty():
                    time.sleep(0.001)

                # If the queue originally reported that it was empty, report
                # that it's now showing the new content
                if queueStatus:
                    self._log.debug("Queue now reporting the added content")

        self._log.debug("Closing pipe handle")
        out.close()

    def publish(self):
        """Push messages from the main queue to all client queues

        Must be triggered by an external mechanism
        Typically triggered by getLine or wait

        """
        with self.inboundQueueLock:
            try:
                while not self.queue.empty():

                    with self.clientQueuesLock:
                        line = self.queue.get_nowait()
                        for q in list(self.clientQueues.values()):
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
        return self.clientQueues[text(clientId)]

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
        with self.inboundQueueLock:
            if clientId is not None:
                empty = self.queue.empty() \
                        and self.getQueue(clientId).empty()

            else:
                empty = self.queue.empty()

                with self.clientQueuesLock:
                    for q in list(self.clientQueues.values()):
                        empty = empty and q.empty()

            self._log.debug("Reporting queue empty: {}".format(empty))
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

        self._log.debug("Returning line")

        return line.value

    def registerClientQueue(self, queueProxy):
        """Attach an additional Queue proxy to this _PrPipe

        All elements published() from now on will also be added to this Queue
        Returns the clientId for the new client, which must be used in all
        future interaction with this _PrPipe

        Args:
            queueProxy (QueueProxy): Proxy object to a Queue we should populate

        Returns:
            string. The client's ID for access to this queue

        """
        # Make sure we don't re-use a clientId
        clientId = self.lastClientId + 1
        self.lastClientId = clientId

        with self.clientQueuesLock:
            self.clientQueues[text(clientId)] = queueProxy

        return text(clientId)

    def unRegisterClientQueue(self, clientId):
        """Detach a Queue proxy from this _PrPipe

        Returns the clientId that was removed

        Args:
            clientId (string): ID of the client

        Returns:
            string. ID of the client queue

        """
        with self.clientQueuesLock:
            if text(clientId) in self.clientQueues:
                self.clientQueues.pop(clientId)

        return text(clientId)

    def destructiveAudit(self):
        """Print a line from each client Queue attached to this _PrPipe

        This is a destructive operation, as it *removes* a line from each Queue
        """
        with self.clientQueuesLock:
            for clientId in list(self.clientQueues):
                try:
                    self._log.info("clientId {}: {}"
                                   .format(text(clientId),
                                           self.getLine(clientId)))
                except Empty:
                    self._log.info("clientId {} is empty"
                                   .format(text(clientId)))
