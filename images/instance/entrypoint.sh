#!/bin/bash
set -euo pipefail
cd /home/container
# Native Eggs have a fixed startup. Do not eval an environment-supplied command.
exec /usr/local/bin/soneyko-instance "$@"
