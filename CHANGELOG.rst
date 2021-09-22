Change Log
==========
Documented changes to the project.

Version 3.0.0+ (TODOs)
----------------------
- Internal ContentWrapper class manage value changes across ContentWrapper.THRESHOLD
    - If the values grow or shink, ContentWrapper should adapt its management
- Internal ContentWrapper class add created and updated timestamps to enable sorting
- Ability to sort combined outputs (stdout+stderr) by created timestamps
- Create diagram of internal ProcessRunner execution model
- Create a performance baseline compared to shell pipe actions
- DAG feature extension
    - Better track when stdout/stderr are closed to then close stdin on the
      receiving instance

Version 2.x
-----------
contentwrapper.ContentWrapper.TYPES is moved to contentwrapper.TYPES and is now a proper enum.

Version 2.6.0
-------------
Major changes:

- Documentation on ReadTheDocs!
- Renamed a large number of internal methods to conform to PEP standards
- Reconfigured to use ``tox``
- Re-enabled use of setuptools-scm to support Git tag-based versioning
- Added validations using pylint, pytest coverage, and bandit
- Moved code under ``src`` directory
- :meth:`wait` behavior change: Now waits for all consumers to finish reading
    - May increase run time or potentially cause apps to hang that have
      unfinished readers
- :meth:`start` now returns ``self`` rather than ``True``
- NEW :meth:`map` method mirrors :meth:`mapLines` and will eventually
  replace it.
- NEW :meth:`readlines` method mirrors :meth:`collectLines` and will
  eventually replace it
- Multiple methods now support timeouts
    - ProcessRunner.wait
- :meth:`collectLines` will now raise a new exception
  :exc:`PotentialDataLoss` if it is called after :meth:`start` while other
  readers are attached

Minor changes:

- :meth:`mapLines` now logs when a :exc:`BrokenPipeError` occurs

Version 2.5.2
-------------
Adds additional ways to interact with output, as well as Python 3.8+ on macOS.

Minor features:

- Mimic the IO read_line generator
- Add ProcessRunner.stdout/stderr/output attributes as iterators

Fixes:

- Compatibility with Python 3.8+ on macOS following change to default multiprocessing start method related to Python issue 33725

Version 2.5.1
-------------
Update to readme that didn't make it into 2.5.0.

Version 2.5.0
-------------
This is a substantial refactor of many parts of the codebase. There should be
only minor API changes.

New major features:

- Simple DAG creation across ProcessRunner instances
- New write() method to easily redirect content into files

New minor features:

- Add discrete "start" functionality to ProcessRunner to manage when the external process begins
- Add timeout (in seconds) argument to wait and collectLines methods
- New Timeout exception

Internal changes:

- collectLines now leverages mapLines internally to build the output list in a shared queue to better interleave content from different pipes
- Closing of stdin is now handled within _Commmand, not _PrPipeWriter
- New QueueLink class to manage movement of records between queues
- Refactored substantial functionality between _PrPipe and sub-classes
- New methods in command.py
    - send_signal
    - is_queue_alive
    - is_queue_drained (based on similar changes to _PrPipe)
- Leverage Events objects to stop child processes

Dependencies now include `funcsigs`.

Version 2.4.0
-------------
Fix a race condition that would sometimes lead to incorrect return codes and
other unacceptable behavior. Add a class to manage large pipe content.
Multitude of internal changes to address issues found by new unit tests.

Still expects pipe contents to be discrete new-line broken text, but can handle
arbitrarily large contents by buffering larger lines to a temp file.
(Relatively low threshold, meant to prevent deadlocks when transferring data
over OS pipes.)

Adds unit tests. Changes to better match PEP syntax recommendations.

Dependencies now include `deprecate` and `kitchen`.

Version 2.3.0
-------------
Fix a memory leak when running multiple instances of ProcessRunner. Refactor
internals into a proper package structure.

Previous entries in this Change Log have been altered to remove new lines in bulleted lists. This should help formatting parsers.

- CHANGE Documentation clarifies the use of ``ProcessRunner.terminate`` and ``.shutdown``
- CHANGE ``ProcessRunner.poll`` raises any exceptions rather than ignoring them
- CHANGE ``ProcessRunner.wait`` removes a try/except block that obscured an error in the join method
- CHANGE ``ProcessRunner.join`` uses a timeout to log and re-try should client readers be waiting to exit
- CHANGE ``ProcessRunner.terminate`` removes a try/except block that was ignoring all exceptions
- CHANGE ``ProcessRunner._terminateQueues`` becomes a "private/protected" method
- CHANGE ``ProcessRunner.terminateCommand`` now raises exceptions other than "OSError number 3" (no such process)
- CHANGE ``ProcessRunner.killCommand`` removes the try/except block, it was just re-raising all exceptions
- CHANGE ``ProcessRunner.shutdown`` runs terminate() before shutting down the managers
- FIX Memory leak caused by a permanent reference established during initialization addressed by removing reference during shutdown

Version 2.2.0
-------------
Compatibility with Python 3 (through 3.7).

Version 2.1.1
-------------
Updated README to include new methods.

Version 2.1.0
-------------
Addition of shutdown() and killCommand() methods, and changes to methods
terminate() and wait(). shutdown() allows the background process manager to
stop, and should be called after child processes are terminated with terminate()
or killCommand(). This helps with process cleanup and prevents buildup of dead
processes over time for long-running applications.

These changes were made to facilitate use with long-running services. (Like a
JVM started for Py4J.)

- NEW shutdown() separates the destruction of the process manager from termination (terminate()) invocation. Run after verifying terminate/kill has destroyed any child processes.
- NEW killCommand() method allows sending SIGKILL to the main process.
- CHANGE terminate(timeoutMs) sends SIGTERM with a timeout to the main process, and also terminates the queue processes.
- CHANGE Update test cases to use new shutdown() method.

Others:
Remove Exception from wait(), and simply return if an error is raised by
self.run. Should make the behavior more predictable.

Version 2.0.1
-------------
Fixes an issue where installation was not installing the core script.

Version 2.0.0
-------------
This version swaps out the threading library for multiprocessing, so discrete
features that formerly ran in threads now run in distinct processes.

Known Issues, 2.0.0
-------------------
- The processrunner_maplines_test.py sometimes fails on a loaded machine, caused by a bad return code from the monitored process. Despite extensive investigation, the root cause has not been identified. This issue appeared to be more pronounced when running with the threading library in the <2.x versions.
