# -*- coding: utf-8 -*-
from builtins import str as text


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
        try:
            pipe.write(text(outputPrefix)+text(line))
            pipe.flush()

        except ValueError as e:
            print("writeOut caught odd error: " + text(e))

    return func
