# -*- coding: utf-8 -*-
"""Get the package version"""
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version


def get_version():
    """Get the package version"""
    try:
        _version = version(__name__)
    except PackageNotFoundError:
        # package is not installed
        _version = "0.0.0"

    return _version
