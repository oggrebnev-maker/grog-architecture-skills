#!/bin/bash
# Runs every test of the toolkit. Exit code is non-zero on any failure.
set -e
cd "$(dirname "$0")/plugins/architecture"
python3 -B -m unittest discover -s skills/architecture/scripts -p 'test_*.py'
python3 -B -m unittest discover -s hooks -p 'test_*.py'
