# -*- coding: utf-8 -*-
import os
import sys
import time
import unittest

from tests.tests import context
from processrunner import which

'''
'''
class ProcessRunnerCommandNotFoundTestCase(unittest.TestCase):
    def setUp(self):
        self.sampleCommandDir = os.path.dirname(__file__)
        sampleCommandPath = os.path.join(os.path.dirname(__file__), '..', 'test-output-script.py')
        self.sampleCommandPath = sampleCommandPath

    def test_processrunner_which_found(self):
        self.assertEqual(which("python"),
                         sys.executable,
                         "which is not properly resolving")

    def test_processrunner_which_notfound(self):
        self.assertNotEqual(which("python-foo"),
                            sys.executable,
                            "which is inappropriately resolving")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerCommandNotFoundTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
