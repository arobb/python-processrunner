Welcome to ProcessRunner's documentation!
=========================================

.. image:: https://badge.fury.io/py/processrunner.svg
   :target: https://pypi.org/project/processrunner
   :alt: Pypi Version
.. image:: https://readthedocs.org/projects/processrunner/badge/?version=latest
   :target: http://processrunner.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

This documentation includes an introduction to the purpose of ProcessRunner,
example uses, and API docs.

.. toctree::
   :maxdepth: 1
   :caption: Contents

   api
   convenience
   examples
   glossary
   changelog
   errata

Introduction and Background
===========================
ProcessRunner is built to run external programs and collect their
character (string/non-binary) output and is built on the
:class:`subprocess.Popen` library. It simplifies the management of output when
multiple concurrent copies of that output are needed.

ProcessRunner was originally built to split the output of a potentially
long-running command line application where it was necessary to write the
app’s output to a file while also processing the records in real time.

Today ProcessRunner continues to simplify the handling of multiple activities
on an external application’s output streams, with many concurrent activities
being performed on those output streams.

.. note:: When not to use ProcessRunner

    Don't use ProcessRunner when the native tools work.
    :mod:`subprocess` is a powerful toolset and should satisfy most use
    cases. Using the native tools also eliminates the fairly significant
    overhead ProcessRunner introduces.

ProcessRunner uses :class:`subprocess.Popen`. It does not use the
``shell=True`` flag. All processes started by the class are saved in
:data:`PROCESSRUNNER_PROCESSES`. A list of currently active processes
started by the class can be retrieved by calling
:func:`processrunner.getActiveProcesses`, which IS NOT a class member of
:class:`ProcessRunner`.

.. _Stopping:

Determining when to stop
------------------------
There are multiple mechanisms to determine when the :term:`command` has
stopped and :term:`readers` have finished. This may seem like a topic for
later, but skipping this can cause indefinite hangs!

:term:`Blocking` methods hold (block) the user's application from continuing to
execute. :meth:`wait` is the most thorough, as it blocks until both the
:term:`command` and all :term:`readers` are finished. :meth:`readlines`
blocks until the :term:`command` is finished and :meth:`readlines` has
collected all requested lines from the :term:`command`'s pipes. (Both stdout
and stderr, or just the one that's been requested via the ``procPipeName``
parameter.)

The :class:`ProcessRunner` attributes :attr:`stdout`, :attr:`stderr`, and
:attr:`output` are special in that they are :term:`blocking` but also
produce values as they are generated. :meth:`readlines` by contrast only
returns a complete list of all output once the :term:`command` has finished.

When using the :term:`non-blocking` methods :meth:`map` and :meth:`write`,
it is necessary to use another mechanism to ensure all output has been
processed. :class:`ProcessRunner` does not require that all output be
processed by a :term:`reader`, except when using :meth:`wait`. (Further
discussion later in this section.)

A potentially risky situation arises when using :meth:`map` and :meth:`wait`
. If a :meth:`map` consumer never finishes reading all the output queued for
it, :meth:`wait` will effectively hang. :class:`ProcessRunner` includes an
``INFO`` log notification for this situation at the ``NOTIFICATION_DELAY``
interval (default every 1 second, not currently exposed for changing).

:meth:`map` returns a :meth:`multiprocessing.Event` object the user can
leverage to determine when the mapping has completed.
:meth:`~multiprocessing.Event` objects contain an :meth:`is_set` method that
returns a ``bool``. In this context, ``False`` means the map is incomplete,
while ``True`` means it has finished and there are no more :term:`lines` to
be processed. For an example of this, see :ref:`Non-blocking example 1`.

Quickstart
==========
For this series of examples, we'll use a small :term:`one-and-done` shell
command to produce some output for us:

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
    third attribute, :attr:`output`, is a combination of the other two,
    interwoven as ProcessRunner gets lines from the command's ``stdout`` and
    ``stderr``.

Writing output to a file
------------------------
To quickly direct output to a file, the :meth:`write` method has you covered:

.. code-block:: python

    from processrunner import ProcessRunner as Pr

    # Python shell
    Pr(['seq', '-f', 'Line %g', '10']).write('output.txt')

    # Python file
    if __name__ == "__main__":
        Pr(['seq', '-f', 'Line %g', '10']).write('output.txt').wait()

.. note:: Non-blocking!

    Note the use of :meth:`wait` after :meth:`write` above. The
    :meth:`write` method is non-blocking, meaning that it will return
    immediately. In this case, that happens before the output from the ``seq``
    command makes it into ``output.txt``.

See more examples on the :doc:`examples page <examples>`.

Issues
======
BrokenPipeErrors and Error 32s/IO Errors
----------------------------------------
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

:exc:`RuntimeError` with mention of ``freeze_support()``
--------------------------------------------------------
When running ProcessRunner in a program (vs on a console) make sure to start
your primary logic inside a ``if __name__ == '__main__':`` block.

This stems from a compromise made when handling the fallout from changes
discussed in https://bugs.python.org/issue33725. See `Github`_ for details
on the changes.

.. _Github: https://github.com/arobb/python-processrunner/commit/06f4f18c163a2d27ad5f6f651d9aa01041272263

Indices and tables
==================
* :ref:`genindex`