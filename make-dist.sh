#!/usr/bin/env bash
# Working directory must be clean for this to create a distribution file cleanly
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
rm -rf $DIR/processrunner.egg-info
python setup.py sdist
