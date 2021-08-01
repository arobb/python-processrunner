# -*- coding: utf-8 -*-
"""
An implementation of the Enum data type
"""
from __future__ import unicode_literals


# For use with deployment statuses
# https://stackoverflow.com/a/1695250
def enum(*sequential, **named):
    """An implementation of the Enum data type

    Usage
    myEnum= enum(
                  'Apple'
                , 'Banana')
    """
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in list(enums.items()))
    enums['reverse_mapping'] = reverse
    return type(str('Enum'), (), enums)
