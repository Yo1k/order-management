#!/usr/bin/env bash
# Uses Mypy to check static types in the code.

set -eu

source ./harness-util/python-util.sh
mypy_check
