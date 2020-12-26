#!/usr/bin/env bash
# Use rst2html-2.7.py README.rst /dev/null to validate the formatting of README
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
VERSION_FILE="$DIR/VERSION"

# Working directory must be clean for this to create a distribution file cleanly
VERSION=$( python -c "import sys; from gitversion import get_git_version; sys.stdout.write(get_git_version())" )
echo "$VERSION" > $VERSION_FILE

rm -rf $DIR/processrunner.egg-info
python setup.py sdist

# Remove the VERSION file now that it's in the dist directory
rm $VERSION_FILE

# Sign the distribution
gpg --detach-sign -a $DIR/dist/*.tar.gz