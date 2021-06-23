# -*- coding: utf-8 -*-
"""Class to house time-related convenience functions."""

import datetime
import math
import time


class Timer:
    """Used to help time events."""

    def __init__(self, interval_ms=10000):
        self.interval_ms = interval_ms
        self.start_time = self.now()
        self.last_interval_count = 0

    @staticmethod
    def now():
        """Returns the current time in milliseconds."""
        current = time.mktime(datetime.datetime.now().timetuple()) \
            + datetime.datetime.now().microsecond / 1000000.0
        current *= 1000

        return int(current)

    def lap(self):
        """Return milliseconds since this instance was created."""
        return self.now() - self.start_time

    def interval(self):
        """Return True if we have exceeded the interval since we started or
        last called interval()."""

        # Get the current lap time
        lap = self.lap()

        # How many intervals have elapsed since this instance was created?
        interval_count_float = lap / self.interval_ms

        # Round down the number of intervals to a whole number
        interval_count_floor = int(math.floor(interval_count_float))

        # If an interval has passed since the last one was recorded,
        # return true
        if interval_count_floor > self.last_interval_count:
            self.last_interval_count = interval_count_floor
            return True
        else:
            return False
