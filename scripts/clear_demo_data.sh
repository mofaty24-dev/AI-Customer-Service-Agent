#!/usr/bin/env bash
# DEV ONLY. Removes fake rows made by seed_demo_traffic.sh and simulate_spend.sh,
# and today's Cost Guard events (so you can demo the guard again).
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

psql_exec -c "DELETE FROM conversation_turn_audit
              WHERE conversation_id LIKE 'demo-%' OR conversation_id LIKE 'sim-%';"
psql_exec -c "DELETE FROM cost_guard_events WHERE event_date = (now() AT TIME ZONE 'UTC')::date;"
echo "Done. If the kill switch was flipped by the guard, run: ./scripts/kill_switch.sh on"
