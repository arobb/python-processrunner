# -*- coding: utf-8 -*-
#
# ProcessRunnerMaplinesTestCase seems to reliably reproduce an error where the return code
#   registered for the client is incorrect (0, instead of 1). I have been unable to
#   track down where this is coming from. AR June 2017
#
from __future__ import unicode_literals
import logging
import logging.config
import os
import sys
import time
import unittest

from tests.tests import context
from tests.tests.spinner import Spinner
from processrunner import ProcessRunner, writeOut

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


class ProcessRunnerMaplinesTestCase(ProcessRunnerTestCase):

    def test_processrunner_return_code_with_maplines(self):
        command = [self.sampleCommandPath, "--lines", "5", "--block", "1", "--sleep", "0", "--return-code", "1"]

        def run():
            proc = ProcessRunner(command)

            # Key aspect
            # When using the threading library, and writeOut writes to a pipe, the return code
            # doesn't always come back as expected
            # Isn't fixed even after the switch to multiprocessing
            with open("/dev/null", 'a') as devnull:
                proc.mapLines(writeOut(pipe=devnull, outputPrefix="test-output-script.py-stdout> "), procPipeName="stdout")
                proc.mapLines(writeOut(pipe=sys.stderr, outputPrefix="test-output-script.py-stderr> "), procPipeName="stderr")
                proc.wait()
                result = proc.poll()

                if result != 1:
                    print("")
                    print("Result output isn't 1!: '" + str(result) + "'")
                    print("Waiting another moment...")
                    time.sleep(.1)
                    result = proc.poll()
                    print("Next Poll(): " + str(result))

            # proc.terminate()
            proc.shutdown()

            if result != 1:
                errorText = "Result output isn't 1!: '{}'".format(result)
                raise ValueError(errorText)

            return result

        # Run a bunch of times
        runs = 200
        totalReturn = 0
        for i in range(runs):
            totalReturn += run()
            self.spinner.spin()

        self.assertEqual(totalReturn, runs,
            'Bad return code found! Expecting ' + str(runs) + ' got ' + str(totalReturn))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerMaplinesTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
