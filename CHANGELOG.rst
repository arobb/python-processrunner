Change Log
==========
Documented changes to the project.

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
