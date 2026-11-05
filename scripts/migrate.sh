#!/usr/bin/env bash
# Applies db/migrations/*.sql in order. Each file runs in ONE transaction together
# with its schema_migrations row, so a failed migration leaves nothing half-applied.
# Safe to re-run: already-applied files are skipped.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

psql_exec -q -c "CREATE TABLE IF NOT EXISTS schema_migrations (
  version    TEXT PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT now());"

for f in db/migrations/*.sql; do
  v="$(basename "$f")"
  applied="$(psql_exec -tA -c "SELECT 1 FROM schema_migrations WHERE version = '$v'")"
  if [ -n "$applied" ]; then
    echo "skip   $v"
    continue
  fi
  echo "apply  $v"
  { cat "$f"; echo; echo "INSERT INTO schema_migrations (version) VALUES ('$v');"; } \
    | psql_exec -q --single-transaction -f -
done
echo "done."
