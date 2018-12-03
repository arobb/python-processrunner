#!/usr/bin/env bash

pythonlist=("python27" "python2.7" "python35" "python3.5" "python36" "python3.6" "python37" "python3.7")
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

# Run the tests for each
for i in ${runlist[@]}; do
    echo "Running tests for $i"
    /usr/bin/env $i -m unittest discover -p '*_test.py'
done