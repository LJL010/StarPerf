#!/bin/bash
# run_least_hop.sh
PROJECT_ROOT=$(realpath $(dirname "$0")/../../..)
PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH python3 $(dirname "$0")/least_hop_path.py "$@"

