#!/usr/bin/env bash
# Use rst2html-2.7.py README.rst /dev/null to validate the formatting of README

# Working directory must be clean for this to create a distribution file cleanly
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
rm -rf $DIR/processrunner.egg-info
python setup.py sdist

# Sign the distribution
gpg --detach-sign -a $DIR/dist/*.tar.gz
