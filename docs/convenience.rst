Convenience Functions
=====================
This page covers details of additional functions available in the
ProcessRunner package.

RunCommand
----------
The RunCommand function returns the process exit code, and stdout and stderr
are connected to local stdout and stderr.

Accessed via `processrunner.RunCommand`.

.. currentmodule:: processrunner.runcommand
.. autofunction:: runCommand

ssh
---
The ssh function runs a command on a remote host, and returns the SSH exit
code. stdout and stderr are connected to local stdout and stderr.

Accessed via `processrunner.ssh`.

.. currentmodule:: processrunner.ssh
.. autofunction:: ssh

WriteOut
--------
The WriteOut function is used to prepend lines from the external process
with a given string. Given a pipe and a string, it returns a function that
accepts a line of text, then writes that line to the provided pipe,
prepended with a user provided string. Useful when handling output from
processes directly. See example use on the :doc:`examples` page.

Accessed via `processrunner.WriteOut`.

.. currentmodule:: processrunner.writeout
.. autofunction:: writeOut


getActiveProcesses
------------------
Accessed via `processrunner.getActiveProcesses`

.. currentmodule:: processrunner
.. autofunction:: getActiveProcesses