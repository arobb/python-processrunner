Examples
========

Viewing log output
------------------
.. code-block:: python

    # Quick way to get output
    import logging
    from processrunner import ProcessRunner as pr

    logging.basicConfig(level=logging.INFO)

    if __name__ == "__main__":
        print("\n".join(
            pr(['seq', '-f', 'Line %g', '10']).output
        ))
