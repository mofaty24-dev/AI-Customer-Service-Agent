#!/usr/bin/env bash
# DEV ONLY. Inserts fake traffic for yesterday and the day before, so the Daily Report has data.
#   ./scripts/seed_demo_traffic.sh          normal day  (~5% of turns have no safe reply)
#   ./scripts/seed_demo_traffic.sh bad      bad day     (~20% -> the report shows "Needs attention")
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

case "${1:-normal}" in
  normal) RATE=0.05 ;;
  bad)    RATE=0.20 ;;
  *) echo "usage: $0 [normal|bad]" >&2; exit 1 ;;
esac

psql_exec -q -v reject_rate="$RATE" -f - < db/seed/demo_traffic.sql
psql_exec -c "SELECT day, turns, total_cost_usd, auto_send, human_review, all_rejected
              FROM v_daily_cost ORDER BY day DESC LIMIT 3;"
