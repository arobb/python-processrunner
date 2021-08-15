# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import sys
import unittest
from multiprocessing import Manager

from processrunner.timer import Timer

from processrunner import ProcessRunner

'''
'''
class ProcessRunnerChainingTestCase(unittest.TestCase):
    def setUp(self):
        self.sampleCommandDir = os.path.join(os.path.dirname(__file__), "..")
        sampleCommandPath = os.path.join(self.sampleCommandDir,
                                         'test-output-script.py')
        self.sampleCommandPath = sampleCommandPath

        self.manager = Manager()

    def test_processrunner_chain_base(self):
        testLen = 10
        outputFilePath = os.path.join(self.sampleCommandDir,
                                      'content',
                                      'new-hello.txt')
        output_validation_queue = self.manager.Queue()

        def f(line):
            output_validation_queue.put(line)

        outputFile = open(outputFilePath, 'w+')

        contentGeneratorCommand = [self.sampleCommandPath,
                                   "--lines", "{}".format(testLen),
                                   "--block", "1",
                                   "--sleep", "0"]
        contentGeneratorProc = ProcessRunner(contentGeneratorCommand,
                                             autostart=False,
                                             log_name="generator")

        contentGeneratorProc.mapLines(lambda line: sys.stdout
                                      .write("generator: {}".format(line)),
                                      "stdout")

        contentWriterCommand = ["tee", outputFilePath]
        # contentWriterCommand = ["cat"]
        contentWriterProc = ProcessRunner(contentWriterCommand,
                                          autostart=False,
                                          log_name="writer")

        # Also write to a queue for us to check
        # Otherwise we don't know when to have tee stop
        contentWriterProc.mapLines(lambda line: f(line), "stdout")

        contentWriterProc.mapLines(lambda line: sys.stdout
                                   .write("writer: {}".format(line)),
                                   "stdout")

        contentWriterProc.mapLines(lambda line: sys.stdout
                                   .write("writer: {}".format(line)),
                                   "stderr")

        # Pipe stdout of the first process into stdin of the second without
        # losing access to the content
        contentGeneratorProc | contentWriterProc

        # Starts the generator
        # Timeout extended for slow tests when run in parallel
        inputText_list = contentGeneratorProc.collectLines(timeout=2)

        # Write another test to verify that we can have a long delay
        # Wait to start the writer to see if this will break anything
        # time.sleep(2)

        # Start the consumer ("writes" into to the stdin of the next process)
        contentWriterProc.start()

        # Give the commands some time to execute
        # This is so complicated because tee doesn't naturally exit unless
        # stdin is closed, but we don't know when to close stdin
        t = Timer(interval=2)
        while True:
            if len(inputText_list) == output_validation_queue.qsize():
                break

            if t.interval():
                print("Test length expired!")
                break

        inputText = "\n".join(inputText_list)

        outputFile.seek(0)
        outputText = outputFile.read().rstrip('\n')
        outputFile.close()

        print("Input text:")
        print(inputText)

        print("Output text:")
        print(outputText)

        contentGeneratorProc.shutdown()
        contentWriterProc.shutdown()

        self.assertEqual(inputText, outputText,
                         "Input and output text does not match")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerChainingTestCase)
    unittest.TextTestRunner(verbosity=3).run(suite)
