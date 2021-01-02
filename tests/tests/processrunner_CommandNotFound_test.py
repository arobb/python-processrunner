# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
import time
import unittest

from tests.tests import context
from processrunner import ProcessRunner
from processrunner import CommandNotFound

'''
'''
class ProcessRunnerCommandNotFoundTestCase(unittest.TestCase):
    def setUp(self):
        sampleCommandPath = os.path.join(os.path.dirname(__file__), '..', 'test-output-script.py')
        self.sampleCommandPath = sampleCommandPath

    def test_processrunner_correct_commandnotfound_raised(self):
        with self.assertRaises(CommandNotFound):
            ProcessRunner([self.sampleCommandPath + "badpath"])


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerCommandNotFoundTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
