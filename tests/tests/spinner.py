# -*- coding: utf-8 -*-
import sys

class Spinner(object):
    def __init__(self):
        self.active = self.spinning_cursor()

    def spinning_cursor(self):
        while True:
            for cursor in '|/-\\':
                yield cursor

    def spin(self):
        sys.stdout.write(next(self.active))
        sys.stdout.write('\b')
        sys.stdout.flush()
