#!/usr/bin/env bash
# Creates if necessary and activates a Python virtual environment for the project.
# Adds the project root directory to the `PYTHONPATH` environment variable.

source ./harness-util/util.sh
./harness-util/python-util.sh
source ./"${PYTHON_VENV}"/bin/activate
[[ ":${PYTHONPATH}:" != *":${PWD}:"* ]] && export PYTHONPATH=${PYTHONPATH:+${PYTHONPATH}:}${PWD}
