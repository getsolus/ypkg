#!/usr/bin/env bash
#
# Set up isolated, clean ypkg_test_venv python venv
#

source ./venv_test_harness_functions.bash

# set up a nice and clean venv environment from newest upstream commits
prepare_venv

# show useful next steps re. testing
help

echo "\nNote that the ypkg_test_venv venv is currently active.\n"
