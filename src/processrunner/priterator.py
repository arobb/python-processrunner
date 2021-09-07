# -*- coding: utf-8 -*-
"""Iterate over list proxies from ProcessRunner"""
import random
import time

from . import settings
from .classtemplate import PRTemplate
from .exceptionhandler import Timeout
from .timer import Timer


class PrIterator(PRTemplate):
    """Iterate over list proxies from ProcessRunner"""
    def __init__(self, output_list, events_dict, timeout=None, log_name=None):
        # Unique ID
        # Not used for cryptographic purposes, so excluding from Bandit
        self.id = \
            ''.join([random.choice(  # nosec
                '0123456789ABCDEF') for x in range(6)])

        self.log_name = log_name

        self.output_list = output_list
        self.events_dict = events_dict
        self.timeout = timeout

        self._log = None
        self._initialize_logging_with_id(__name__)

    def __iter__(self):
        return self

    def __next__(self):
        # Let a user know if we're stuck in the loop
        # Use a timer so we don't write the notification on every iteration
        interval_delay = settings.config["NOTIFICATION_DELAY"]
        loop_timer = Timer(interval=interval_delay)

        # Start a timeout timer
        if self.timeout is not None:
            timeout_timer = Timer(interval=self.timeout)

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

    def __repr__(self):
        return "\n".join(self)

    def complete(self):
        """Check whether the list populator is finished"""
        complete = True

        for name, event in self.events_dict.items():
            self._log.debug("Checking if %s client has finished", name)
            complete = complete and event.is_set()

        self._log.debug("Process complete status: %s", complete)

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
