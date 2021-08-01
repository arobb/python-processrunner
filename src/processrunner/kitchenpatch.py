# -*- coding: utf-8 -*-
"""Patched version of PyPi Kitchen's Python 3 getwriter function. Removes
extraneous newlines."""
import codecs

from kitchen.text.converters import to_bytes


def getwriter(encoding):
    """Return a :class:`codecs.StreamWriter` that resists tracing back.

    :arg encoding: Encoding to use for transforming :class:`str` strings
        into byte :class:`bytes`.
    :rtype: :class:`codecs.StreamWriter`
    :returns: :class:`~codecs.StreamWriter` that you can instantiate to wrap
        output streams to automatically translate :class:`str` strings into
        :attr:`encoding`.

    This is a reimplemetation of :func:`codecs.getwriter` that returns
    a :class:`~codecs.StreamWriter` that resists issuing tracebacks.  The
    :class:`~codecs.StreamWriter` that is returned uses
    :func:`kitchen.text.converters.to_bytes` to convert :class:`str`
    strings into byte :class:`bytes`.  The departures from
    :func:`codecs.getwriter` are:

    1) The :class:`~codecs.StreamWriter` that is returned will take byte
       :class:`bytes` as well as :class:`str` strings.  Any byte
       :class:`bytes` will be passed through unmodified.
    2) The default error handler for unknown bytes is to ``replace`` the bytes
       with the unknown character (``?`` in most ascii-based encodings, ``�``
       in the utf encodings) whereas :func:`codecs.getwriter` defaults to
       ``strict``.  Like :class:`codecs.StreamWriter`, the returned
       :class:`~codecs.StreamWriter` can have its error handler changed in
       code by setting ``stream.errors = 'new_handler_name'``

    Example usage::

        $ LC_ALL=C python
        >>> import sys
        >>> from kitchen.text.converters import getwriter
        >>> UTF8Writer = getwriter('utf-8')
        >>> unwrapped_stdout = sys.stdout
        >>> sys.stdout = UTF8Writer(unwrapped_stdout)
        >>> print 'caf\\xc3\\xa9'
        café
        >>> print u'caf\\xe9'
        café
        >>> ASCIIWriter = getwriter('ascii')
        >>> sys.stdout = ASCIIWriter(unwrapped_stdout)
        >>> print 'caf\\xc3\\xa9'
        café
        >>> print u'caf\\xe9'
        caf?

    .. seealso::

        API docs for :class:`codecs.StreamWriter` and :func:`codecs.getwriter`
        and `Print Fails <http://wiki.python.org/moin/PrintFails>`_ on the
        python wiki.

    .. versionadded:: kitchen 0.2a2, API: kitchen.text 1.1.0
    """
    class _StreamWriter(codecs.StreamWriter):
        # :W0223: We don't need to implement all methods of StreamWriter.
        #   This is not the actual class that gets used but a replacement for
        #   the actual class.
        # :C0111: We're implementing an API from the stdlib.  Just point
        #   people at that documentation instead of writing docstrings here.
        # pylint:disable-msg=W0223,C0111
        def __init__(self, stream, errors='replace'):
            codecs.StreamWriter.__init__(self, stream, errors)

        def encode(self, msg, errors='replace'):
            return (to_bytes(msg, encoding=self.encoding, errors=errors),
                    len(msg))

    _StreamWriter.encoding = encoding
    return _StreamWriter
