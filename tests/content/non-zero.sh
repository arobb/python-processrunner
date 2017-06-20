#!/usr/bin/env bash
echo "Some text on stdout"
echo 1>&2 "Some text on stderr"
echo 1>&2 "Failing this run"
exit 1
