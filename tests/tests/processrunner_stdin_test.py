# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import random
import sys
import time
import unittest

from parameterized import parameterized
from tempfile import NamedTemporaryFile
from codecs import getreader

from tests.tests import context
from processrunner import ProcessRunner
from processrunner.exceptionhandler import ExceptionHandler
from processrunner.exceptionhandler import HandleNotSet


class ProcessRunnerTestCase(unittest.TestCase):
    def test_processrunner_stdin(self):
        outputFile = NamedTemporaryFile()
        command = ['tee', outputFile.name]

        try:
            with ProcessRunner(command, autostart=False, stdin=True) as proc:
                # Get a queue that publishes to the process' stdin
                stdin_clientId, stdin_q = proc.registerForClientQueue("stdin")
                proc.start()

                inputText = "Hello world! {}".format(random.randint(100, 999))
                stdin_q.put(inputText)
                # time.sleep(.1)  # 100ms for tee to push the input to tempfile

                # Make sure any output is available in output queues
                proc.flush()

                proc.closeStdin()
                proc.shutdown()

                outputFile.seek(0)
                outputText = getreader("utf-8")(outputFile).read()

                self.assertEqual(inputText,
                                 outputText,
                                 "The inputs and outputs don't match")

        except HandleNotSet as e:
            print("Caught HandleNotSet:")
            ExceptionHandler(e)

        except Exception as e:
            ExceptionHandler(e)

        finally:
            outputFile.close()


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
