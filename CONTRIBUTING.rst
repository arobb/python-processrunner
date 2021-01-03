Publishing ProcessRunner
========================
Information on contributing may get added later.

Publishing
----------
Configure Twine and the PyPi RC file at `~/.pypirc` .

.. code-block:: ini

    [distutils]
    index-servers=
        test-processrunner
        processrunner

    # Use twine upload --repository test-processrunner dist/*
    [test-processrunner]
    repository = https://test.pypi.org/legacy/
    username = __token__
    password = <your token>

    # Use twine upload --repository processrunner dist/*
    [processrunner]
    repository = https://upload.pypi.org/legacy/
    username = __token__
    password = <your token>

1. Make sure you're at the project root

2. Ensure all commits are made, pushed, and the Git environment clear

.. code-block:: bash

    git stash

3. Tag the current version

.. code-block:: bash

    git tag -a x.y.z -m "Version release message"

4. Build the release package. The resulting files will be in `./dist/`.

.. code-block:: bash

    ./make-dist.sh

5. Push to PyPi's test environment first and ensure everything looks good on
the web site.

.. code-block:: bash

    python -m twine upload --repository test-processrunner dist/*

6. Then push to PyPi's official repo.

.. code-block:: bash

    python -m twine upload --repository processrunner dist/*
