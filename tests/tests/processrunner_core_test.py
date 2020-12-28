# -*- coding: utf-8 -*-
import os
import sys
import time
import unittest

from tempfile import NamedTemporaryFile

from tests.tests import context
from tests.tests.spinner import Spinner
from processrunner import ProcessRunner
from processrunner import runCommand


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
    while proc.isAlive() or q.qsize() > 0:
        print(q.qsize())
        time.sleep(0.01)


class ProcessRunnerTestCase(unittest.TestCase):
    def setUp(self):
        sampleCommandPath = os.path.join(os.path.dirname(__file__), '..', 'test-output-script.py')
        self.sampleCommandPath = sampleCommandPath

        self.spinner = Spinner()


class ProcessRunnerCoreTestCase(ProcessRunnerTestCase):

    def test_processrunner_correct_stdout_count(self):
        testLen = 10000
        command = [self.sampleCommandPath, "--lines", str(testLen), "--block", "1", "--sleep", "0"]
        with ProcessRunner(command) as proc:
            output = proc.collectLines()
            result = proc.wait().poll()

        length = len(output)

        self.assertEqual(length, testLen,
            'Count of output lines unexpected: Expected '+str(testLen)+' got ' + str(length))

        self.assertEqual(result, 0,
            'Test script return code not zero')

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
        textIn = "a" * 2**20  # "a" repeated 1,048,576 times

        with NamedTemporaryFile() as tempFile:
            tempFile.write(textIn.encode("utf-8"))
            tempFile.flush()
            command = ["cat", tempFile.name]

            with ProcessRunner(command) as proc:
                textOut = proc.collectLines()[0]

        self.assertEqual(len(textIn),
                         len(textOut),
                         "Returned text not the same length: in {}, out {}".format(len(textIn), len(textOut)))

    def test_processrunner_multiline_check_content(self):
        pass


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerCoreTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
