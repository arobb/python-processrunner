# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import random
import sys
import time
import unittest

# See commented test below for details
# from io import StringIO
#
# try:
#     from unittest.mock import patch
# except ImportError:
#     from mock import patch

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

    def test_processrunner_runCommand_emoji_check_content(self):
        textIn = "😂" * 10
        command = ["echo", textIn]
        returnData = runCommand(command, returnAllContent=True)
        textOut = returnData[1][0]

        self.assertEqual(textIn,
                         textOut,
                         "Returned text not the same: in '{}', out '{}'".format(textIn, textOut))

    # No idea how to get this to run reliably. Patching stdout with multiprocessing appears... difficult
    # @patch('sys.stdout', new_callable=StringIO)
    # def test_processrunner_runCommand_emoji_check_stdout(self, mock_stdout):
    #     textIn = "😂" * 10
    #     command = ["echo", textIn]
    #
    #     outputPrefix = "Unicode Validation> "
    #     validationText = outputPrefix + textIn
    #     returnCodeOut = runCommand(command, outputPrefix=outputPrefix, returnAllContent=False)
    #
    #     self.assertEqual(0,  # echo standard return is 0
    #                      returnCodeOut,
    #                      "Something went wrong checking for unicode compliance, return code not zero: {}".format(
    #                          returnCodeOut
    #                      ))
    #
    #     mock_stdout.seek(0)
    #     textOut = mock_stdout.getvalue()
    #     self.assertEqual(validationText,
    #                      textOut,
    #                      "Console text not the same: input {}, output {}".format(validationText, textOut))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerRunCommandTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
