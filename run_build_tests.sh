#!/usr/bin/env bash
#
# Run the actual ypkg build integration tests

# assume this is called from the ypkg dir
function show_git_refs () {
    echo ">>> eopkg git ref: $(git -C ../eopkg/ rev-parse --short HEAD)"
    echo ">>>  ypkg git ref: $(git rev-parse --short HEAD)"
}

time fakeroot ./ypkg-build examples/nano.yml

show_git_refs
