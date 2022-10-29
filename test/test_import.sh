#! /bin/bash

if [ -d bin ]; then
  read -p "Existing venv found. Delete it? [Y/N] " -n 1
  if [ "$(echo "$REPLY" | tr A-Z a-z)" = "y" ]; then
    rm -r ./bin ./include ./lib ./pyvenv.cfg
  fi
fi

python3 -m venv .

env -i bash --norc -c './bin/pip install ..' || exit 1
env -i bash --norc -c './bin/python test_import.py' || exit 1

rm -r ./bin ./include ./lib ./pyvenv.cfg
