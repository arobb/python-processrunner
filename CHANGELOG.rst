Change Log
==========
Documented changes to the project.

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
