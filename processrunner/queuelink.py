# -*- coding: utf-8 -*-
"""Manages the pull/push with queues"""
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import logging
import random
import time

from multiprocessing import Process, Lock

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty


class QueueLink(object):
    def __init__(self):
        """Manages the pull/push with PrPipe queues"""
        self.id = \
            ''.join([random.choice('0123456789ABCDEF') for x in range(6)])

        self._initializeLogging()

        # List of locks allows decoupled IO while also preventing the set of
        # queues from changing during IO operations
        self.clientQueuesLock = Lock()
        self.lastClientId = 0
        self.clientQueuesSource = dict()
        self.clientQueuesDestination = dict()
        self.clientPairPublishers = dict()

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

    @staticmethod
    def publisher(pair_name, source_queue, dest_queue):
        """Move messages from the inbound queue to the outbound queue"""
        # with lock:
        # Think about whether this should be a double loop over two lists,
        # or whether to have a separate publisher for each source/dest pair
        # Atm I like having a separate one for each pair
        log = logging.getLogger("{}-{}".format(__name__, pair_name))
        log.addHandler(logging.NullHandler())

        while True:
            try:
                log.debug("Getting line from source in pair {}"
                          .format(pair_name))
                line = source_queue.get_nowait()

                log.debug("Writing line to dest in pair {}".format(pair_name))
                dest_queue.put(line)

                source_queue.task_done()

            except Empty:
                time.sleep(0.001)

    def getClientQueue(self, client_id):
        """Retrieve a client's Queue proxy object

        Args:
            client_id (string): ID of the client

        Returns:
            QueueProxy
        """
        if client_id in self.clientQueuesSource:
            queue_list = self.clientQueuesSource
        else:
            queue_list = self.clientQueuesDestination

        return queue_list[text(client_id)]

    def registerClientQueue(self, queue_proxy, direction):
        """Attach an additional Queue proxy to this _PrPipe

        All elements published() from now on will also be added to this Queue
        Returns the clientId for the new client, which must be used in all
        future interaction with this _PrPipe

        A list of Locks created by getQueueLock allows reads and writes to be
        decoupled while also preventing the list from changing during either
        operation.

        Args:
            queue_proxy (QueueProxy): Proxy object to a Queue we should populate
            direction (string): source or destination

        Returns:
            string. The client's ID for access to this queue

        """
        # Make sure we don't re-use a clientId
        # with self.clientQueuesLock:
        #     clientId = self.lastClientId + 1
        #     self.lastClientId = clientId
        #
        #     self.clientQueues[text(clientId)] = queueProxy

        if direction == "source" or direction == "destination":
            pass
        else:
            raise TypeError("destination must be 'source' or 'destination'")

        # Get the 'direction' names with the first letter capitalized
        direction_caps = direction.capitalize()
        op_direction_caps = "Destination" if direction == "source" \
            else "Source"

        with self.clientQueuesLock:
            # Get the queue list and opposite queue list
            queue_list = getattr(self, "clientQueues{}".format(direction_caps))
            op_queue_list = getattr(self, "clientQueues{}"
                                    .format(op_direction_caps))

            # Make sure we don't accidentally create a loop, or add multiple
            # times
            if queue_proxy in queue_list.values():
                raise ValueError("Cannot add this queue again")

            if queue_proxy in op_queue_list.values():
                raise ValueError("This queue is in the opposite list. Cannot"
                                 " add to the {} list because it would cause"
                                 " a circular reference.".format(direction))

            # Increment the current client_id
            client_id = self.lastClientId + 1
            self.lastClientId = client_id

            # Store the queue proxy in the queue list
            queue_list[text(client_id)] = queue_proxy

            # Create the publishing processes for all new pairs
            op_direction_caps = "Destination" if direction == "source" \
                else "Source"
            op_queue_list = getattr(self, "clientQueues{}"
                                    .format(op_direction_caps))

            # Iterate over the list of queues in the opposite list
            for op_client_id, op_q in op_queue_list.items():
                if direction == "source":
                    pair_name = "{}-{}".format(client_id, op_client_id)
                    source_queue = queue_proxy
                    dest_queue = op_q
                else:
                    pair_name = "{}-{}".format(op_client_id, client_id)
                    source_queue = op_q
                    dest_queue = queue_proxy

                # Start a publisher process to move items from the source
                # queue to the destination queue
                proc = Process(target=self.publisher,
                               name="ClientPublisher-{}".format(pair_name),
                               kwargs={"pair_name": pair_name,
                                       "source_queue": source_queue,
                                       "dest_queue": dest_queue})
                proc.daemon = True
                proc.start()
                self.clientPairPublishers[text(pair_name)] = proc

        return text(client_id)

    def unRegisterClientQueue(self, client_id, direction):
        """Detach a Queue proxy from this _PrPipe

        Returns the clientId that was removed

        Args:
            client_id (string): ID of the client
            direction (string): source or destination

        Returns:
            string. ID of the client queue

        """
        # with self.clientQueuesLock:
        #     if text(clientId) in self.clientQueues:
        #         self.clientQueues.pop(clientId)

        direction_caps = direction.capitalize()

        with self.clientQueuesLock:
            queue_list = getattr(self, "clientQueues{}".format(direction_caps))
            if text(client_id) in queue_list:
                queue_list.pop(client_id)

            # Create the publishing processes for all new pairs
            op_direction_caps = "Destination" if direction == "source" \
                else "Source"
            op_queue_list = getattr(self, "clientQueues{}"
                                    .format(op_direction_caps))

            # Iterate over the list of queues in the opposite list
            for op_client_id, op_q in op_queue_list.items():
                if direction == "source":
                    pair_name = "{}-{}".format(client_id, op_client_id)
                else:
                    pair_name = "{}-{}".format(op_client_id, client_id)

                # Stop the publisher for the pair
                self.clientPairPublishers[text(pair_name)].terminate()

        return text(client_id)

    def destructiveAudit(self, direction):
        """Print a line from each client Queue attached to this _PrPipe

        Args:
            direction (string): source or destination

        This is a destructive operation, as it *removes* a line from each Queue
        """
        # with self.clientQueuesLock:
        #     for clientId in list(self.clientQueues):
        #         try:
        #             self._log.info("clientId {}: {}"
        #                            .format(text(clientId),
        #                                    self.getLine(clientId)))
        #         except Empty:
        #             self._log.info("clientId {} is empty"
        #                            .format(text(clientId)))

        direction_caps = direction.capitalize()

        with self.clientQueuesLock:
            queue_list = getattr(self, "clientQueues{}".format(direction_caps))

            for client_id in list(queue_list):
                try:
                    self._log.info("client_id {}: {}"
                                   .format(text(client_id),
                                           self.getLine(client_id)))
                except Empty:
                    self._log.info("client_id {} is empty"
                                   .format(text(client_id)))
