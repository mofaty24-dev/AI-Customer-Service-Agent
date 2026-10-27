#!/usr/bin/env bash
# Runs every db/tests/*.sql (each one rolls itself back).
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

for f in db/tests/*.sql; do
  echo "== $f"
  psql_exec -f - < "$f"
done
