# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import time

from multiprocessing import Process, Lock

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from . import settings
from .prpipe import _PrPipe
from .contentwrapper import ContentWrapper
from .exceptionhandler import HandleAlreadySet
from .exceptionhandler import HandleNotSet


# Private class only intended to be used by ProcessRunner
# Works around (https://bryceboe.com/2011/01/28/
# the-python-multiprocessing-queue-and-large-objects/ with large objects)
# by using ContentWrapper to buffer large lines to disk
class _PrPipeWriter(_PrPipe):
    """Custom pipe manager to read thread-safe queues and write their contents
        to an outbound pipe.

       Clients register their own queues.
    """

    def __init__(self, pipeHandle=None):
        """
        Args:
            pipeHandle (pipe): Pipe to write records to
        """
        # Initialize the parent class
        super(type(self), self).__init__()
        self._initializeLogging(__name__)

        self.outboundQueueLock = self.getQueueLock()

        self.pipeHandle = None
        if pipeHandle is not None:
            self.setPipeHandle(pipeHandle)

    def setPipeHandle(self, pipeHandle):
        """Set the outbound pipe handle for us to write to

        Args:
            pipeHandle (pipe): An open pipe (subclasses of file, IO.IOBase)

        Raises:
            HandleAlreadySet
        """
        if self.pipeHandle is not None:
            raise HandleAlreadySet

        self._log.info("Setting outbound pipe handle (e.g. open(pipe, 'w'))")
        self.pipeHandle = pipeHandle

    def close(self):
        """Close the outbound queue"""
        if self.pipeHandle is None:
            raise HandleNotSet("_PrPipeWriter output file handle hasn't been "
                               "set, but .close was called")

        return self.pipeHandle.close()

    def publish(self, requireLock=None):
        """Push messages from client queues to the outbound pipe

        Must be triggered by an external mechanism
        Typically triggered by getLine or wait

        requireLock (None): Used for compatibility with _PrPipeReader's
            signature
        """
        if self.pipeHandle is None:
            raise HandleNotSet("_PrPipeWriter.publish called before "
                               "pipeHandle set")

        # Lock the list of client queues
        self._log.debug("Trying to get outboundQueueLock")
        with self.outboundQueueLock:
            self._log.debug("outboundQueueLock obtained")

            # Iterate throught the list of clients
            for clientId in list(self.clientQueues.keys()):
                self._log.debug("Checking for a line from client {} to write"
                                .format(clientId))

                # Try to get a line from each queue. getLine throws Empty
                try:
                    while True:
                        line = self.getLine(clientId)
                        self.pipeHandle.write(line)
                        self._log.debug("Line: '{}'".format(line))

                except Empty:
                    self._log.debug("Line was empty")

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
        if clientId is not None:
            empty = self.getQueue(clientId).empty()

        else:
            empty = True  # Prime the value

            with self.outboundQueueLock:
                for q in list(self.clientQueues.values()):
                    empty = empty and q.empty()

        self._log.debug("Reporting pipe empty: {}".format(empty))
        return empty

    def getLine(self, clientId):
        """Retrieve a line from a given client's Queue

        Args:
            clientId (string): ID of the client

        Returns:
            <element from Queue>

        Raises:
            Empty
        """
        # Throws Empty
        q = self.getQueue(clientId)
        line = q.get_nowait()
        q.task_done()

        self._log.debug("Returning line")

        if type(line) is ContentWrapper:
            return line.value
        else:
            return line

