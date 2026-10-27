#!/usr/bin/env bash
# Shared helper - sourced by the other scripts. Not meant to be run directly.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "Missing .env - run: cp .env.example .env" >&2
  exit 1
fi
set -a; . ./.env; set +a

# psql inside the running db container
psql_exec() {
  docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"
}
