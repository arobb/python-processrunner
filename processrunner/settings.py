# -*- coding: utf-8 -*-
# Holder for shared Configuration

def init():
    global config

    try:
        config
    except NameError:
        config = {}
