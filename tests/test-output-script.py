#!/usr/bin/env python2
# -*- coding: utf-8 -*-
'''
'''

import argparse
import os
import sys
import time
from datetime import datetime

from processrunner import ProcessRunner, WriteOut


class TestScript(object):
    def __init__(self):

        #
        # Parse arguments
        #
        parser = argparse.ArgumentParser(usage='%(prog)s [options]', description='')
        parser.add_argument('--lines', required=False, nargs='?', dest='lines', default='10', help='Number of lines to output. Defaults to 10')
        parser.add_argument('--block', required=False, nargs='?', dest='block', default='1', help='Number of lines to output between sleep. Defaults to 1')
        parser.add_argument('--sleep', required=False, nargs='?', dest='sleep', default='0', help='Sleep')
        self.config = parser.parse_args().__dict__


        class DateNote:
            def init(self):
                pass
            def __repr__(self):
                return datetime.now().isoformat() + " "

        self.stdout = WriteOut(pipe=sys.stdout, outputPrefix=DateNote())
        self.stderr = WriteOut(pipe=sys.stderr, outputPrefix=DateNote())

        self.write(self.config['lines'])
        exit(0)

    def write(self, count):
        count = int(count)

        for i in range(0, count):
            self.stdout("Line: "+str(i+1)+" of "+str(count)+"\n")

            if (i+1) % int(self.config['block']) == 0:
                time.sleep(float(self.config['sleep']))

if __name__ == "__main__":
    obj = TestScript()
