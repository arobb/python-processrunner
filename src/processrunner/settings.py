# -*- coding: utf-8 -*-
"""Holder for shared Configuration"""


def init():
    """Holder for shared Configuration"""
    global config

    try:
        config
    except NameError:
        config = {}
