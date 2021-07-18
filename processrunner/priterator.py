# -*- coding: utf-8 -*-
import logging
import random
import time

from . import settings
from .timer import Timer
from .exceptionhandler import Timeout


class PrIterator(object):
    """Iterate over list proxies from ProcessRunner"""
    def __init__(self, output_list, events_dict, timeout=None, log_name=None):
        # Unique ID
        self.id = \
            ''.join([random.choice('0123456789ABCDEF') for x in range(6)])
        self.log_name = log_name

        self.output_list = output_list
        self.events_dict = events_dict
        self.settimeout(timeout)

        self._initializeLogging()

    def __iter__(self):
        return self

    def __next__(self):
        # Let a user know if we're stuck in the loop
        # Use a timer so we don't write the notification on every iteration
        interval_delay = settings.config["NOTIFICATION_DELAY"] * 1000
        loop_timer = Timer(interval_ms=interval_delay)

        # Start a timeout timer
        if self.timeout is not None:
            timeout_timer = Timer(interval_ms=self.timeout * 1000)

        # Wait until the list has content or we're done
        while len(self.output_list) == 0 and not self.complete():

            # Check for a timeout
            if self.timeout is not None:
                if timeout_timer.interval():
                    raise Timeout("_PrIterator timeout at {} seconds"
                                  .format(self.timeout))

            # Let the user know what's happening if we're delayed
            if loop_timer.interval():
                self._log.info("Not complete for {:.1f} seconds"
                               .format(loop_timer.lap() / 1000))

            # Pause for the next iteration
            time.sleep(0.001)

        # We're complete AND there is no content
        if len(self.output_list) == 0 and self.complete():
            raise StopIteration

        # We have content
        return self.output_list.pop(0)

    def _initializeLogging(self):
        if hasattr(self, '_log'):
            if self._log is not None:
                return

        # Logger name
        log_name = "{}-{}".format(__name__, self.id)

        if self.log_name is not None:
            log_name = "{}.{}".format(log_name, self.log_name)

        # Logging
        self._log = logging.getLogger(log_name)
        self.addLoggingHandler(logging.NullHandler())

    def addLoggingHandler(self, handler):
        """Pass-through for Logging's addHandler method"""
        self._log.addHandler(handler)

    def complete(self):
        """Check whether the list populator is finished"""
        complete = True

        for name, event in self.events_dict.items():
            self._log.debug("Checking if {} client has finished".format(name))
            complete = complete and event.is_set()

        self._log.debug("Process complete status: {}".format(complete))

        return complete

    def next(self):
        """Python 2 compatibility"""
        return self.__next__()

    def readline(self):
        """Mirrors some behavior of io.TextIOBase.readline

        Does not include the ``size`` argument

        :return string
        """
        try:
            return self.__next__()
        except StopIteration:
            return ''

    def readlines(self):
        """Get a complete list of line output

        :returns list
        """
        output = list()

        for line in iter(self.readline, ''):
            output.append(line)

        return output

    def settimeout(self, timeout):
        """Set timeout, in seconds"""
        self.timeout = timeout
