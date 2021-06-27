# -*- coding: utf-8 -*-
"""Parent class for _PrPipeReader and _PrPipeWriter"""
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import logging
import random

from multiprocessing import Lock

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty


class _PrPipe(object):
    def __init__(self):
        self.id = \
            ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

        # List of locks allows decoupled IO while also preventing the set of
        # queues from changing during IO operations
        self.clientQueuesLockList = []  # Might get rid of this
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

    def _initializeLogging(self, name):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Logging
        self._log = logging.getLogger(name)
        self.addLoggingHandler(logging.NullHandler())

    def addLoggingHandler(self, handler):
        self._log.addHandler(handler)

    def getQueue(self, clientId):
        """Retrieve a client's Queue proxy object

        Args:
            clientId (string): ID of the client

        Returns:
            QueueProxy
        """
        return self.clientQueues[text(clientId)]

    def getQueueLock(self):
        """Retrieve a new Lock for the client queue list

        Returns:
            Lock
        """
        newLock = Lock()
        self.clientQueuesLockList.append(newLock)

        return newLock

    def deleteQueueLock(self, lock):
        """Remove a previously created Lock object from the list of Locks

        :arg lock Lock() previously obtained from getQueueLock
        """
        self.clientQueuesLockList.remove(lock)

    def getQueueLockList(self):
        return self.clientQueuesLockList

    def registerClientQueue(self, queueProxy):
        """Attach an additional Queue proxy to this _PrPipe

        All elements published() from now on will also be added to this Queue
        Returns the clientId for the new client, which must be used in all
        future interaction with this _PrPipe

        A list of Locks created by getQueueLock allows reads and writes to be
        decoupled while also preventing the list from changing during either
        operation.

        Args:
            queueProxy (QueueProxy): Proxy object to a Queue we should populate

        Returns:
            string. The client's ID for access to this queue

        """
        # # Lock all of the locks
        # localLock = None  # In case there are no current locks, make one
        # if len(self.clientQueuesLockList) == 0:
        #     localLock = self.getQueueLock()
        #     localLock.acquire()
        #
        # # With existing locks, lock them all
        # else:
        #     for lock in self.clientQueuesLockList:
        #         lock.acquire(block=True)

        # Make sure we don't re-use a clientId
        with self.clientQueuesLock:
            clientId = self.lastClientId + 1
            self.lastClientId = clientId

            self.clientQueues[text(clientId)] = queueProxy

        # # Unlock all of the locks
        # if localLock is not None:
        #     localLock.release()
        #     self.deleteQueueLock(localLock)
        #
        # else:
        #     for lock in self.clientQueuesLockList:
        #         lock.release()

        return text(clientId)

    def unRegisterClientQueue(self, clientId):
        """Detach a Queue proxy from this _PrPipe

        Returns the clientId that was removed

        Args:
            clientId (string): ID of the client

        Returns:
            string. ID of the client queue

        """
        # # Lock all of the locks
        # lock = None  # In case there are no current locks, make one
        # if len(self.clientQueuesLockList) == 0:
        #     lock = self.getQueueLock()
        #
        # # With existing locks, lock them all
        # else:
        #     for lock in self.clientQueuesLockList:
        #         lock.acquire(block=True)

        with self.clientQueuesLock:
            if text(clientId) in self.clientQueues:
                self.clientQueues.pop(clientId)

        # self.deleteQueueLock(lock)

        return text(clientId)

    def destructiveAudit(self):
        """Print a line from each client Queue attached to this _PrPipe

        This is a destructive operation, as it *removes* a line from each Queue
        """
        # lock = self.getQueueLock()
        #
        # with lock:

        with self.clientQueuesLock:
            for clientId in list(self.clientQueues):
                try:
                    self._log.info("clientId {}: {}"
                                   .format(text(clientId),
                                           self.getLine(clientId)))
                except Empty:
                    self._log.info("clientId {} is empty"
                                   .format(text(clientId)))

        # self.deleteQueueLock(lock)
