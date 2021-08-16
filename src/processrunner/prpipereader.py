# -*- coding: utf-8 -*-
"""Custom pipe-queue adapter to read from a pipe and write *text* content to
thread-safe queues"""
from __future__ import unicode_literals

import logging

from .contentwrapper import ContentWrapper
from .prpipe import _PrPipe


# Private class only intended to be used by ProcessRunner
# Works around (https://bryceboe.com/2011/01/28/
# the-python-multiprocessing-queue-and-large-objects/ with large objects)
# by using ContentWrapper to buffer large lines to disk
class _PrPipeReader(_PrPipe):
    """Custom pipe manager to capture the output of processes and store them in
       one more more dedicated thread-safe queues.

       Clients register their own queues.
    """

    def __init__(self, queue, pipeHandle=None, name=None, log_name=None):
        """
        Args:
            pipeHandle (pipe): Pipe to monitor for records
        """
        # Initialize the parent class
        # pylint: disable=bad-super-call
        # Py3 supports super().__init__; this form is kept for backward compat
        super(type(self), self).__init__(queue=queue,
                                         subclass_name=__name__,
                                         queue_direction="source",
                                         name=name,
                                         pipe_handle=pipeHandle,
                                         log_name=log_name)

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
            # Flush out any potentially waiting content
            pipe_handle.flush()

            for line in iter(pipe_handle.readline, ''):
                log.info("Read line, trying to get a lock")
                with queue_lock:
                    log.info("Enqueing line of length %s", len(line))
                    line_content = ContentWrapper(line)
                    queue.put(line_content)

                # Check whether we should stop now
                if stop_event.is_set():
                    log.info("Asked to stop")
                    break

            log.info("Closing pipe handle")
            pipe_handle.close()

        log.info("Sub-process complete")

    def get_line(self, client_id, timeout=-1):
        """Retrieve a line from a given client's Queue

        Args:
            client_id (string): ID of the client
            timeout (float): <0 for get_nowait behavior, otherwise use
                           get(timeout=timeout); in seconds

        Returns:
            <element from Queue>

        Raises:
            Empty
        """
        self._log.debug("Trying to get a line for client %s", client_id)

        # Throws Empty
        client_q = self.get_queue(client_id)

        # Throws Empty
        if timeout < 0:
            line = client_q.get_nowait()

        else:
            line = client_q.get(timeout=timeout)

        # Mark the item as retrieved
        client_q.task_done()

        self._log.debug("Returning line to client %s", client_id)

        return line.value
