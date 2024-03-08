# Release testing requirements

This documents how to peform reproducible testing of ypkg-py3 + eopkg-py3 commits.

## Automated release testing

Run `./run_release_tests.sh <path to the root of your git clone of the solus packages repo>`

This will update the ypkg/master and eopkg/python3 branches to their newest commits and test against those.

## Manual testing

Start by running `./set_up_ypkg_test_venv.sh` to prepare a stand-alone python3 venv that links to the ../eopkg/pisi module.

and follow the instructions it prints out to activate the isolated ypkg_test_venv.

Note that `set_up_ypkg_test_venv.sh` will reset the venv each time it is run.

### Run a build

To run a manual package build, run:

    time fakeroot ./ypkg-build <path to package.yml under test>

### Exit testing venv

When you are done testing, remember to run `deactivate` to exit the ypkg_test_env venv.
