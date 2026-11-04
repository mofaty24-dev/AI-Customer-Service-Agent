-- Fake traffic for DEV ONLY: 120 turns yesterday + 100 turns the day before.
-- All rows have conversation_id 'demo-...' so scripts/clear_demo_data.sh removes them.
-- psql variable :reject_rate = share of turns with no safe reply (set by the script).
INSERT INTO conversation_turn_audit
    (conversation_id, turn_id, received_at, channel, intent, outcome, routing_reasons,
     input_tokens, output_tokens, cost_usd, latency_ms, model_version, reviewer_score, overridden)
SELECT conv, 't1', ts, channel, intent, outcome,
       CASE outcome
            WHEN 'auto_send'    THEN '{}'::text[]
            WHEN 'all_rejected' THEN ARRAY['all_drafts_rejected']
            ELSE ARRAY[(ARRAY['low_confidence','safety_flag','escalation_request','high_value_order'])
                       [1 + floor(random() * 4)::int]]
       END,
       in_tok, out_tok, cost, latency, 'claude-haiku-4-5-20251001', score,
       (outcome = 'human_review' AND random() < 0.15)
FROM (
    SELECT 'demo-' || base.d || '-' || base.g AS conv,
           (((now() AT TIME ZONE 'UTC')::date - base.d)::timestamp AT TIME ZONE 'UTC')
               + random() * interval '23 hours'                                        AS ts,
           (ARRAY['web','email','whatsapp'])[1 + floor(random() * 3)::int]             AS channel,
           (ARRAY['policy_question','purchase_intent','greeting','off_topic',
                  'escalation_request','ambiguous'])[1 + floor(random() * 6)::int]     AS intent,
           CASE WHEN base.r < :reject_rate        THEN 'all_rejected'
                WHEN base.r < :reject_rate + 0.25 THEN 'human_review'
                ELSE 'auto_send' END                                                    AS outcome,
           800 + floor(random() * 1700)::int                                           AS in_tok,
           150 + floor(random() * 250)::int                                            AS out_tok,
           round((0.02 + random() * 0.10)::numeric, 6)                                 AS cost,
           3000 + floor(random() * 9000)::int                                          AS latency,
           round((0.75 + random() * 0.25)::numeric, 3)                                 AS score
    FROM (
        SELECT x.d, g.g, random() AS r
        FROM (VALUES (1, 120), (2, 100)) AS x(d, n)
        CROSS JOIN LATERAL generate_series(1, x.n) AS g(g)
    ) base
) m
ON CONFLICT (conversation_id, turn_id) DO NOTHING;
