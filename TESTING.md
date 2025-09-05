# Release testing requirements

This documents how to perform reproducible testing of `ypkg` + `eopkg` commits.

## Automated release testing

Run `./run_release_tests.sh <path to the root of your git clone of the solus packages repo>`

This will update the ypkg/master and eopkg/master branches to their newest commits and test against those.

## Manual testing

Start by running `./prepare_venv.sh` to prepare a stand-alone Python 3 venv with everything needed to run `ypkg`. Follow the instructions it prints out to activate the isolated venv.

> ![Note]
The `prepare_venv.sh` script will reset the venv each time it is run.

### Run a simple build

To run a manual package build, run:

    time fakeroot ypkg build path/to/package.yml

### Run a more complicated build with dependencies

To run a manual package build with dependencies, run:

    ypkg install-deps path/to/package.yml
    time fakeroot ypkg build path/to/package.yml

### Remove manually installed dependencies from the step above

Check the eopkg history with `eopkg history`, then find the transaction index of the operation before the operation
that installed the dependencies and run `eopkg history -t <the transaction>`

### Exit testing venv

When you are done testing, remember to run `deactivate` to exit the venv.
