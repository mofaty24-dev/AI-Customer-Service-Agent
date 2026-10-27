#!/usr/bin/env bash
# Inserts one fake audit row costing <usd>, to demo the Cost Guard in dev.
# Usage: ./scripts/simulate_spend.sh 13
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

AMOUNT="${1:-}"
if ! [[ "$AMOUNT" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
  echo "usage: $0 <usd-amount>   e.g. $0 13" >&2
  exit 1
fi

psql_exec -c "INSERT INTO conversation_turn_audit
  (conversation_id, turn_id, channel, intent, outcome, cost_usd, model_version)
  VALUES ('sim-$(date +%s)', 't1', 'web', 'policy_question', 'auto_send', $AMOUNT,
          'claude-haiku-4-5-20251001');"
psql_exec -c "SELECT fn_daily_cost() AS cost_today_usd;"
