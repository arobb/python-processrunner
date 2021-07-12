# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import random
import signal
import sys
import time
import unittest

from parameterized import parameterized
from tempfile import NamedTemporaryFile
from codecs import getreader

from tests.tests import context
from processrunner import ProcessRunner
from processrunner.timer import Timer
from processrunner.exceptionhandler import ExceptionHandler
from processrunner.exceptionhandler import HandleNotSet
from processrunner.exceptionhandler import Timeout

class ProcessRunnerTestCase(unittest.TestCase):
    def setUp(self):
        sampleCommandPath = os.path.join(os.path.dirname(__file__), '..', 'test-output-script.py')
        self.sampleCommandPath = sampleCommandPath

    def test_processrunner_stdin(self):
        test_len = 10
        contentGeneratorCommand = [self.sampleCommandPath,
                                   "--lines", "{}".format(test_len),
                                   "--block", "1",
                                   "--sleep", "0"]

        with ProcessRunner(contentGeneratorCommand) as proc:

            output_text = ""
            force_fail = False
            try:
                output_text = proc.collectLines(timeout=1)
            except Timeout as e:
                print("Timed out")
                force_fail = True

            proc.closeStdin()
            proc.shutdown()

            if force_fail:
                message = "Timeout occurred, forcing an assertion failure"
                message = "{}\nInput: {} lines\n" \
                          "Output: {} lines".format(message,
                                                    test_len,
                                                    len(output_text))

                self.assertEqual(0, 1, message)

            self.assertEqual(len(output_text),
                             test_len,
                             "Not enough output!")

    # def test_processrunner_stdin(self):
    #     outputFile = NamedTemporaryFile()
    #     command = ['tee', outputFile.name]
    #     t = Timer(interval_ms=1000)
    #     force_fail = False
    #
    #     try:
    #         with ProcessRunner(command, autostart=False, stdin=True) as proc:
    #             # Get a queue that publishes to the process' stdin
    #             stdin_clientId, stdin_q = proc.registerForClientQueue("stdin")
    #             proc.start()
    #
    #             inputText = "Hello world! {}".format(random.randint(100, 999))
    #             stdin_q.put(inputText)
    #
    #             try:
    #                 proc.wait(timeout=1)
    #             except Timeout:
    #                 print("Forcing stdin closed")
    #                 force_fail = True
    #                 proc.closeStdin()
    #                 proc.run.send_signal(signal.SIGINT)  # Shouldn't have to
    #
    #             try:
    #                 proc.wait(timeout=1)
    #                 print("Complete")
    #             except Timeout:
    #                 print("Full timeout")
    #
    #             proc.closeStdin()
    #             proc.shutdown()
    #
    #             outputFile.seek(0)
    #             outputText = getreader("utf-8")(outputFile).read().rstrip('\n')
    #             print("Output text: {}".format(outputText))
    #
    #             if force_fail:
    #                 message = "Timeout occurred, forcing an assertion failure"
    #                 message = "{}\nInput:\n{}\nOutput:\n{}".format(message,
    #                                                                inputText,
    #                                                                outputText)
    #                 self.assertEqual(0, 1, message)
    #
    #             self.assertEqual(inputText,
    #                              outputText,
    #                              "The inputs and outputs don't match")
    #
    #     except HandleNotSet as e:
    #         print("Caught HandleNotSet:")
    #         ExceptionHandler(e)
    #
    #     finally:
    #         outputFile.close()

    # def test_processrunner_stdin_non_definitive_stop(self):
    #     outputFile = NamedTemporaryFile()
    #
    #     try:
    #         c1 = ProcessRunner(["tests/test-output-script.py"],
    #                            autostart=False)
    #         c2 = ProcessRunner(["grep", "Line: 2"], autostart=False)
    #
    #         c1 | c2
    #
    #         c1.start()
    #         c2.start()
    #
    #         print(c2.collectLines(timeout=1))
    #
    #         self.assertEqual(0, 1, "The inputs and outputs don't match")
    #
    #     except HandleNotSet as e:
    #         print("Caught HandleNotSet:")
    #         ExceptionHandler(e)
    #
    #     # except Exception as e:
    #     #     ExceptionHandler(e)
    #
    #     finally:
    #         outputFile.close()

if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
