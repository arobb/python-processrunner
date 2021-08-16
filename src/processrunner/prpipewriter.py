# -*- coding: utf-8 -*-
"""Custom queue-pipe adapter to read from thread-safe queues and write their
contents to a pipe"""
from __future__ import unicode_literals

import logging

try:  # Python 2.7
    from Queue import Empty
except ImportError:  # Python 3.x
    from queue import Empty

from .prpipe import _PrPipe
from .contentwrapper import ContentWrapper


# Private class only intended to be used by ProcessRunner
# Works around (https://bryceboe.com/2011/01/28/
# the-python-multiprocessing-queue-and-large-objects/ with large objects)
# by using ContentWrapper to buffer large lines to disk
class _PrPipeWriter(_PrPipe):
    """Custom pipe manager to read thread-safe queues and write their contents
        to an outbound pipe.

       Clients register their own queues.
    """

    def __init__(self, queue, pipeHandle=None, name=None, log_name=None):
        """
        Args:
            pipeHandle (pipe): Pipe to write records to
        """
        # Initialize the parent class
        # pylint: disable=bad-super-call
        # Py3 supports super().__init__; this form is kept for backward compat
        super(type(self), self).__init__(queue=queue,
                                         subclass_name=__name__,
                                         queue_direction="destination",
                                         name=name,
                                         pipe_handle=pipeHandle,
                                         log_name=log_name)

    @staticmethod
    def queue_pipe_adapter(pipe_name,
                           pipe_handle,
                           queue,
                           queue_lock,
                           stop_event):
        """Copy lines from a local multiprocessing.JoinableQueue into a pipe

        Runs in a separate process, started by __init__. Does not close the
        pipe when done writing.

        Args:
            pipe_name (string): Name of the pipe we will write to
            pipe_handle (pipe): Pipe to write to
            queue (Queue): Queue to read from
            queue_lock (Lock): Lock used to indicate a write in progress
            stop_event (Event): Used to determine whether to stop the process
        """
        logger_name = "{}.queue_pipe_adapter.{}".format(__name__, pipe_name)
        log = logging.getLogger(logger_name)
        log.addHandler(logging.NullHandler())

        log.info("Starting writer process")
        if pipe_handle.closed:
            log.warning("Pipe handle is already closed")

        else:
            while True:
                try:
                    # line = queue.get_nowait()
                    line = queue.get(timeout=0.05)

                    # Extract the content if the line is in a ContentWrapper
                    # Make sure there is a trailing newline
                    log.info("Writing line to %s", pipe_name)
                    if isinstance(line, ContentWrapper):
                        line_str = line.value.rstrip('\n')
                        pipe_handle.write("{}\n".format(line_str))
                    else:
                        line.rstrip('\n')
                        pipe_handle.write("{}\n".format(line))

                    # Flush the pipe to make sure it gets to the process
                    pipe_handle.flush()

                    # Signal to the queue that we are done processing the line
                    queue.task_done()

                    # Exit if we are asked to stop
                    if stop_event.is_set():
                        log.info("Asked to stop")
                        break

                except Empty:
                    # time.sleep(0.01)
                    log.debug("No line currently available for %s", pipe_name)

                    # Exit if we are asked to stop
                    if stop_event.is_set():
                        log.info("Asked to stop")
                        break

        log.info("Sub-process complete")

    def put_line(self, client_id, line):
        """Adds a line to a given client's Queue

        Args:
            client_id (string): ID of the client
            line (string): The content to add to the queue
        """
        client_q = self.get_queue(client_id)

        if isinstance(line, ContentWrapper):
            client_q.put(line)
        else:
            client_q.put(ContentWrapper(line))
