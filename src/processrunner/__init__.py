def simpleLoader(moduleName, name=None):
    """ Import a named object from a module in the context of this function.
    Source:
    https://www.oreilly.com/library/view/python-cookbook/0596001673/5s04.html

    moduleName: Dot-notation module name; use alone if importing a package or
    non-qualified module
    name: Object or submodule to import from moduleName
    """
    try:
        module = __import__(moduleName, globals(), locals(), [name])
    except ImportError:
        return None

    try:
        return vars(module)[name]
    except KeyError:
        return None


def safe_list_get(inList, idx):
    """https://stackoverflow.com/a/5125636"""
    try:
        return inList[idx]
    except IndexError:
        return None


# [moduleName, name, asName]
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

    # Deprecated as of 2.3, removed in 3.0
    ["writeout", "writeOut", "WriteOut"],
    ["writeout", "runCommand", "RunCommand"]
]

for entry in import_list:
    # Determine the effective name of the import
    if safe_list_get(entry, 2) is not None:
        asName = safe_list_get(entry, 2)
    elif safe_list_get(entry, 1) is None:
        asName = safe_list_get(entry, 0)
    else:
        asName = safe_list_get(entry, 1)

    # Try to import with the provided value (Python 2.7)
    if safe_list_get(entry, 1) is None:
        importedModule = simpleLoader(entry[0])
    else:
        importedModule = simpleLoader(entry[0], entry[1])

    # Try with an extended path (Python 3)
    if importedModule is None:
        if safe_list_get(entry, 1) is None:
            moduleName = "processrunner"
            importedModule = simpleLoader(moduleName, entry[0])
        else:
            moduleName = ".".join(["processrunner", entry[0]])
            importedModule = simpleLoader(moduleName, entry[1])

    locals()[asName] = importedModule
