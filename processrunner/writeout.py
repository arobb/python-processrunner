# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from kitchen.text.converters import to_bytes
from .kitchenpatch import getwriter

from .exceptionhandler import ExceptionHandler


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
        pipeWriter = getwriter("utf-8")(pipe)
        output = "{}{}".format(outputPrefix, line)

        try:
            pipeWriter.write(output)

        except TypeError:
            # Shenanigans with unicode
            try:
                pipeWriter.write(to_bytes(output))
            except TypeError:
                pipe.write(str(output))
            except Exception as e:
                raise ExceptionHandler(e,
                                       "Crazy pipe writer stuff: {}".format(e))

        except ValueError as e:
            raise ExceptionHandler(e,
                                   "writeOut caught odd error: {}".format(e))

        finally:
            pipeWriter.flush()
            pipe.flush()

    return func
