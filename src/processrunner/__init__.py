# -*- coding: utf-8 -*-
"""ProcessRunner baseline."""


def simple_loader(module_name, name=None):
    """ Import a named object from a module in the context of this function.
    Source:
    https://www.oreilly.com/library/view/python-cookbook/0596001673/5s04.html

    module_name: Dot-notation module name; use alone if importing a package or
    non-qualified module
    name: Object or submodule to import from module_name
    """
    try:
        module = __import__(module_name, globals(), locals(), [name])
    except ImportError:
        return None

    try:
        return vars(module)[name]
    except KeyError:
        return None


def safe_list_get(in_list, idx):
    """https://stackoverflow.com/a/5125636"""
    try:
        return in_list[idx]
    except IndexError:
        return None


# [moduleName, name, as_name]
import_list = [

    # Core modules
    ["processrunner", "ProcessRunner"],
    ["processrunner", "PROCESSRUNNER_PROCESSES"],
    ["processrunner", "getActiveProcesses"],
    ["ssh", "ssh"],
    ["writeout", "writeOut"],
    ["runcommand", "runCommand"],
    ["which", "which"],

    # Exceptions
    ["exceptionhandler", "SIGINTException"],
    ["exceptionhandler", "CommandNotFound"],

    # Middle column deprecated as of 2.3, removed in 3.0
    ["writeout", "writeOut", "WriteOut"],
    ["writeout", "runCommand", "RunCommand"]
]

for entry in import_list:
    # Determine the effective name of the import
    if safe_list_get(entry, 2) is not None:
        as_name = safe_list_get(entry, 2)
    elif safe_list_get(entry, 1) is None:
        as_name = safe_list_get(entry, 0)
    else:
        as_name = safe_list_get(entry, 1)

    # Try to import with the provided value (Python 2.7)
    if safe_list_get(entry, 1) is None:
        imported_module = simple_loader(entry[0])
    else:
        imported_module = simple_loader(entry[0], entry[1])

    # Try with an extended path (Python 3)
    if imported_module is None:
        # pylint: disable=invalid-name
        if safe_list_get(entry, 1) is None:
            module_str = "processrunner"
            imported_module = simple_loader(module_str, entry[0])
        else:
            module_str = ".".join(["processrunner", entry[0]])
            imported_module = simple_loader(module_str, entry[1])

    locals()[as_name] = imported_module
