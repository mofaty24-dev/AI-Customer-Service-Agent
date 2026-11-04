-- 004: 12-month audit retention (SDD s9.1 "12 months, then automatic deletion", NFR-Audit)

INSERT INTO system_settings (key, value, description) VALUES
  ('RETENTION_MONTHS', '12',
   'Audit rows older than this many months are deleted by WF-06 (SDD s9.1). Minimum 12 is enforced.');

-- One row per run, so there is proof of what was deleted and when.
CREATE TABLE retention_log (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    retention_months INTEGER     NOT NULL,
    cutoff           TIMESTAMPTZ NOT NULL,
    rows_deleted     BIGINT      NOT NULL
);

-- Called daily by n8n WF-06. Returns exactly one row (also written to retention_log).
-- Safety rail: refuses to run if the setting is below 12 months, because deleting
-- audit data early is irreversible and would break the SDD retention requirement.
CREATE FUNCTION run_retention()
RETURNS TABLE (out_cutoff TIMESTAMPTZ, out_rows_deleted BIGINT, out_retention_months INTEGER)
LANGUAGE plpgsql AS $$
DECLARE
    v_months  INTEGER := fn_setting('RETENTION_MONTHS')::integer;
    v_cutoff  TIMESTAMPTZ;
    v_deleted BIGINT;
BEGIN
    IF v_months IS NULL OR v_months < 12 THEN
        RAISE EXCEPTION 'RETENTION_MONTHS must be >= 12 (SDD retention requirement), got %', v_months;
    END IF;

    v_cutoff := now() - make_interval(months => v_months);

    DELETE FROM conversation_turn_audit WHERE received_at < v_cutoff;
    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    INSERT INTO retention_log (retention_months, cutoff, rows_deleted)
    VALUES (v_months, v_cutoff, v_deleted);

    RETURN QUERY SELECT v_cutoff, v_deleted, v_months;
END $$;
