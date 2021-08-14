# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import multiprocessing
import os
import sys
import time
import unittest
from tempfile import NamedTemporaryFile

from parameterized import parameterized
from processrunner.exceptionhandler import ProcessAlreadyStarted
from processrunner.timer import Timer

from processrunner import ProcessRunner
from processrunner import runCommand
from tests.tests.spinner import Spinner

'''
# Watch the main queue fill and empty
command = [self.sampleCommandPath,"--lines","100000","--block","1000","--sleep","0.01"]
proc = ProcessRunner(command)

t = Thread(target=printQsize, kwargs={"proc":proc})
t.daemon = True
t.start()

output = proc.collectLines()
result = proc.wait().poll()
'''
def printQsize(proc):
    q = proc.pipes['stdout'].queue
    while proc.is_alive() or q.qsize() > 0:
        print(q.qsize())
        time.sleep(0.01)


class ProcessRunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.sampleCommandDir = os.path.join(os.path.dirname(__file__), "..")
        sampleCommandPath = os.path.join(os.path.dirname(__file__), '..', 'test-output-script.py')
        self.sampleCommandPath = sampleCommandPath

        self.spinner = Spinner()

        self.manager = multiprocessing.Manager()


class ProcessRunnerCoreTestCase(ProcessRunnerTestCase):
    @parameterized.expand([
        [True, False],  # Autostart, no need to manually trigger start
        [False, True]   # Trigger manual start at A
    ])
    def test_processrunner_correct_stdout_count(self, autostart, manualstart):
        testLen = 1000
        command = [sys.executable, self.sampleCommandPath, "--lines", "{}".format(testLen), "--block", "1", "--sleep", "0"]
        t = Timer(interval=5)
        print("Before with-as time: {}ms".format(t.lap()))
        with ProcessRunner(command, autostart=autostart) as proc:
            print("After with-as time: {}ms".format(t.lap()))

            # Verify start works when placed before collectLines
            if manualstart:
                proc.start()

            # Store process output
            print("Before collectLines time: {}ms".format(t.lap()))

            output = proc.collectLines()
            print("Following collectLines time: {}ms".format(t.lap()))

            result = proc.wait().poll()
            print("Following proc.wait().poll() time: {}ms".format(t.lap()))

        length = len(output)

        # Verify the count of lines is identical
        message = 'Count of output lines unexpected: Expected ' \
                  '{} got {}. Top 20:\n{}'.format(testLen,
                                                  length,
                                                  "\n".join(output[:20]))
        self.assertEqual(length, testLen, message)

        # Verify the test script exit code was 0
        self.assertEqual(result, 0, 'Test script return code not zero')

    @parameterized.expand([
        [True, True, False],
        [False, True, True]
    ])
    def test_processrunner_second_start_raises_exception_once(self,
                                                              autostart,
                                                              start_a,
                                                              start_b):
        command = ["echo", "bonjour"]
        with ProcessRunner(command, autostart=autostart) as proc:
            # Duplicate proc.starts()
            with self.assertRaises(ProcessAlreadyStarted):
                if start_a:
                    proc.start()
                if start_b:
                    proc.start()

    @parameterized.expand([
        [True],
        [False]
    ])
    def test_processrunner_second_start_raises_exception_repeated(self,
                                                                  autostart):
        testLen = 5
        command = ["echo", "bonjour"]
        with ProcessRunner(command, autostart=autostart) as proc:
            # Trigger the process to start if it wasn't done by autostart
            if not autostart:
                proc.start()

            # Run start N times
            # Duplicate proc.starts()
            for i in range(0, testLen):
                try:
                    proc.start()
                except ProcessAlreadyStarted:
                    pass

            # Trigger one more that is the test
            with self.assertRaises(ProcessAlreadyStarted):
                proc.start()

    def test_processrunner_leak_check(self):
        limit = 100
        command = ["echo", "bonjour"]
        openFilesCommand = ["lsof", "-p", str(os.getpid())]

        openFilesStart = runCommand(openFilesCommand, returnAllContent=True)

        for i in range(limit):
            self.spinner.spin()
            with ProcessRunner(command) as proc:
                discard = proc.collectLines()

        openFilesEnd = runCommand(openFilesCommand, returnAllContent=True)

        self.assertEqual(len(openFilesStart),
                         len(openFilesEnd),
                         "Open file count changed: Start {} to End {}".format(len(openFilesStart), len(openFilesEnd)))

    def test_processrunner_onek_check_content(self):
        textIn = "a" * 2**10  # "a" repeated 1,024 times

        with NamedTemporaryFile() as tempFile:
            tempFile.write(textIn.encode("utf-8"))
            tempFile.flush()
            command = ["cat", tempFile.name]

            with ProcessRunner(command) as proc:
                textOut = proc.collectLines()[0]

        self.assertEqual(len(textIn),
                         len(textOut),
                         "Returned text not the same length: in {}, out {}".format(len(textIn), len(textOut)))

    def test_processrunner_onem_check_content(self):
        """Checks the integrity of the inter-process locking mechanisms"""
        textIn = "a" * 2**22  # a * 2**20 is "a" repeated 1,048,576 times, 22 is 4,194,304

        with NamedTemporaryFile() as tempFile:
            tempFile.write(textIn.encode("utf-8"))
            tempFile.flush()
            command = ["cat", tempFile.name]

            with ProcessRunner(command) as proc:
                textOut = proc.collectLines()[0]  # < Sometimes fails with index out of range

        self.assertEqual(len(textIn),
                         len(textOut),
                         "Returned text not the same length: in {}, out {}".format(len(textIn), len(textOut)))

    def test_processrunner_check_emoji_content(self):
        """Verifies compatibility with extended characters"""
        textIn = "😂" * 10
        command = ["echo", textIn]

        with ProcessRunner(command) as proc:
            textOut = proc.collectLines()[0]

        self.assertEqual(textIn,
                         textOut,
                         "Returned unicode text is not equivalent: In {}, Out {}".format(textIn, textOut))

    def test_processrunner_check_onem_emoji_content(self):
        """Checks the integrity of the inter-process locking mechanisms with unicode text"""
        textIn = "😂" * 2**22  # a * 2**20 is "a" repeated 1,048,576 times, 22 is 4,194,304

        with NamedTemporaryFile() as tempFile:
            tempFile.write(textIn.encode("utf-8"))
            tempFile.flush()
            command = ["cat", tempFile.name]

            with ProcessRunner(command) as proc:
                fullText = proc.collectLines()
                textOut = fullText[0]  # < Sometimes fails with index out of range

        self.assertEqual(len(textIn),
                         len(textOut),
                         "Returned text not the same length: in {}, out {}".format(len(textIn), len(textOut)))

    def test_processrunner_check_mixed_ascii_emoji_content(self):
        textIn = "a😂" * 10
        command = ["echo", textIn]

        with ProcessRunner(command) as proc:
            textOut = proc.collectLines()[0]

        self.assertEqual(textIn,
                         textOut,
                         "Returned unicode text is not equivalent: In {}, Out {}".format(textIn, textOut))

    def test_processrunner_getexpandinglist_raises_error_stdin(self):
        command = ["echo", "bonjour"]

        with ProcessRunner(command) as proc:
            self.assertRaises(ValueError,
                              proc.getExpandingList,
                              procPipeName="stdin")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerCoreTestCase)
    unittest.TextTestRunner(verbosity=3).run(suite)
