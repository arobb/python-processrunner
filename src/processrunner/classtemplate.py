# -*- coding: utf-8 -*-
"""Template class to standardize repetitive functionality"""
# pylint: disable=too-few-public-methods

import logging


class PRTemplate(object):
    """A pattern to hold boilerplate code across ProcessRunner classes"""
    id = None
    log_name = None
    name = None
    _log = None

    def _initialize_logging(self, class_name):
        """Basic logging with class name

        Args:
            class_name (string): String to use for the class name
        """
        if getattr(self, "_log", None) is not None:
            return

        # Logging
        self._log = logging.getLogger(class_name)
        self.add_logging_handler(logging.NullHandler())

    def _initialize_logging_with_id(self, class_name):
        """Adds `self.id` to logger name after class name

        Args:
            class_name (string): String to use for the class name
        """
        if getattr(self, '_log', None) is not None:
            return

        # Logger name
        log_name = "{}-{}".format(class_name, self.id)

        # Logging
        self._log = logging.getLogger(log_name)
        self.add_logging_handler(logging.NullHandler())

    def _initialize_logging_with_log_name(self, class_name):
        """Use an extended name when recording log lines

        Will include `class_name`, `self.id`, `self.log_name`, and `self.name`
            if those are populated (in that order).

        Args:
            class_name (string): String to use for the class name
        """
        if getattr(self, '_log', None) is not None:
            return

        # Logger name
        log_name = "{}-{}".format(class_name, self.id)

        if getattr(self, 'log_name', None) is not None:
            log_name = "{}.{}".format(log_name, self.log_name)

        if getattr(self, 'name', None) is not None:
            log_name = "{}.{}".format(log_name, self.name)

        # Logging
        self._log = logging.getLogger(log_name)
        self.add_logging_handler(logging.NullHandler())

    def add_logging_handler(self, handler):
        """Add a logging handler to the logger

        Args:
            handler (logging.Handler): A logging handler
        """
        self._log.addHandler(handler)
