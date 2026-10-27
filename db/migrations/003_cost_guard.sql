-- 003: kill switch + daily cost guard (SDD sections 6, 15, 16)

-- ---------- settings (kill switch lives here so a workflow can flip it) ----------
CREATE TABLE system_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT        NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_by  TEXT        NOT NULL DEFAULT 'migration'
);

INSERT INTO system_settings (key, value, description) VALUES
  ('AUTOMATION_ENABLED',   'true', 'Kill switch. false = every message goes to the human queue (WF-01 step 2)'),
  ('DAILY_COST_WARN_USD',  '12',   'Send a warning alert when today''s AI cost reaches this (SDD s16)'),
  ('DAILY_COST_KILL_USD',  '20',   'Flip AUTOMATION_ENABLED=false when today''s AI cost reaches this');

CREATE FUNCTION fn_setting(p_key TEXT) RETURNS TEXT
LANGUAGE sql STABLE AS $$
    SELECT value FROM system_settings WHERE key = p_key
$$;

-- ---------- alert log (one alert per level per day, no spam) ----------
CREATE TABLE cost_guard_events (
    event_date  DATE          NOT NULL,
    level       TEXT          NOT NULL CHECK (level IN ('warn', 'kill')),
    total_cost  NUMERIC(10,4) NOT NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    PRIMARY KEY (event_date, level)
);

-- ---------- cost helpers (day boundary = UTC) ----------
CREATE FUNCTION fn_daily_cost(p_day DATE DEFAULT (now() AT TIME ZONE 'UTC')::date)
RETURNS NUMERIC
LANGUAGE sql STABLE AS $$
    SELECT COALESCE(SUM(cost_usd), 0)
    FROM conversation_turn_audit
    WHERE received_at >= (p_day::timestamp       AT TIME ZONE 'UTC')
      AND received_at <  ((p_day + 1)::timestamp AT TIME ZONE 'UTC')
$$;

CREATE VIEW v_daily_cost AS
SELECT (received_at AT TIME ZONE 'UTC')::date                 AS day,
       count(*)                                               AS turns,
       round(sum(cost_usd), 4)                                AS total_cost_usd,
       round(avg(cost_usd), 6)                                AS avg_cost_per_turn_usd,
       sum(input_tokens)                                      AS input_tokens,
       sum(output_tokens)                                     AS output_tokens,
       count(*) FILTER (WHERE outcome = 'auto_send')          AS auto_send,
       count(*) FILTER (WHERE outcome = 'human_review')       AS human_review,
       count(*) FILTER (WHERE outcome = 'all_rejected')       AS all_rejected
FROM conversation_turn_audit
GROUP BY 1
ORDER BY 1 DESC;

-- ---------- the guard itself ----------
-- Called by n8n WF-05 every hour. Returns 0 rows (nothing to do) or 1 row
-- (an alert to send). Idempotent: each level fires once per day.
CREATE FUNCTION run_cost_guard()
RETURNS TABLE (out_level TEXT, out_total_cost NUMERIC, out_threshold NUMERIC, out_action TEXT)
LANGUAGE plpgsql AS $$
DECLARE
    v_today DATE    := (now() AT TIME ZONE 'UTC')::date;
    v_total NUMERIC := fn_daily_cost(v_today);
    v_warn  NUMERIC := fn_setting('DAILY_COST_WARN_USD')::numeric;
    v_kill  NUMERIC := fn_setting('DAILY_COST_KILL_USD')::numeric;
BEGIN
    IF v_total >= v_kill THEN
        INSERT INTO cost_guard_events (event_date, level, total_cost)
        VALUES (v_today, 'kill', v_total)
        ON CONFLICT DO NOTHING;
        IF FOUND THEN
            UPDATE system_settings
               SET value = 'false', updated_at = now(), updated_by = 'cost_guard'
             WHERE key = 'AUTOMATION_ENABLED';
            RETURN QUERY SELECT 'kill'::text, v_total, v_kill,
                                'AUTOMATION_ENABLED set to false - all traffic now goes to the human queue'::text;
        END IF;
    ELSIF v_total >= v_warn THEN
        INSERT INTO cost_guard_events (event_date, level, total_cost)
        VALUES (v_today, 'warn', v_total)
        ON CONFLICT DO NOTHING;
        IF FOUND THEN
            RETURN QUERY SELECT 'warn'::text, v_total, v_warn,
                                'Warning only - automation still running'::text;
        END IF;
    END IF;
END $$;
