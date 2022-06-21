#!/usr/bin/env bash
# Uses Pylint to analyze and report errors, check style of the code.

set -eu

source ./harness-util/python-util.sh
pylint_check
