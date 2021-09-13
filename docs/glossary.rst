Glossary
========
Throughout this documentation these terms have specific meanings.

.. glossary::

    Blocking
        ProcessRunner methods that return only once they have completed an
        activity (as opposed to Non-blocking). Refers to methods like
        :meth:`wait` and :meth:`readlines`, as well as attributes
        :attr:`stdout`, :attr:`stderr`, and :attr:`output`.

        See :ref:`stopping` for more discussion.

    Command
        The external program (able to run in a command line shell) that is
        to be run in the first argument of :class:`ProcessRunner`.

    One-and-done
        Commands that are expected to be run quickly and usually synchronously
        with the user's application, where the user's application waits for the
        command to complete before doing much other work.

    Line
    Lines
        A newline-terminated string that represents the output of a
        :term:`command`.

    Long-running
        Commands that will run asynchronously with the user's application and
        are not expected to exit quickly.

    Non-blocking
        ProcessRunner methods that return immediately.

    Reader
    Readers
        Generic term for a process that is consuming output from the
        :term:`command` via a :class:`ProcessRunner` instance. Outside
        :class:`ProcessRunner` all readers will be consuming via a mechanism
        that leverages :meth:`map`: :meth:`map` directly, :attr:`stdout`,
        :attr:`stderr`, :attr:`output`, or :meth:`readlines`.