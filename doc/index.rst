Welcome to ProcessRunner's documentation!
=========================================
This documentation includes an introduction to the purpose of ProcessRunner,
example uses, and API docs.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Introduction and Background
---------------------------
ProcessRunner is built to run external programs and collect their output and
is built on the :class:`subprocess.Popen` library. It simplifies the
collection of output when multiple concurrent copies of that output are
needed.

ProcessRunner was originally built to split the output of a potentially
long-running command line application where it was necessary to write the
app’s output to a file while also processing the records in real time.

Today ProcessRunner continues to simplify the handling of multiple actions
on an external application’s output streams, with several

.. admonition:: When not to use ProcessRunner

    Don't use ProcessRunner when the native tools work.
    :mod:`subprocess` is a powerful toolset and should satisfy most use
    cases. Using the native tools also eliminates the fairly significant
    overhead ProcessRunner introduces.

ProcessRunner uses subprocess.Popen. It does not use the ``shell=True`` flag
. All processes started by the class are saved in
:data:`PROCESSRUNNER_PROCESSES`. A list of currently active processes
started by the class can be retrieved by calling :func:`getActiveProcesses`,
which IS NOT a class member.

Quickstart
----------
For this series of examples, we'll use a small shell command to produce
some output for us:

.. code-block:: bash

    seq -f 'Line %g' 10

In Python, this can be run without ProcessRunner like so:

.. code-block:: python

    from subprocess import call

    # Python shell
    call(['seq', '-f', 'Line %g', '10'])

    # Python file
    if __name__ == "__main__":
        print("\n".join(
            call(['seq', '-f', 'Line %g', '10']) )
        )

Which will output the following 11 lines. The first 10 are from ``seq``,
and the last is the exit code.

..  code-block:: text

    Line 1
    Line 2
    Line 3
    Line 4
    Line 5
    Line 6
    Line 7
    Line 8
    Line 9
    Line 10
    0

Similar behavior can be seen with ProcessRunner:

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    # Python shell
    Pr(['seq', '-f', 'Line %g', '10']).output

    # Python file
    if __name__ == "__main__":
        print("\n".join(
            Pr(['seq', '-f', 'Line %g', '10']).output
        ))

This will output the same lines, but without the exit code:

.. code-block:: text

    Line 1
    Line 2
    Line 3
    Line 4
    Line 5
    Line 6
    Line 7
    Line 8
    Line 9
    Line 10

.. admonition:: Note on output

    ProcessRunner has several ways to collect output, the simplest being the
    attributes :attr:`stdout`, :attr:`stderr`, and :attr:`output`. This
    third attribute,  :attr:`output`, is a combination of the other two,
    interwoven as ProcessRunner gets lines from the command's ``stdout`` and
    ``stderr``.

Writing output to a file
^^^^^^^^^^^^^^^^^^^^^^^^
To quickly direct output to a file, the :meth:`write` method has you covered:

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    # Python shell
    Pr(['seq', '-f', 'Line %g', '10']).write('output.txt')

    # Python file
    if __name__ == "__main__":
        Pr(['seq', '-f', 'Line %g', '10']).write('output.txt').wait()

.. admonition:: Non-blocking!

    Note the use of :meth:`wait` after :meth:`write` above. The
    :meth:`write` method is non-blocking, meaning that it will return
    immediately. In this case, that happens before the output from the ``seq``
    command makes it into ``output.txt``.

Examples
--------

.. toctree::
   :maxdepth: 2

   examples

API Reference
-------------
Detailed method-level information.

.. toctree::
   :maxdepth: 2

   api

Issues
------
BrokenPipeErrors and Error 32s/IO Errors
These happen when a ProcessRunner instance starts to shut down before it's
really finished. Internally this often occurs when the :meth:`shutdown`
routine begins to terminate the child processes managing various aspects of
the library (like the central _Command object referred to as the :data:`run`
attribute) but mapLines processing children aren't done and try to get
status from the run/_Command object.

This can be mitigated by ensuring the "complete" Event returned from a call
to mapLines is headed before tearing down the ProcessRunner instance.
:meth:`wait` was redesigned after version 2.5.3 to globally watch these
instances before returning.

Indices and tables
==================
* :ref:`genindex`