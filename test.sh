#!/bin/bash
# Runs every test of the toolkit. Exit code is non-zero on any failure.
set -e
cd "$(dirname "$0")"
python3 -B -m unittest test_project_sh
(cd lib && python3 -B -m unittest test_user_settings)
(cd skills/design-transfer/scripts && python3 -B -m unittest test_guard)
cd plugins/architecture
python3 -B -m unittest discover -s skills/architecture/scripts -p "test_*.py"
python3 -B -m unittest discover -s hooks -p "test_*.py"
