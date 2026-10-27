-- Self-cleaning test: everything runs inside a transaction that is rolled back.
-- Thresholds are set relative to today's current spend, so it is safe on a dev DB.
BEGIN;

DO $$
DECLARE
    base NUMERIC := fn_daily_cost();
    r    RECORD;
    n    INT;
BEGIN
    UPDATE system_settings SET value = (base + 1)::text WHERE key = 'DAILY_COST_WARN_USD';
    UPDATE system_settings SET value = (base + 2)::text WHERE key = 'DAILY_COST_KILL_USD';
    UPDATE system_settings SET value = 'true'           WHERE key = 'AUTOMATION_ENABLED';
    DELETE FROM cost_guard_events WHERE event_date = (now() AT TIME ZONE 'UTC')::date;

    -- 1) below warn -> nothing happens
    SELECT count(*) INTO n FROM run_cost_guard();
    ASSERT n = 0, 'T1 failed: expected no alert below the warn threshold';

    -- 2) cross warn -> exactly one warn alert
    INSERT INTO conversation_turn_audit (conversation_id, turn_id, channel, outcome, cost_usd)
    VALUES ('test-cg', 't1', 'web', 'auto_send', 1.5);
    SELECT * INTO r FROM run_cost_guard();
    ASSERT r.out_level = 'warn', 'T2 failed: expected a warn alert';
    ASSERT fn_setting('AUTOMATION_ENABLED') = 'true', 'T2 failed: warn must not flip the kill switch';

    -- 3) same level again -> no duplicate alert
    SELECT count(*) INTO n FROM run_cost_guard();
    ASSERT n = 0, 'T3 failed: warn alert fired twice';

    -- 4) cross kill -> kill alert + switch flipped
    INSERT INTO conversation_turn_audit (conversation_id, turn_id, channel, outcome, cost_usd)
    VALUES ('test-cg', 't2', 'web', 'auto_send', 1.0);
    SELECT * INTO r FROM run_cost_guard();
    ASSERT r.out_level = 'kill', 'T4 failed: expected a kill alert';
    ASSERT fn_setting('AUTOMATION_ENABLED') = 'false', 'T4 failed: kill switch was not flipped';

    -- 5) kill again -> no duplicate
    SELECT count(*) INTO n FROM run_cost_guard();
    ASSERT n = 0, 'T5 failed: kill alert fired twice';

    -- 6) audit immutability
    BEGIN
        UPDATE conversation_turn_audit SET cost_usd = 0 WHERE conversation_id = 'test-cg';
        RAISE EXCEPTION 'T6 failed: audit row was editable' USING ERRCODE = 'P0001';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'T6 failed%' THEN RAISE; END IF;
    END;
    UPDATE conversation_turn_audit SET overridden = true, human_agent_id = 'agent-1'
     WHERE conversation_id = 'test-cg' AND turn_id = 't1';

    -- 7) idempotency key
    BEGIN
        INSERT INTO conversation_turn_audit (conversation_id, turn_id, channel, outcome)
        VALUES ('test-cg', 't1', 'web', 'auto_send');
        RAISE EXCEPTION 'T7 failed: duplicate turn was accepted';
    EXCEPTION WHEN unique_violation THEN
        NULL;
    END;

    RAISE NOTICE 'ALL CHECKS PASSED (7/7)';
END $$;

ROLLBACK;
