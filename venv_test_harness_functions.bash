# Set up isolated, clean Python venv
#
# This is designed to be sourced from other bash scripts

function prepare_venv() {
  # Assume the user starts in the ypkg dir
  echo ">>> Updating the ypkg git repo ..."
  # ensure we show the current branch
  git fetch && git pull && git branch

  echo ">>> Cloning or updating the eopkg git repo ..."
  # assume that eopkg lives in ../eopkg
  #   git -C ../ clone https://github.com/getsolus/eopkg.git ||
  #     { git -C ../eopkg/ switch master && git -C ../eopkg/ pull; }

  echo ">>> Set up a clean venv with symlink to ../eopkg/pisi in venv site-packages/ dir ..."
  python3 -m venv --clear venv
  source venv/bin/activate
  python3 -m pip install .
  python3 -m pip install ../eopkg
  install_solus_prereq_pkgs
}

function install_solus_prereq_pkgs() {
  # we are currently carrying a patch to iksemel that has not yet been upstreamed
  sudo eopkg it iksemel
  ln -srv /usr/lib/python3.12/site-packages/iksemel.cpython-312-x86_64-linux-gnu.so venv/lib/python3.12/site-packages/
}

function help() {
  cat <<EOF

    1. To activate the newly prepared venv, execute:

        source venv/bin/activate /
        source venv/bin/activate.fish /
        source venv/bin/activate.zsh

      ... depending on which shell you use.

    2. When you are done testing, execute:

        deactivate

      ... to exit the venv.

    3. To run the integration tests, execute:
    
        ./run_release_tests.sh

      ... this will run in a clean checkout + venv
          and will deactivate the venv after
          run is done.

EOF
}
