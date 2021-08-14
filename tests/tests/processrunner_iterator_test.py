# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import sys
import time
import unittest

from processrunner import ProcessRunner

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


class ProcessRunnerIteratorTestCase(ProcessRunnerTestCase):

    def test_processrunner_basic_iterate(self):
        """Iterate over stdout
        """
        test_len = 10
        command = [sys.executable, self.sampleCommandPath, "--lines", "{}".format(test_len), "--block", "1", "--sleep", "0"]
        output = []

        with ProcessRunner(command) as proc:
            for line in proc.stdout:
                output.append(line.rstrip('\n'))

        self.assertEqual(test_len,
                         len(output),
                         "Length not right: Correct {}, actual {}"
                         .format(test_len, len(output)))

    def test_processrunner_readline(self):
        """Iterate over stdout
        """
        test_len = 10
        command = [sys.executable, self.sampleCommandPath, "--lines", "{}".format(test_len), "--block", "1", "--sleep", "0"]
        output = []

        with ProcessRunner(command) as proc:
            for line in iter(proc.stdout.readline, ''):
                output.append(line.rstrip('\n'))

        self.assertEqual(test_len,
                         len(output),
                         "Length not right: Correct {}, actual {}"
                         .format(test_len, len(output)))

    def test_processrunner_readline_both_pipes(self):
        """Iterate over stdout and stderr
        """
        test_len = 10
        command = [sys.executable,
                   self.sampleCommandPath,
                   "--lines",
                   "{}".format(test_len),
                   "--block", "1",
                   "--sleep", "0",
                   "--out-pipe", "both"]
        output = []

        with ProcessRunner(command) as proc:
            for line in iter(proc.output.readline, ''):
                output.append(line.rstrip('\n'))

        self.assertEqual(test_len * 2,
                         len(output),
                         "Length not right: Correct {}, actual {}"
                         .format(test_len * 2, len(output)))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerIteratorTestCase)
    unittest.TextTestRunner(verbosity=3).run(suite)
