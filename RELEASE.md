# Release testing requirements

Start by running `./set_up_ypkg_test_venv.sh` to prepare a stand-alone python3 venv that links to the ../eopkg/pisi module.

and follow the instructions it prints out to activate the isolated ypkg_test_venv.

Note that `set_up_ypkg_test_venv.sh` will reset the venv each time it is run.

## Manual package tests

To run a manual package test, run:

    time fakeroot ./ypkg-build <path to package.yml under test>

## Exit testing venv

When you are done testing, remember to run `deactivate` to exit the ypkg_test_env venv.
