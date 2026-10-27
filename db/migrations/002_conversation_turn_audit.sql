-- 002: core audit table (SDD section 9.2)
-- One row per customer turn. Idempotency key = (conversation_id, turn_id).

CREATE TABLE conversation_turn_audit (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id   TEXT          NOT NULL,   -- ticket_id / conversation_id
    turn_id           TEXT          NOT NULL,
    received_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    channel           TEXT          NOT NULL
                      CHECK (channel IN ('web', 'email', 'whatsapp')),
    intent            TEXT
                      CHECK (intent IN ('policy_question', 'purchase_intent', 'greeting',
                                        'off_topic', 'escalation_request', 'ambiguous')),
    safety_flags      JSONB         NOT NULL DEFAULT '{}'::jsonb,
    routing_reasons   TEXT[]        NOT NULL DEFAULT '{}',
    outcome           TEXT          NOT NULL
                      CHECK (outcome IN ('auto_send', 'human_review', 'all_rejected')),
    drafts            JSONB         NOT NULL DEFAULT '[]'::jsonb,
    rejection_reasons TEXT[]        NOT NULL DEFAULT '{}',
    chosen_draft      TEXT,
    final_reply       TEXT,
    citations         JSONB         NOT NULL DEFAULT '[]'::jsonb,
    product_skus      TEXT[]        NOT NULL DEFAULT '{}',
    input_tokens      INTEGER       NOT NULL DEFAULT 0 CHECK (input_tokens  >= 0),
    output_tokens     INTEGER       NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
    cost_usd          NUMERIC(10,6) NOT NULL DEFAULT 0 CHECK (cost_usd >= 0),
    latency_ms        INTEGER       CHECK (latency_ms >= 0),
    model_version     TEXT,
    reviewer_score    NUMERIC(5,3), -- scale to be agreed with Basmala
    overridden        BOOLEAN       NOT NULL DEFAULT false,
    human_agent_id    TEXT,
    CONSTRAINT uq_audit_turn UNIQUE (conversation_id, turn_id)
);

COMMENT ON TABLE conversation_turn_audit IS
  'Immutable per-turn audit record (12-month retention). Only overridden / human_agent_id may be updated.';

-- Daily cost, reports and the backlog monitor all filter by time
CREATE INDEX idx_audit_received_at  ON conversation_turn_audit (received_at);
CREATE INDEX idx_audit_outcome_time ON conversation_turn_audit (outcome, received_at);

-- Immutability: after insert, only the human-override fields may change.
CREATE FUNCTION trg_audit_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF (to_jsonb(NEW) - 'overridden' - 'human_agent_id')
       IS DISTINCT FROM
       (to_jsonb(OLD) - 'overridden' - 'human_agent_id') THEN
        RAISE EXCEPTION 'conversation_turn_audit is immutable (only overridden/human_agent_id can change)';
    END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER audit_immutable
    BEFORE UPDATE ON conversation_turn_audit
    FOR EACH ROW EXECUTE FUNCTION trg_audit_immutable();
