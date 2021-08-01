# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import time
import unittest
from tempfile import NamedTemporaryFile

from parameterized import parameterized

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
    while proc.isAlive() or q.qsize() > 0:
        print(q.qsize())
        time.sleep(0.01)


class ProcessRunnerTestCase(unittest.TestCase):
    def setUp(self):
        self.sampleCommandDir = os.path.join(os.path.dirname(__file__), "..")
        sampleCommandPath = os.path.join(os.path.dirname(__file__), '..', 'test-output-script.py')
        self.sampleCommandPath = sampleCommandPath


class ProcessRunnerCoreTestCase(ProcessRunnerTestCase):

    def test_processrunner_write_to_files_bad_name(self):
        """Valdiate write will raise an error when given a bad name
        """
        command = ["echo", "bonjour"]
        temp_file = NamedTemporaryFile()
        output_file_path = temp_file.name

        with ProcessRunner(command) as proc:
            self.assertRaises(KeyError,
                              proc.write,
                              file_path=output_file_path,
                              procPipeName='stdin'
                              )

    @parameterized.expand([
        [None],
        ['stdout']
    ])
    def test_processrunner_write_to_files(self, procPipeName):
        """Valdiate the capability to specify files for output to be easily
        redirected to
        """
        test_len = 12
        temp_file = NamedTemporaryFile()
        output_file_path = temp_file.name

        command = [self.sampleCommandPath,
                   "--lines", "{}".format(test_len),
                   "--block", "1",
                   "--sleep", "0"]

        with ProcessRunner(command, autostart=False) as proc:
            proc.write(file_path=output_file_path, procPipeName=procPipeName)
            text_in_list = proc.collectLines()
            text_in = "\n".join(text_in_list)

        with open(output_file_path, 'r') as out_handle:
            text_out = out_handle.read().rstrip('\n')

        print("In:")
        print(text_in)
        print("Out:")
        print(text_out)

        self.assertEqual(text_in,
                         text_out,
                         "Returned unicode text is not equivalent: In {}, Out {}".format(text_in, text_out))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(ProcessRunnerCoreTestCase)
    unittest.TextTestRunner(verbosity=3).run(suite)
