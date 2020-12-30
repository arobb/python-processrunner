# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import random
import sys
import time
import unittest

from tests.tests import context
from processrunner import runCommand

'''
'''
class ProcessRunnerRunCommandTestCase(unittest.TestCase):
    def setUp(self):
        self.sampleCommandDir = os.path.dirname(__file__)
        sampleCommandPath = os.path.join(os.path.dirname(__file__), '..', 'test-output-script.py')
        self.sampleCommandPath = sampleCommandPath

    def test_processrunner_runCommand_check_zero_return(self):
        returnCodeIn = 0
        command = [self.sampleCommandPath, "--lines", "0", "--return-code", str(returnCodeIn)]
        returnCodeOut = runCommand(command)

        self.assertEqual(returnCodeIn,
                         returnCodeOut,
                         "Return code from runCommand not returning {}, instead {}".format(returnCodeIn, returnCodeOut))

    def test_processrunner_runCommand_check_one_return(self):
        returnCodeIn = 1
        command = [self.sampleCommandPath, "--lines", "0", "--return-code", str(returnCodeIn)]
        returnCodeOut = runCommand(command)

        self.assertEqual(returnCodeIn,
                         returnCodeOut,
                         "Return code from runCommand not returning {}, instead {}".format(returnCodeIn, returnCodeOut))

    def test_processrunner_runCommand_check_onetwoseven_return(self):
        returnCodeIn = 127
        command = [self.sampleCommandPath, "--lines", "0", "--return-code", str(returnCodeIn)]
        returnCodeOut = runCommand(command)

        self.assertEqual(returnCodeIn,
                         returnCodeOut,
                         "Return code from runCommand not returning {}, instead {}".format(returnCodeIn, returnCodeOut))

    def test_processrunner_runCommand_check_twofivefive_return(self):
        returnCodeIn = 255
        command = [self.sampleCommandPath, "--lines", "0", "--return-code", str(returnCodeIn)]
        returnCodeOut = runCommand(command)

        self.assertEqual(returnCodeIn,
                         returnCodeOut,
                         "Return code from runCommand not returning {}, instead {}".format(returnCodeIn, returnCodeOut))

    def test_processrunner_runCommand_check_zero_return_combined(self):
        returnCodeIn = 0
        command = [self.sampleCommandPath, "--lines", "0", "--return-code", str(returnCodeIn)]
        returnCodeOut = runCommand(command, returnAllContent=True)[0]

        self.assertEqual(returnCodeIn,
                         returnCodeOut,
                         "Return code from runCommand not returning {}, instead {}".format(returnCodeIn, returnCodeOut))

    def test_processrunner_runCommand_check_one_return_combined(self):
        returnCodeIn = 1
        command = [self.sampleCommandPath, "--lines", "0", "--return-code", str(returnCodeIn)]
        returnCodeOut = runCommand(command, returnAllContent=True)[0]

        self.assertEqual(returnCodeIn,
                         returnCodeOut,
                         "Return code from runCommand not returning {}, instead {}".format(returnCodeIn, returnCodeOut))

    def test_processrunner_runCommand_check_onetwoseven_return_combined(self):
        returnCodeIn = 127
        command = [self.sampleCommandPath, "--lines", "0", "--return-code", str(returnCodeIn)]
        returnCodeOut = runCommand(command, returnAllContent=True)[0]

        self.assertEqual(returnCodeIn,
                         returnCodeOut,
                         "Return code from runCommand not returning {}, instead {}".format(returnCodeIn, returnCodeOut))

    def test_processrunner_runCommand_check_twofivefive_return_combined(self):
        returnCodeIn = 255
        command = [self.sampleCommandPath, "--lines", "0", "--return-code", str(returnCodeIn)]
        returnCodeOut = runCommand(command, returnAllContent=True)[0]

        self.assertEqual(returnCodeIn,
                         returnCodeOut,
                         "Return code from runCommand not returning {}, instead {}".format(returnCodeIn, returnCodeOut))

    def test_processrunner_runCommand_basic_check_content(self):
        textIn = "Hello"
        command = ["echo", textIn]
        returnData = runCommand(command, returnAllContent=True)
        textOut = returnData[1][0]

        self.assertEqual(textIn,
                         textOut,
                         "Returned text not the same: in '{}', out '{}'".format(textIn, textOut))

    def test_processrunner_runCommand_onek_check_content(self):
        textIn = "a" * 1024
        command = ["echo", textIn]
        returnData = runCommand(command, returnAllContent=True)
        textOut = returnData[1][0]

        self.assertEqual(textIn,
                         textOut,
                         "Returned text not the same: in '{}', out '{}'".format(textIn, textOut))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerRunCommandTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
