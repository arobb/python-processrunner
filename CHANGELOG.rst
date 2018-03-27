Change Log
==========
Documented changes to the project.

Version 2.1.0
-------------
Addition of shutdown() and killCommand() methods, and changes to methods
terminate() and wait(). shutdown() allows the background process manager to
stop, and should be called after child processes are terminated with terminate()
or killCommand(). This helps with process cleanup and prevents buildup of dead
processes over time for long-running applications.

These changes were made to facilitate use with long-running services. (Like a
JVM started for Py4J.)

- NEW shutdown() separates the destruction of the process manager from termination
(terminate()) invocation. Run after verifying terminate/kill has destroyed any
child processes.
- NEW killCommand() method allows sending SIGKILL to the main process.
- CHANGE terminate(timeoutMs) sends SIGTERM with a timeout to the
main process, and also terminates the queue processes.
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
- The processrunner_maplines_test.py sometimes fails on a loaded machine, caused
by a bad return code from the monitored process. Despite extensive investigation,
the root cause has not been identified. This issue appeared to be more pronounced
when running with the threading library in the <2.x versions.
