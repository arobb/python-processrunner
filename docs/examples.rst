Examples
========

Simple iteration over output
----------------------------
Iterate over the output lines of a ":term:`one-and-done`" :term:`command`.

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    if __name__ == "__main__":
        command = ['seq', '-f', 'Line %g', '10']
        for line in Pr(command).output:
            print(line)

Using :func:`with` syntax (context manager)
-------------------------------------------
Simplify some uses of ProcessRunner by using :func:`with`:

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    if __name__ == "__main__":
        command = ['seq', '-f', 'Line %g', '10']
        output_lines = []

        with Pr(command) as proc:
            lines = proc.readlines()

        for line in lines:
            print(line)

Writing output to a file
------------------------
To quickly direct output to a file, the :meth:`write` method has you covered.

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    # Python shell
    Pr(['seq', '-f', 'Line %g', '10']).write('output.txt')

    # Python file
    if __name__ == "__main__":
        Pr(['seq', '-f', 'Line %g', '10']).write('output.txt').wait()

.. note:: Non-blocking!

    Note the use of :meth:`wait` after :meth:`write` above. The
    :meth:`write` method is :term:`non-blocking`, meaning that it will return
    immediately. In this case, that return happens before the output from
    the :command:`seq` command makes it into ``output.txt``, and as a result
    the program would exit before writing any of :command:`seq`'s output.

Start the command after instantiating :class:`ProcessRunner`
------------------------------------------------------------
When you want to control the start time of the :term:`command`, use
``autostart=False`` along with :meth:`start`.

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    if __name__ == "__main__":
        command = ['seq', '-f', 'Line %g', '10']
        output_lines = []

        with Pr(command, autostart=False) as proc:
            # Do something else here
            print("Doing other things before the command starts")

            # Ready to start now
            proc.start()
            lines = proc.readlines()

        for line in lines:
            print(line)

Process output in real time, in the foreground
----------------------------------------------
Read output as it occurs from the :term:`command`.

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    if __name__ == "__main__":
        command = ['seq', '-f', 'Line %g', '10']
        proc = Pr(command)

        # Can also use proc.stdout or proc.stderr for those specific pipes
        for line in proc.output:
            print("My line: {}".format(line))

.. _Non-blocking example 1:

Process output in real time, in the background
----------------------------------------------
Process output as it occurs from the :term:`command` *in the background*,
while the main application continues to do other things.

.. code-block:: python

    from processrunner import ProcessRunner as Pr
    from time import sleep

    if __name__ == "__main__":
        command = ['seq', '-f', 'Line %g', '10']
        proc = Pr(command, autostart=False)

        # A function to run against each line
        def f1(line):
            print("My line: {}".format(line))

        # Map each line against the function f1
        # Returns a multiprocessing.Event to signal when the map is complete
        f1_stop_event = proc.map(func=f1, procPipeName="stdout")

        # Start the command
        proc.start()

        while not f1_stop_event.is_set():
            print("waiting, doing other stuff")
            sleep(0.01)

The output will look something like this. (The exact output depends on
random timing factors)

.. code-block::

    waiting
    My line: Line 1

    My line: Line 2

    My line: Line 3

    My line: Line 4

    My line: Line 5

    waiting
    My line: Line 6

    My line: Line 7

    My line: Line 8

    My line: Line 9

    My line: Line 10

    waiting
    waiting
    waiting
    waiting
    waiting
    waiting
    waiting
    waiting
    waiting
    waiting

.. note:: New lines

    Notice the extra lines after each of the lines returned from the
    :term:`command`. Unlike :attr:`output` (and :attr:`stdout`/:attr:`stderr`)
    :meth:`map` does not strip whitespace. (They're seen as "extra" lines
    here because :func:`print` also prints a newline after each invocation.
    Using a direct pipe writer like :meth:`sys.stdout.write` the user needs
    to supply newlines where necessary.)

Process output in real time and write to a file
-----------------------------------------------
Read output as it occurs from the :term:`command` and write the output to a
file.

.. note:: Stripping newlines

    This example applies :meth:`strip` to each line to remove the trailing
    newline.

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    if __name__ == "__main__":
        command = ['seq', '-f', 'Line %g', '10']
        proc = Pr(command, autostart=False)

        def f1(line):
            print("My line: {}".format(line.strip()))

        # Map each line against the function f1
        proc.map(func=f1, procPipeName="stdout")

        # Also write the output to a file (truncating it first)
        proc.write("output.txt")

        # Start the command and wait for it (and the map/write) to finish
        proc.start().wait()

        with open("output.txt", "r") as f:
            for line in f:
                print("Line from file: {}".format(line.strip()))

The output will look like this:

.. code-block::

    My line: Line 1
    My line: Line 2
    My line: Line 3
    My line: Line 4
    My line: Line 5
    My line: Line 6
    My line: Line 7
    My line: Line 8
    My line: Line 9
    My line: Line 10
    Line from file: Line 1
    Line from file: Line 2
    Line from file: Line 3
    Line from file: Line 4
    Line from file: Line 5
    Line from file: Line 6
    Line from file: Line 7
    Line from file: Line 8
    Line from file: Line 9
    Line from file: Line 10

Adding real-time values to :meth:`map` output
---------------------------------------------
Especially for timing, it's nice to have annotation generated at runtime for
:meth:`map` functions.

.. code-block:: python

    import sys
    from datetime import datetime
    from processrunner import ProcessRunner as Pr

    if __name__ == "__main__":
        command = ['seq', '-f', 'Line %g', '10']
        proc = Pr(command, autostart=False)

        # A function to run against each line
        def f1(line):
            sys.stdout.write("{} {}".format(datetime.now().isoformat(), line))

        # Map each line against the function f1
        proc.map(func=f1, procPipeName="stdout")

        # Start the command
        proc.start().wait()

This produces:

.. code-block::

    2021-09-12T14:31:29.926617 Line 1
    2021-09-12T14:31:29.927616 Line 2
    2021-09-12T14:31:29.928213 Line 3
    2021-09-12T14:31:29.929022 Line 4
    2021-09-12T14:31:29.929822 Line 5
    2021-09-12T14:31:29.930501 Line 6
    2021-09-12T14:31:29.931075 Line 7
    2021-09-12T14:31:29.931562 Line 8
    2021-09-12T14:31:29.931988 Line 9
    2021-09-12T14:31:29.932412 Line 10

For more complex examples where you're not totally sure about encoding and
need to make sure the pipe is being flushed, a helper function exists called
:func:`WriteOut`. This example is a bit contrived, but produces the same
results:

.. code-block:: python

    import sys
    from datetime import datetime
    from processrunner import ProcessRunner as Pr
    from processrunner import WriteOut

    if __name__ == "__main__":
        command = ['seq', '-f', 'Line %g', '10']
        proc = Pr(command, autostart=False)

        # A function to run against each line
        # Date/time notation for output lines in files
        class DateNote:
            def init(self):
                pass
            def __repr__(self):
                return datetime.now().isoformat() + " "

        # pipe is the terminal pipe where the combined value to go
        # outputPrefix is a class instance/string to include before a
        #     command line
        f1 = WriteOut(pipe=sys.stdout, outputPrefix=DateNote())

        # Map each line against the function f1
        proc.map(func=f1, procPipeName="stdout")

        # Start the command and wait for everything to finish
        proc.start().wait()


Using WriteOut to concurrently map output to the console and files
------------------------------------------------------------------
.. note::

    This example uses a script from the ProcessRunner source tree to generate
    output on both stdout and stderr.

While an external command runs, write the external process' ``stdout`` and
``stderr`` to the corresponding local pipes, as well as corresponding files.
Further, prefix the local pipe output with dedicated notes, and prefix the
file output with timestamps.

.. code-block:: python

    # Imports
    import os
    import sys
    from datetime import datetime
    from processrunner import ProcessRunner, WriteOut

    if __name__ == "__main__":
        # Logging files
        working_dir = os.path.dirname(os.path.realpath(__file__))
        stdoutFile = open(working_dir+'/stdout.txt', 'a')
        stderrFile = open(working_dir+'/stderr.txt', 'a')

        # Date/time notation for output lines in files
        class DateNote:
            def init(self):
                pass
            def __repr__(self):
                return datetime.now().isoformat() + " "

        # Prep the process
        command = ["tests/test-output-script.py",
                   "--lines", "5",
                   "--out-pipe", "both"]
        proc = ProcessRunner(command, autostart=False)

        # Attach output mechanisms to the process's output pipes. These are
        # handled asynchronously, so you can see the output while it is happening
        # Write to the console's stdout and stderr, with custom prefixes for each
        proc.mapLines(WriteOut(pipe=sys.stdout,
                               outputPrefix="validation-stdout> "),
                      procPipeName="stdout")
        proc.mapLines(WriteOut(pipe=sys.stderr,
                               outputPrefix="validation-stderr> "),
                      procPipeName="stderr")

        # Write to the log files, prepending each line with a date/time stamp
        proc.mapLines(WriteOut(pipe=stdoutFile, outputPrefix=DateNote()),
                      procPipeName="stdout")
        proc.mapLines(WriteOut(pipe=stderrFile, outputPrefix=DateNote()),
                      procPipeName="stderr")

        # Start the process, then block regular execution until the
        # process finishes
        proc.start().wait()

        stdoutFile.close()
        stderrFile.close()


Viewing log output
------------------
.. code-block:: python

    # Quick way to get output
    import logging
    from processrunner import ProcessRunner as Pr

    logging.basicConfig(level=logging.INFO)

    if __name__ == "__main__":
        print("\n".join(
            Pr(['seq', '-f', 'Line %g', '10']).output
        ))
