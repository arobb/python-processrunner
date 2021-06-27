# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import time

from multiprocessing import Process, Lock, JoinableQueue

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from . import settings
from .prpipe import _PrPipe
from .contentwrapper import ContentWrapper
from .exceptionhandler import HandleAlreadySet


# Private class only intended to be used by ProcessRunner
# Works around (https://bryceboe.com/2011/01/28/
# the-python-multiprocessing-queue-and-large-objects/ with large objects)
# by using ContentWrapper to buffer large lines to disk
class _PrPipeReader(_PrPipe):
    """Custom pipe manager to capture the output of processes and store them in
       one more more dedicated thread-safe queues.

       Clients register their own queues.
    """

    def __init__(self, pipeHandle=None):
        """
        Args:
            pipeHandle (pipe): Pipe to monitor for records
        """
        super(type(self), self).__init__()
        self._initializeLogging(__name__)

        self.queue = JoinableQueue(settings.config["MAX_QUEUE_LENGTH"])
        # self.inboundQueueLock = self.getQueueLock()
        self.inboundQueueLock = Lock()

        self.process = None
        if pipeHandle is not None:
            self.setPipeHandle(pipeHandle)

    def setPipeHandle(self, pipeHandle):
        """Set the inbound pipe handle to read from

        Args:
            pipeHandle (pipe): An open pipe (subclasses of file, IO.IOBase)

        Raises:
            HandleAlreadySet
        """
        if self.process is not None:
            raise HandleAlreadySet

        self.process = Process(target=self.enqueue_output,
                               name="PrPipeReader",
                               kwargs={"fromprocess": pipeHandle,
                                       "queue": self.queue})
        self.process.daemon = True
        self.process.start()

    def enqueue_output(self, fromprocess, queue):
        """Copy lines from a given pipe handle into a local threading.Queue

        Runs in a separate process, started by __init__. Closes pipe when done
        reading.

        Args:
            fromprocess (pipe): Pipe to read from
            queue (Queue): Queue to write to
        """
        for line in iter(fromprocess.readline, ''):
            self._log.info("Enqueing line of length {}".format(len(line)))
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
        fromprocess.close()

    def publish(self, requireLock=False):
        """Push messages from the main queue to all client queues

        Must be triggered by an external mechanism
        Typically triggered by getLine or wait

        Args:
            requireLock (bool): True to force obtaining a queue lock. If a
                lock is not obtained, publishing will not occur to prevent
                queues from missing messages. NOTE THAT TRUE MAY DEADLOCK
                WHEN CALLED CONCURRENTLY WITH A CALL TO isEmpty.

                Recommend using False (the default) when called from outside
                ProcessRunner. (Internal functions call this with True
                regularly.)
        """
        self._log.debug("Trying to get inboundQueueLock")
        with self.inboundQueueLock:
            self._log.debug("inboundQueueLock obtained")
            try:

                while True:
                    self._log.debug("Getting line from the main queue")
                    line = self.queue.get_nowait()

                    # Write the line to each client queue
                    for clientId, q in self.clientQueues.items():
                        self._log.debug("Writing line to {}".format(clientId))
                        q.put(line)

                    self.queue.task_done()

            except Empty:
                self._log.debug("Queue empty")

            return True

        return False

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

                for q in list(self.clientQueues.values()):
                    empty = empty and q.empty()

            self._log.debug("Reporting pipe empty: {}".format(empty))
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
