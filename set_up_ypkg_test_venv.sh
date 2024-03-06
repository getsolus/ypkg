#!/usr/bin/env bash
#
# Set up isolated, clean ypkg_test_venv python venv

# Assume the user starts in the ypkg dir
echo ">>> Updating the ypkg git repo ..."
git fetch && git pull && git branch

echo ">>> Cloning or updating the eopkg git repo ..."
# assume that eopkg lives in ../eopkg
git -C ../ clone https://github.com/getsolus/eopkg.git || \
{ git -C ../eopkg/ switch master && git -C ../eopkg/ fetch && git -C ../eopkg/ switch python3 && git -C ../eopkg/ pull ; }
git -C ../eopkg/ branch

echo ">>> Set up a clean ypkg_test_venv with symlink to ../eopkg/pisi in venv site-packages/ dir ..."
python3 -m venv --clear ypkg_test_venv
ln -srv ../eopkg/pisi ypkg_test_venv/lib/python3.11/site-packages/
  source ypkg_test_venv/bin/activate
python3 -m pip install -r requirements.txt
cat << EOF
1. To activate the newly prepared ypkg_test_venv, execute:

    source ypkg_test_venv/bin/activate /
    source ypkg_test_venv/bin/activat.fish / 
    source ypkg_test_venv/bin/activate.zsh

  ... depending on which shell you use.

2. To run the integration tests, execute:
    
    ./run_build_tests.sh

3. When you are done testing, execute:

    deactivate

  ... to exit the ypkg_test_venv venv.

EOF

deactivate
