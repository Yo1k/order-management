#!/usr/bin/env bash
# Contains Python-specific utils.
# For example, functions for managing Python virtual environment.

set -eu

source ./harness-util/util.sh

function create_python_venv() {
    IN_PYTHON_VENV=$(in_python_venv)
    if [[ ${IN_PYTHON_VENV} = "false" ]]; then
        python3 -m venv --upgrade-deps "./${PYTHON_VENV}"
        activate_python_venv;
    fi
    python3 -m pip install -r requirements.txt
    if [[ ${IN_PYTHON_VENV} = "false" ]]; then
        deactivate_python_venv;
    fi
}

function in_python_venv() {
    python3 - "./${PYTHON_VENV}" <<EOF
import sys
import os
from pathlib import PurePath
if sys.prefix == sys.base_prefix:
    print("false", end="")
else:
    expected_python_venv = PurePath(sys.argv[1]).name
    current_python_venv = PurePath(sys.prefix).name
    if current_python_venv == expected_python_venv:
        print("true", end="")
    else:
        sys.exit(("The script must be run either with Python venv named"
        + " '{expected_python_venv}' being active"
        + " or without any active venv.{linesep}").format(
        expected_python_venv = expected_python_venv, linesep = os.linesep))
EOF
}

function activate_python_venv() {
    source "./${PYTHON_VENV}/bin/activate"
}

function deactivate_python_venv() {
    deactivate
}

function pylint_check() {
    pylint "${CODE_DIR}"
}

function mypy_check() {
    mypy "${CODE_DIR}"
}

function test() {
    python3 -m unittest discover "${CODE_DIR}"
}

function verify() {
    pylint_check && mypy_check && test
}

create_python_venv > /dev/null
