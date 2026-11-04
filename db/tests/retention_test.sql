-- Self-cleaning test: runs in a transaction that is rolled back.
BEGIN;

DO $$
DECLARE
    -- rows that are already too old on this DB (so the test also works on dev data)
    base BIGINT;
    r    RECORD;
BEGIN
    UPDATE system_settings SET value = '12' WHERE key = 'RETENTION_MONTHS';
    SELECT count(*) INTO base FROM conversation_turn_audit
     WHERE received_at < now() - interval '12 months';

    INSERT INTO conversation_turn_audit (conversation_id, turn_id, channel, outcome, received_at) VALUES
      ('test-ret', 'old-1',    'web', 'auto_send', now() - interval '13 months'),
      ('test-ret', 'old-2',    'web', 'auto_send', now() - interval '24 months'),
      ('test-ret', 'recent-1', 'web', 'auto_send', now() - interval '11 months'),
      ('test-ret', 'recent-2', 'web', 'auto_send', now());

    -- 1) old rows are deleted, recent rows are kept
    SELECT * INTO r FROM run_retention();
    ASSERT r.out_rows_deleted = base + 2,
        format('T1 failed: expected %s deleted, got %s', base + 2, r.out_rows_deleted);
    ASSERT (SELECT count(*) FROM conversation_turn_audit
             WHERE conversation_id = 'test-ret' AND turn_id LIKE 'old-%') = 0,
        'T1 failed: old rows still present';
    ASSERT (SELECT count(*) FROM conversation_turn_audit
             WHERE conversation_id = 'test-ret' AND turn_id LIKE 'recent-%') = 2,
        'T1 failed: recent rows were deleted';

    -- 2) the run is logged
    ASSERT (SELECT count(*) FROM retention_log WHERE rows_deleted = base + 2) = 1,
        'T2 failed: run was not logged';

    -- 3) running again deletes nothing (idempotent)
    SELECT * INTO r FROM run_retention();
    ASSERT r.out_rows_deleted = 0, 'T3 failed: second run deleted rows';

    -- 4) safety rail: below 12 months is refused and deletes nothing
    UPDATE system_settings SET value = '6' WHERE key = 'RETENTION_MONTHS';
    BEGIN
        PERFORM run_retention();
        RAISE EXCEPTION 'T4 failed: retention below 12 months was allowed';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'T4 failed%' THEN RAISE; END IF;
    END;
    ASSERT (SELECT count(*) FROM conversation_turn_audit WHERE conversation_id = 'test-ret') = 2,
        'T4 failed: rows were deleted despite the refusal';

    RAISE NOTICE 'ALL CHECKS PASSED (4/4)';
END $$;

ROLLBACK;
