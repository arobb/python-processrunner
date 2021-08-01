#!/usr/bin/env bash
# Use rst2html-2.7.py README.rst /dev/null to validate the formatting of README
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
VERSION_FILE="$DIR/src/processrunner/VERSION"

# Working directory must be clean for this to create a distribution file cleanly
python $DIR/resources/gitversion/gitversion.py --outfile "$VERSION_FILE"

rm -rf $DIR/src/processrunner.egg-info
python setup.py sdist

# Remove the VERSION file now that it's in the dist directory
rm $VERSION_FILE

# Sign the distribution
gpg --detach-sign -a $DIR/dist/*.tar.gz