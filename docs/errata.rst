Errata
******
Notes, internals, custom exceptions, and other miscellaneous topics.

Internals
=========

- Uses Popen
    - TODO: Document the configuration used
- Memory considerations
    - Reader attributes
    - readlines

Custom Exceptions
=================
CommandNotFound
    Exception thrown when the command to execute isn't available.

Timeout
    Exception thrown when methods with 'timeout' arguments reach max duration.

ProcessAlreadyStarted
    Raise if start is called after the process is started.

ProcessNotStarted
    Raise if start hasn't been called, but a method has been called that
    depends on the target process running.

HandleAlreadySet
    Raise if a pipe has already been configured with a pipe handle.

HandleNotSet
    Raise if a pipe has not been configured with a pipe handle, but a call
    requires one to have been set.

PotentialDataLoss
    Raise if there's a potential for data loss.
