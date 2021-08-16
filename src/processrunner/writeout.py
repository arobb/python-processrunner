# -*- coding: utf-8 -*-
"""Wrapper to make async writing to a pipe more reliable across processes"""
from __future__ import unicode_literals

from kitchen.text.converters import to_bytes

from .exceptionhandler import ExceptionHandler
from .kitchenpatch import getwriter


def writeOut(pipe, outputPrefix):
    """Use with ProcessRunner.mapLines to easily write to your favorite pipe
    or handle

    Args:
        pipe (pipe): A system pipe/file handle to write output to
        outputPrefix (string): A string to prepend to each line

    Returns:
        function
    """
    # TODO Validate the pipe somehow

    def func(line):
        pipe_writer = getwriter("utf-8")(pipe)
        output = "{}{}".format(outputPrefix, line)

        try:
            pipe_writer.write(output)

        except TypeError:
            # Shenanigans with unicode
            try:
                pipe_writer.write(to_bytes(output))
            except TypeError:
                pipe.write(str(output))
            except Exception as exc:
                raise ExceptionHandler(exc, "Crazy pipe writer stuff: {}"
                                       .format(exc))

        except ValueError as exc:
            raise ExceptionHandler(exc,
                                   "writeOut caught odd error: {}".format(exc))

        finally:
            pipe_writer.flush()
            pipe.flush()

    return func
