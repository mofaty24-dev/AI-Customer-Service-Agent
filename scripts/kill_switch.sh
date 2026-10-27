#!/usr/bin/env bash
# Manual control of the kill switch.  Usage: ./scripts/kill_switch.sh on|off|status
#   on  = automation enabled   (AUTOMATION_ENABLED=true)
#   off = all traffic to human (AUTOMATION_ENABLED=false)
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

case "${1:-status}" in
  on)  VALUE=true  ;;
  off) VALUE=false ;;
  status)
    psql_exec -c "SELECT key, value, updated_at, updated_by FROM system_settings WHERE key = 'AUTOMATION_ENABLED';"
    exit 0 ;;
  *) echo "usage: $0 on|off|status" >&2; exit 1 ;;
esac

psql_exec -c "UPDATE system_settings
                 SET value = '$VALUE', updated_at = now(), updated_by = 'manual'
               WHERE key = 'AUTOMATION_ENABLED';"
psql_exec -c "SELECT key, value, updated_at, updated_by FROM system_settings WHERE key = 'AUTOMATION_ENABLED';"
