#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import argparse
import sys
import time
from datetime import datetime

from processrunner import writeOut


class TestScript(object):
    """Provides output to test ProcessRunner"""
    def __init__(self):

        #
        # Parse arguments
        #
        parser = argparse.ArgumentParser(usage='%(prog)s [options]',
                                         description='')
        parser.add_argument('--lines',
                            required=False,
                            nargs='?',
                            dest='lines',
                            default='10',
                            help='Total number of lines to output. '
                                 'Defaults to 10')
        parser.add_argument('--block',
                            required=False,
                            nargs='?',
                            dest='block',
                            default='1',
                            help='Number of lines to output '
                                 'between sleep. Defaults to 1')
        parser.add_argument('--return-code',
                            required=False,
                            nargs='?',
                            dest='return-code',
                            default='0',
                            help='Code to return at completion')
        parser.add_argument('--sleep',
                            required=False,
                            nargs='?',
                            dest='sleep',
                            default='0',
                            help='Time to sleep in seconds (float), '
                                 'after the first "block"')
        parser.add_argument('--port',
                            required=False,
                            nargs='?',
                            dest='port',
                            default=None,
                            help='Stub for PyCharm debug compatibility')
        parser.add_argument('--client',
                            required=False,
                            nargs='?',
                            dest='client',
                            default=None,
                            help='Stub for PyCharm debug compatibility')
        parser.add_argument('--file',
                            required=False,
                            nargs='?',
                            dest='file',
                            default=None,
                            help='Stub for PyCharm debug compatibility')
        parser.add_argument('--multiproc',
                            required=False,
                            dest='port',
                            action='store_const',
                            const=None,
                            default=None,
                            help='Stub for PyCharm debug compatibility')
        self.config = parser.parse_args().__dict__

        class DateNote:
            def __init__(self):
                pass

            def __repr__(self):
                return datetime.now().isoformat() + " "

            def __add__(self, other):
                return self.__repr__() + other

        self.stdout = writeOut(pipe=sys.stdout, outputPrefix=DateNote())
        self.stderr = writeOut(pipe=sys.stderr, outputPrefix=DateNote())

        self.write(self.config['lines'])
        exit(int(self.config['return-code']))

    def write(self, count):
        count = int(count)

        for i in range(0, count):
            self.stdout("Line: {} of {}\n".format(i+1, count))

            if (i+1) % int(self.config['block']) == 0:
                time.sleep(float(self.config['sleep']))


if __name__ == "__main__":
    obj = TestScript()
