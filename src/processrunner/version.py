# -*- coding: utf-8 -*-
from os import path


def get_version():
    here = path.abspath(path.dirname(__file__))

    # Version information
    try:
        with open(path.join(here, 'VERSION')) as vf:
            version = vf.readline()

    except IOError:
        version = "0.0.0"

    return version
