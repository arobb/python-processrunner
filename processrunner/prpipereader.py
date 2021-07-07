# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str as text
from builtins import dict

import logging

from multiprocessing import Process, Lock

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from . import settings
from .prpipe import _PrPipe
from .contentwrapper import ContentWrapper


# Private class only intended to be used by ProcessRunner
# Works around (https://bryceboe.com/2011/01/28/
# the-python-multiprocessing-queue-and-large-objects/ with large objects)
# by using ContentWrapper to buffer large lines to disk
class _PrPipeReader(_PrPipe):
    """Custom pipe manager to capture the output of processes and store them in
       one more more dedicated thread-safe queues.

       Clients register their own queues.
    """

    def __init__(self, queue, pipeHandle=None, name=None):
        """
        Args:
            pipeHandle (pipe): Pipe to monitor for records
        """
        # Initialize the parent class
        super(type(self), self).__init__(queue=queue,
                                         subclass_name=__name__,
                                         queue_direction="source",
                                         name=name,
                                         pipe_handle=pipeHandle)

        # Store the queue in the correct orientation in the queue link
        # self.queue_link.registerQueue(queue_proxy=self.queue,
        #                               direction="source")

    @staticmethod
    def queue_pipe_adapter(pipe_name,
                           pipe_handle,
                           queue,
                           queue_lock,
                           stop_event):
        """Copy lines from a given pipe handle into a local threading.Queue

        Runs in a separate process, started by __init__. Closes pipe when done
        reading.

        Args:
            pipe_name (string): Name of the pipe we will read from
            pipe_handle (pipe): Pipe to read from
            queue (Queue): Queue to write to
            queue_lock (Lock): Lock used to indicate a write in progress
            stop_event (Event): Used to determine whether to stop the process
        """
        logger_name = "{}.queue_pipe_adapter.{}".format(__name__, pipe_name)
        log = logging.getLogger(logger_name)
        log.addHandler(logging.NullHandler())

        log.info("Starting reader process")
        if pipe_handle.closed:
            log.warning("Pipe handle is already closed")

        else:
            for line in iter(pipe_handle.readline, ''):
                log.info("Read line, trying to get a lock")
                with queue_lock:
                    log.info("Enqueing line of length {}".format(len(line)))
                    lineContent = ContentWrapper(line)
                    queue.put(lineContent)

                # Check whether we should stop now
                if stop_event.is_set():
                    log.info("Asked to stop")
                    break

            log.info("Closing pipe handle")
            pipe_handle.close()

        log.info("Sub-process complete")

    def getLine(self, clientId):
        """Retrieve a line from a given client's Queue

        Args:
            clientId (string): ID of the client

        Returns:
            <element from Queue>

        Raises:
            Empty
        """
        self._log.debug("Trying to get a line for client {}".format(clientId))

        # Throws Empty
        q = self.getQueue(clientId)
        line = q.get_nowait()
        q.task_done()

        self._log.debug("Returning line to client {}".format(clientId))

        return line.value
