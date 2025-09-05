#!/usr/bin/env bash
#
# Run the actual ypkg build integration tests

SOLUSREPO="$1"

function check_solus_repo() {
    # the first argument should be the solus packages repo git root path
    if [[ -z "${SOLUSREPO}" ]]; then
        echo -e "\n  Please run $0 with the path to the root of the solus packages repo.\n" && exit 1
        else:
        test -d ${SOLUSREPO}/.git -a -d ${SOLUSREPO}/common ||
            { echo -e "Invalid solus packages repo path '$1' ?" && exit 1; }
    fi
}

source ./venv_test_harness_functions.bash

# assume this is called from the ypkg dir
function show_git_refs() {
    echo -e "Tests run against the following eopkg and ypkg git refs:\n"
    echo -e "---------------------------------------------------"
    echo -e ">>> eopkg: $(git -C ../eopkg/ rev-parse HEAD)"
    echo -e "---------------------------------------------------"
    echo -e ">>>  ypkg: $(git rev-parse HEAD)"
    echo -e "---------------------------------------------------"
}

# specify without leading and trailing slash '/' please
# recipes with emul32 set will fail to build!
TEST_PKGS=(
    l/lzip
)

function run_tests() {
    echo -e "\nRunning ypkg release test builds ...\n"
    {
        for p in ${TEST_PKGS[@]}; do
            time fakeroot ypkg build ${SOLUSREPO}/packages/${p}/package.yml
        done
    }
    echo -e "\nFinished running ypkg release test builds.\n"
}

time {
    check_solus_repo
    prepare_venv
    run_tests
    show_git_refs
    unset SOLUSREPO
    unset TEST_PKGS
    deactivate
    echo -e "\nExited venv.\n"
}
