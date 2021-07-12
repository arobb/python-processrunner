# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from builtins import str as text

#
# ProcessRunnerMaplinesTestCase seems to reliably reproduce an error where the return code
#   registered for the client is incorrect (0, instead of 1). I have been unable to
#   track down where this is coming from. AR June 2017
#
import multiprocessing
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

    def test_processrunner_check_multiple_clients(self):
        """Verifies compatibility with multiple readers"""
        textIn = "many😂" * 5
        command = ["echo", textIn]

        m = multiprocessing.Manager()

        client1 = m.list()
        client2 = m.list()

        def f1(line):
            client1.append(text(line).strip())

        def f2(line):
            client2.append(text(line).strip())

        with ProcessRunner(command, autostart=False) as proc:
            ml1 = proc.mapLines(f1, "stdout")
            ml2 = proc.mapLines(f2, "stdout")

            proc.start()
            proc.wait()  # Wait for the process to complete

            ml1.wait()  # Wait for mapLines to complete
            ml2.wait()  # Wait for mapLines to complete

            textOut1 = client1[0]
            textOut2 = client2[0]

        errors = list()

        if textIn != textOut1:
            errors.append("Returned unicode text from client1 is not "
                          "equivalent: In {}, Out {}".format(textIn, textOut1))

        if textIn != textOut2:
            errors.append("Returned unicode text from client1 is not "
                          "equivalent: In {}, Out {}".format(textIn, textOut2))

        self.assertListEqual(errors,
                             list(),
                             "errors occured:\n{}".format("\n".join(errors)))

    def test_processrunner_return_code_with_maplines_200_rounds(self):
        command = [self.sampleCommandPath, "--lines", "5", "--block", "1", "--sleep", "0", "--return-code", "1"]

        def run():
            proc = ProcessRunner(command)

            # Key aspect
            # When using the threading library, and writeOut writes to a pipe,
            # the return code doesn't always come back as expected
            # Isn't fixed even after the switch to multiprocessing
            with open("/dev/null", 'a') as devnull:
                proc.mapLines(writeOut(pipe=devnull, outputPrefix="test-output-script.py-stdout> "), procPipeName="stdout")
                proc.mapLines(writeOut(pipe=sys.stderr, outputPrefix="test-output-script.py-stderr> "), procPipeName="stderr")

                # This sleep shouldn't be needed, but prevents a race condition
                # ... eh maybe not. May not make any difference

                # See processrunner line 388
                # Calls out the concern that if clients aren't done reading it
                # would deadlock
                # Command.wait:
                #      while self.poll() is None or isAliveLocal() is True:
                #         time.sleep(0.01)

                # Try elminating the use of maplines and autostart=true

                # startMapLines called in ProcessRunner.wait and ProcessRunner.start
                # This doesn't call ProcessRunner.start...
                # time.sleep(0.1)  # 0.1 seems to reliably work, 0.01 reliably breaks

                # Try to see if an alternative to wait() will cause the same issue
                proc.wait(timeout=1)
                # proc.startMapLines()
                # while proc.poll() is None:
                #     time.sleep(0.01)

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
            # print("Run {}".format(i))
            totalReturn += run()
            self.spinner.spin()

        self.assertEqual(totalReturn, runs,
            'Bad return code found! Expecting ' + str(runs) + ' got ' + str(totalReturn))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerMaplinesTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
