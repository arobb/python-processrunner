# -*- coding: utf-8 -*-
# Provide test modules an easy way to import project stuff

import logging
import logging.config
import os
import sys

# Configure the package search path to include the main package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configure log detail
log_config_fname = os.path.dirname(__file__) + "/../content/testing_logging_config.ini"
logging.config.fileConfig(fname=log_config_fname, disable_existing_loggers=False)