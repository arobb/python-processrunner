# Python ProcessRunner
Designed to make reading from external processes easier. Does not permit interactive communication with the process, but rather provides simplified consumption of process output (especially for logging.)

## Provided classes
ProcessRunner

## Provided convenience functions
runCommand
ssh
WriteOut
getActiveProcesses

## Exceptions
CommandNotFound


ssh function returns the SSH exit code. Takes the following parameters
- REQUIRED string remoteAddress IP or hostname for target system
- REQUIRED string remotecommand The command to run on the target system
- OPTIONAL string outputPrefix String to prepend to all output lines. Defaults to 'ssh> '


WriteOut function returns a function that accepts a line and writes that line
to the provided pipe, prepended with a user provided string. Useful when handling
output from processes directly. See example use in the ssh function.
Takes the following parameters
- REQUIRED pipe pipe A system pipe to write the output to
- REQUIRED string outputPrefix A string to prepend to each line
-- This can also be any object that can be cast to a string


getActiveProcesses function returns a list of ProcessRunner instances that are
currently alive. Takes no parameters.


ProcessRunner class uses subprocess.Popen. It does not use the shell=True flag.
All processes started by the class are saved in PROCESSRUNNER_PROCESSES. A list
of currently active processes started by the class can be retreived by calling
getActiveProcesses(), which IS NOT a class member.
Takes these parameters:
- REQUIRED [string,] command The command to execute along with all parameters
- OPTIONAL string cwd Directory to switch into before execution. CWD does not
                      apply to the _location_ of the process, which must be on
                      PATH


Simple example:
# Run a command, wait for it to complete, and gather its return code
command = ["scp", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "/path/to/local/file", clientAddress+":/tmp/"]
result = ProcessRunner(command).wait().poll()


Complex example:
# Logging files
stdoutFile = open(workingDir+'/stdout.txt', 'a')
stderrFile = open(workingDir+'/stderr.txt', 'a')

# Date/time notation for output lines in files
class DateNote:
    def init(self):
        pass
    def __repr__(self):
        return datetime.now().isoformat() + " "

# Start the process
proc = ProcessRunner(command)

# Attach output mechanisms to the process's output pipes. These are handled asynchronously, so you can see the output while it is happening
# Write to the console's stdout and stderr, with custom prefixes for each
proc.mapLines(WriteOut(pipe=sys.stdout, outputPrefix="validation-stdout> "), procPipeName="stdout")
proc.mapLines(WriteOut(pipe=sys.stderr, outputPrefix="validation-stderr> "), procPipeName="stderr")

# Write to the log files, prepending each line with a date/time stamp
proc.mapLines(WriteOut(pipe=stdoutFile, outputPrefix=DateNote()), procPipeName="stdout")
proc.mapLines(WriteOut(pipe=stderrFile, outputPrefix=DateNote()), procPipeName="stderr")

# Block regular execution until the process finishes
result = proc.wait().poll()

# Wait until the queues are emptied to close the files
while not proc.areAllQueuesEmpty():
    time.sleep(0.01)

stdoutFile.close()
stderrFile.close()
