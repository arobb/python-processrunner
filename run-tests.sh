#!/usr/bin/env bash
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

pythonlist=()
pythonlist+=("python27" "python2.7")
pythonlist+=("python37" "python3.7")
pythonlist+=("python38" "python3.8")
pythonlist+=("python39" "python3.9")
runlist=()

# Determine which pythons exist
for i in ${pythonlist[@]}; do
    if command -v "$i" 2>/dev/null; then
        runlist+=("$i")
    fi
done

# Print the list of pythons
for i in ${runlist[@]}; do
    echo "Found $i"
done

echo ""

# Validate or create virtualenvs for each version
for i in ${runlist[@]}; do
    echo -n "Checking for VirtualEnv corresponding to $i... "
    venv_dir="$DIR/venv-$i"

    if [ ! -d "$venv_dir" ]; then
      echo "No; Creating VirtualEnv for $i"
      virtualenv --quiet --python $i "$venv_dir"

      # Install dev package
      source $venv_dir/bin/activate
      pip install -e $DIR[dev,test]
      deactivate
    else
      echo "Yes"
    fi
done

# Run the tests for each
for i in ${runlist[@]}; do
    echo ""
    echo "Running tests for $i"
    venv_dir="$DIR/venv-$i"
    source $venv_dir/bin/activate

    if [ "$1" == "" ]; then
      # python -m unittest discover -p '*_test.py'
      pytest
    else
      # python -m unittest discover -p "$1"
      pytest -v "$DIR/tests/tests/$1"
    fi

    deactivate
done