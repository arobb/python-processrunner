# -*- coding: utf-8 -*-
"""Manages the pull/push with queues"""
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import logging
import random
import time

from multiprocessing import Process, Lock, Manager

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty


class QueueLink(object):
    def __init__(self, name=None):
        """Manages the pull/push with PrPipe queues"""
        self.id = \
            ''.join([random.choice('0123456789ABCDEF') for x in range(6)])
        self.name = name

        self._initializeLogging()

        # List of locks allows decoupled IO while also preventing the set of
        # queues from changing during IO operations
        self.queuesLock = Lock()
        self.lastQueueId = 0
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

        # Make a helpful name
        if self.name is None:
            name = __name__
        else:
            name = "{}.{}".format(__name__, self.name)

        self._log = logging.getLogger(name)
        self.addLoggingHandler(logging.NullHandler())

    def addLoggingHandler(self, handler):
        self._log.addHandler(handler)

    @staticmethod
    def publisher(pair_name, source_queue, dest_queue, name=None):
        """Move messages from the source queue to the destination queue"""
        # TODO: Refactor this to iterate through a list of dest_queues
        # Make a helpful logger name
        if name is None:
            logger_name = "{}.publisher.{}".format(__name__, pair_name)
        else:
            logger_name = "{}.publisher.{}.{}".format(__name__
                                                      , name
                                                      , pair_name)

        log = logging.getLogger(logger_name)
        log.addHandler(logging.NullHandler())

        while True:
            try:
                log.debug("Trying to get line from source in pair {}"
                          .format(pair_name))
                line = source_queue.get_nowait()

                log.info("Writing line to dest in pair {}"
                         .format(pair_name))
                dest_queue.put(line)

                source_queue.task_done()

            except Empty:
                time.sleep(0.001)

    # @staticmethod
    # def publisher(source_no, source_queue, dest_queue_list, pipe_name=None):
    #     """Move messages from the source queue to the destination queue"""
    #     # TODO: Refactor this to iterate through a list of dest_queues
    #     # Make a helpful logger name
    #     if pipe_name is None:
    #         logger_name = "{}.publisher.{}".format(__name__, source_no)
    #     else:
    #         logger_name = "{}.publisher.{}.{}".format(__name__
    #                                                   , pipe_name
    #                                                   , source_no)
    #
    #     log = logging.getLogger(logger_name)
    #     log.addHandler(logging.NullHandler())
    #
    #     while True:
    #         try:
    #             log.debug("Trying to get line from source in pair {}"
    #                       .format(source_no))
    #             line = source_queue.get_nowait()
    #
    #             log.info("Writing line to dest in pair {}"
    #                      .format(source_no))
    #             for dest_queue in dest_queue_list:
    #                 dest_queue.put(line)
    #
    #             source_queue.task_done()
    #
    #         except Empty:
    #             time.sleep(0.001)

    def getQueue(self, queue_id):
        """Retrieve a client's Queue proxy object

        Args:
            queue_id (string): ID of the client

        Returns:
            QueueProxy
        """
        if queue_id in self.clientQueuesSource:
            queue_list = self.clientQueuesSource
        else:
            queue_list = self.clientQueuesDestination

        return queue_list[text(queue_id)]

    def registerQueue(self, queue_proxy, direction):
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
        # TODO: Refactor this to only start one publisher per source queue
        # Probably also need to use a managed list so we can add and remove
        # dest queues
        if direction == "source" or direction == "destination":
            pass
        else:
            raise TypeError("destination must be 'source' or 'destination'")

        # Get the 'direction' names with the first letter capitalized
        direction_caps = direction.capitalize()
        op_direction_caps = "Destination" if direction == "source" \
            else "Source"

        with self.queuesLock:
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

            # Increment the current queue_id
            queue_id = self.lastQueueId + 1
            self.lastQueueId = queue_id

            # Store the queue proxy in the queue list
            queue_list[text(queue_id)] = queue_proxy

            # Create the publishing processes for all new pairs
            # Iterate over the list of queues in the opposite list
            for op_queue_id, op_q in op_queue_list.items():
                if direction == "source":
                    pair_name = "{}-{}".format(queue_id, op_queue_id)
                    source_queue = queue_proxy
                    dest_queue = op_q
                else:
                    pair_name = "{}-{}".format(op_queue_id, queue_id)
                    source_queue = op_q
                    dest_queue = queue_proxy

                # Start a publisher process to move items from the source
                # queue to the destination queue
                self._log.info("Starting queue link for pair {}"
                               .format(pair_name))
                proc = Process(target=self.publisher,
                               name="ClientPublisher-{}".format(pair_name),
                               kwargs={"name": self.name,
                                       "pair_name": pair_name,
                                       "source_queue": source_queue,
                                       "dest_queue": dest_queue})
                proc.daemon = True
                proc.start()
                self.clientPairPublishers[text(pair_name)] = proc

        return text(queue_id)

    def unRegisterQueue(self, queue_id, direction):
        """Detach a Queue proxy from this _PrPipe

        Returns the clientId that was removed

        Args:
            queue_id (string): ID of the client
            direction (string): source or destination

        Returns:
            string. ID of the client queue

        """
        # with self.queuesLock:
        #     if text(clientId) in self.clientQueues:
        #         self.clientQueues.pop(clientId)

        direction_caps = direction.capitalize()

        with self.queuesLock:
            queue_list = getattr(self, "clientQueues{}".format(direction_caps))
            if text(queue_id) in queue_list:
                queue_list.pop(queue_id)

            # Create the publishing processes for all new pairs
            op_direction_caps = "Destination" if direction == "source" \
                else "Source"
            op_queue_list = getattr(self, "clientQueues{}"
                                    .format(op_direction_caps))

            # Iterate over the list of queues in the opposite list
            for op_queue_id, op_q in op_queue_list.items():
                if direction == "source":
                    pair_name = "{}-{}".format(queue_id, op_queue_id)
                else:
                    pair_name = "{}-{}".format(op_queue_id, queue_id)

                # Stop the publisher for the pair
                self.clientPairPublishers[text(pair_name)].terminate()

        return text(queue_id)

    def isEmpty(self, queue_id=None):
        """Checks whether the primary Queue or any clients' Queues are empty

        Returns True ONLY if ALL queues are empty if clientId is None
        Returns True ONLY if both main queue and specified client queue are
            empty when clientId is provided

        Args:
            queue_id (string): ID of the client

        Returns:
            bool
        """
        with self.queuesLock:
            if queue_id is not None:
                self._log.debug("Checking if {} is empty".format(queue_id))
                empty = True

                # If this is a downstream queue, we need to make sure all
                # upstream queues are empty, too
                if queue_id in self.clientQueuesDestination.keys():
                    self._log.debug("First checking upstream queue(s) of {}"
                                    .format(queue_id))

                    for source_id in self.clientQueuesSource.keys():
                        source_empty = self.getQueue(source_id).empty()
                        self._log.info("Source {} is empty: {}"
                                        .format(source_id, source_empty))
                        empty = empty and source_empty

                queue_empty = self.getQueue(queue_id).empty()
                empty = empty and queue_empty
                self._log.info("{} is empty: {}"
                                .format(queue_id, queue_empty))

            else:
                empty = True

                for q in list(self.clientQueuesSource.values()):
                    empty = empty and q.empty()

                for q in list(self.clientQueuesDestination.values()):
                    empty = empty and q.empty()

            self._log.debug("Reporting queue link empty: {}".format(empty))
            return empty

    def destructiveAudit(self, direction):
        """Print a line from each client Queue attached to this _PrPipe

        Args:
            direction (string): source or destination

        This is a destructive operation, as it *removes* a line from each Queue
        """
        # with self.queuesLock:
        #     for clientId in list(self.clientQueues):
        #         try:
        #             self._log.info("clientId {}: {}"
        #                            .format(text(clientId),
        #                                    self.getLine(clientId)))
        #         except Empty:
        #             self._log.info("clientId {} is empty"
        #                            .format(text(clientId)))

        direction_caps = direction.capitalize()

        with self.queuesLock:
            queue_list = getattr(self, "clientQueues{}".format(direction_caps))

            for queue_id in list(queue_list):
                try:
                    self._log.info("queue_id {}: {}"
                                   .format(text(queue_id),
                                           self.getLine(queue_id)))
                except Empty:
                    self._log.info("queue_id {} is empty"
                                   .format(text(queue_id)))
