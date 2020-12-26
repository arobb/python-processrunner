#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
'''

import argparse
import os
import sys
import time
from datetime import datetime

import tests.context
from processrunner import ProcessRunner
from processrunner import writeout


class TestScript(object):
    def __init__(self):

        #
        # Parse arguments
        #
        parser = argparse.ArgumentParser(usage='%(prog)s [options]', description='')
        parser.add_argument('--lines', required=False, nargs='?', dest='lines', default='10', help='Number of lines to output. Defaults to 10')
        parser.add_argument('--block', required=False, nargs='?', dest='block', default='1', help='Number of lines to output between sleep. Defaults to 1')
        parser.add_argument('--return-code', required=False, nargs='?', dest='return-code', default='0', help='Code to return at completion')
        parser.add_argument('--sleep', required=False, nargs='?', dest='sleep', default='0', help='Sleep')
        parser.add_argument('--port', required=False, nargs='?', dest='port', default=None, help='Stub for PyCharm debug compatibility')
        parser.add_argument('--client', required=False, nargs='?', dest='client', default=None, help='Stub for PyCharm debug compatibility')
        parser.add_argument('--file', required=False, nargs='?', dest='file', default=None, help='Stub for PyCharm debug compatibility')
        parser.add_argument('--multiproc', required=False, dest='port', action='store_const', const=None, default=None,
                            help='Stub for PyCharm debug compatibility')
        self.config = parser.parse_args().__dict__


        class DateNote:
            def init(self):
                pass
            def __repr__(self):
                return datetime.now().isoformat() + " "

        self.stdout = writeout(pipe=sys.stdout, outputPrefix=DateNote())
        self.stderr = writeout(pipe=sys.stderr, outputPrefix=DateNote())

        self.write(self.config['lines'])
        exit(int(self.config['return-code']))

    def write(self, count):
        count = int(count)

        for i in range(0, count):
            self.stdout("Line: "+str(i+1)+" of "+str(count)+"\n")

            if (i+1) % int(self.config['block']) == 0:
                time.sleep(float(self.config['sleep']))

if __name__ == "__main__":
    obj = TestScript()
