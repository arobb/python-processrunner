try:
    from processrunner.processrunner import ProcessRunner
except ImportError:
    from processrunner import ProcessRunner

try:
    from processrunner.processrunner import getActiveProcesses
except ImportError:
    from processrunner import getActiveProcesses

try:
    from processrunner.processrunner import PROCESSRUNNER_PROCESSES
except ImportError:
    from processrunner import PROCESSRUNNER_PROCESSES

try:
    from processrunner.writeout import writeout
except ImportError:
    from writeout import writeout

try:
    from processrunner.runcommand import runcommand
except ImportError:
    from runcommand import runcommand

try:
    from processrunner.ssh import ssh
except ImportError:
    from ssh import ssh