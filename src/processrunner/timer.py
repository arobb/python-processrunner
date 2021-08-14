# -*- coding: utf-8 -*-
"""Class to house time-related convenience functions."""
import datetime
import math  # pylint: disable=no-name-in-module
import time


class Timer:
    """Used to help time events."""

    def __init__(self, interval=10):
        """Timing events: Establish start time reference for lap and interval

        ``interval`` supports resolution to microseconds. Default is 10
        seconds.

        :param float interval: Seconds between intervals
        """
        self.interval_period = interval
        self.start_time = self.now()
        self.last_interval_count = 0

    @staticmethod
    def now():
        """Returns the current Unix epoch time in seconds as a float

        Returned value has resolution to microseconds.

        :return: float seconds
        """
        current = time.mktime(datetime.datetime.now().timetuple()) \
            + datetime.datetime.now().microsecond / 1000000.0

        return float(current)

    def lap(self):
        """Return seconds since this instance was created.

        :return: float"""
        return self.now() - self.start_time

    def interval(self):
        """Return True if we have exceeded the interval since we started or
        last called interval().

        :return: bool"""

        # Get the current lap time
        lap = int(self.lap() * 1000000)  # full resolution as an int
        interval = int(self.interval_period * 1000000)

        # How many intervals have elapsed since this instance was created?
        interval_count_float = lap / interval  # integer division

        # Round down the number of intervals to a whole number
        # pylint: disable=c-extension-no-member
        interval_count_floor = int(math.floor(interval_count_float))
        # pylint: enable=c-extension-no-member

        # If an interval has passed since the last one was recorded,
        # return true
        # pylint: disable=no-else-return
        if interval_count_floor > self.last_interval_count:
            self.last_interval_count = interval_count_floor
            return True
        else:
            return False
