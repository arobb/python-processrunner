try:
    from processrunner.processrunner import ProcessRunner
except ImportError:
    from processrunner import ProcessRunner

try:
    from processrunner.processrunner import PROCESSRUNNER_PROCESSES
except ImportError:
    from processrunner import PROCESSRUNNER_PROCESSES

try:
    from processrunner.processrunner import getActiveProcesses
except ImportError:
    from processrunner import getActiveProcesses

try:
    from processrunner.ssh import ssh
except ImportError:
    from ssh import ssh


# Deprecated as of 2.3, removed in 3.0
try:
    from processrunner.writeout import writeOut as WriteOut
except ImportError:
    from writeout import writeOut as WriteOut

try:
    from processrunner.runcommand import runCommand as RunCommand
except ImportError:
    from runcommand import runCommand as RunCommand


# 3.0 Compatible versions
try:
    from processrunner.writeout import writeOut
except ImportError:
    from writeout import writeOut

try:
    from processrunner.runcommand import runCommand
except ImportError:
    from runcommand import runCommand
