# ShopAssist AI – Database & Automation (DB/Automation Lead)

First deliverable of the data layer for **ShopAssist AI** (SDD-001 v1.0).
It contains the audit schema, the kill switch, and **WF-05 Cost Guard**, an n8n
workflow that watches daily AI spend and shuts automation down automatically.

| Piece | SDD reference |
|---|---|
| `conversation_turn_audit` table (immutable, idempotent) | §9.2, §11 |
| `system_settings` – `AUTOMATION_ENABLED` kill switch | §6.2 step 2, §15 |
| `run_cost_guard()` + n8n workflow **WF-05** | §16 (daily cost > $12 / $200 per month) |
| `run_retention()` + n8n workflow **WF-06** (12-month audit deletion) | §9.1, NFR-Audit |
| n8n workflow **WF-02** Daily Report (Slack summary + attention rules) | – |
| pgvector extension enabled (for RAG later) | §4.3 |

## Repo layout

```
.
├── docker-compose.yml            # PostgreSQL 16 + pgvector, and n8n (dev)
├── .env.example                  # copy to .env (never commit .env)
├── db/
│   ├── migrations/               # 001..004, applied in order, once each
│   ├── seed/demo_traffic.sql     # fake traffic for dev demos
│   └── tests/                    # self-cleaning SQL tests
│       ├── cost_guard_test.sql   #   7 checks
│       └── retention_test.sql    #   4 checks
├── workflows/                    # import into n8n
│   ├── WF-05_cost_guard.json
│   ├── WF-06_retention.json
│   └── WF-02_daily_report.json
└── scripts/
    ├── migrate.sh                # apply pending migrations
    ├── test.sh                   # run SQL tests
    ├── simulate_spend.sh         # fake spend, to demo the Cost Guard
    ├── seed_demo_traffic.sh      # fake yesterday traffic, to demo the Daily Report
    ├── clear_demo_data.sh        # remove all fake data (dev only)
    └── kill_switch.sh            # on | off | status
```

## Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- Git
- Windows: run the scripts from **WSL** or **Git Bash**

---

## Part 1 – Database

### Step 1. Configure
```bash
cp .env.example .env
```
Edit `.env` and set `POSTGRES_PASSWORD`. Leave `SLACK_WEBHOOK_URL` empty for now.

### Step 2. Start PostgreSQL
```bash
docker compose up -d db
docker compose ps        # wait until db shows "healthy"
```

### Step 3. Apply the migrations
```bash
./scripts/migrate.sh
```
Expected:
```
apply  001_extensions.sql
apply  002_conversation_turn_audit.sql
apply  003_cost_guard.sql
done.
```
Run it again – every file shows `skip`. Each migration runs in a single
transaction together with its `schema_migrations` row, so a failure never leaves
a half-applied schema.

### Step 4. Run the tests
```bash
./scripts/test.sh
# NOTICE:  ALL CHECKS PASSED (7/7)
```
The test runs inside a transaction that is rolled back, so it leaves no data
behind. It verifies: no alert below warn, one warn alert, no duplicate alerts,
kill switch flips at the kill threshold, audit rows are immutable (except
`overridden` / `human_agent_id`), and the `(conversation_id, turn_id)`
idempotency key rejects duplicates.

### What the schema gives you
- **Idempotency:** WF-01 can insert with
  `INSERT ... ON CONFLICT (conversation_id, turn_id) DO NOTHING` – a retried
  webhook never creates a second record.
- **Immutability:** a trigger blocks edits to any audit column except the two
  human-override fields.
- **Kill switch in the DB:** `AUTOMATION_ENABLED` lives in `system_settings`
  (instead of only an env var) so a workflow can flip it without a redeploy.
  WF-01 reads it as its step 2:
  ```sql
  SELECT fn_setting('AUTOMATION_ENABLED') = 'true' AS automation_on;
  ```
- **Useful view:** `SELECT * FROM v_daily_cost;` – turns, cost, avg cost/turn,
  and auto-send / human-review / rejected counts per day.

---

## Part 2 – Automation (n8n WF-05 Cost Guard)

**How it works:** every hour n8n calls `SELECT * FROM run_cost_guard();`.

| Today's AI cost | What happens | Repeats? |
|---|---|---|
| < `DAILY_COST_WARN_USD` (12) | nothing – function returns 0 rows, workflow ends | – |
| ≥ warn, < kill | one **warn** alert to Slack | once per day |
| ≥ `DAILY_COST_KILL_USD` (20) | `AUTOMATION_ENABLED` set to `false` + one **kill** alert | once per day |

Thresholds are rows in `system_settings`, so you can change them with SQL, no
workflow edit needed:
```sql
UPDATE system_settings SET value = '15' WHERE key = 'DAILY_COST_WARN_USD';
```

### Step 5. Start n8n
```bash
docker compose up -d n8n
```
Open http://localhost:5678 and create the owner account.

### Step 6. Create the Postgres credential
n8n → **Credentials → Create → Postgres**:

| Field | Value |
|---|---|
| Host | `db` *(the compose service name, not localhost)* |
| Database | value of `POSTGRES_DB` |
| User / Password | values from `.env` |
| Port | `5432` |
| SSL | Disable |

Name it **ShopAssist Postgres**.

### Step 7. Import the workflow
n8n → **Workflows → Import from file** → `workflows/WF-05_cost_guard.json`.
Open the **Run Cost Guard** node and select the credential from Step 6.

### Step 8. (Optional) Slack alerts
Create a Slack *Incoming Webhook*, put the URL in `.env` as `SLACK_WEBHOOK_URL`,
then `docker compose up -d n8n` to reload the env.

### Step 9. Demo it end to end
```bash
./scripts/simulate_spend.sh 13     # fake $13 spend today
```
In n8n click **Execute workflow** → you get a ⚠️ **warn** alert.
Click it again → nothing (no duplicate alert).

```bash
./scripts/simulate_spend.sh 8      # total is now $21
```
Execute again → 🛑 **kill** alert, and:
```bash
./scripts/kill_switch.sh status    # AUTOMATION_ENABLED = false, updated_by = cost_guard
```

### Step 10. Activate
Toggle the workflow to **Active**. It now runs every hour.

### After a kill – resuming
```bash
./scripts/kill_switch.sh on
```
The guard will **not** re-kill again the same day (the event was already logged).
That is deliberate: re-enabling is a human decision.

> **Clean up demo data** before real use:
> `DELETE FROM conversation_turn_audit WHERE conversation_id LIKE 'sim-%';`
> (and `DELETE FROM cost_guard_events;`)

---

## Part 2b – Audit retention (n8n WF-06)

SDD §9.1: audit records are kept **12 months, then deleted automatically**.

**How it works:** every day at 03:00 n8n calls `SELECT * FROM run_retention();`.
The function deletes rows in `conversation_turn_audit` older than
`RETENTION_MONTHS` (default 12), writes one row to `retention_log`, and returns
the cutoff date and how many rows were deleted.

**Safety rail:** the function **refuses to run** if `RETENTION_MONTHS` is below
12, because deleting audit data early is irreversible and would break the SDD
requirement. If you ever need a shorter period (e.g. a privacy decision), change
the check inside `run_retention()` in a new migration, with team approval.

### Apply and test
```bash
./scripts/migrate.sh        # applies 004_retention.sql
./scripts/test.sh           # retention_test.sql: ALL CHECKS PASSED (4/4)
```
The test checks: old rows are deleted, recent rows are kept, the run is logged,
a second run deletes nothing, and a setting below 12 is refused.

### Activate the workflow
n8n -> **Workflows -> Import from file** -> `workflows/WF-06_retention.json`,
select the **ShopAssist Postgres** credential in the **Run Retention** node, then
toggle **Active**.

### Check what it did
```sql
SELECT run_at, cutoff, rows_deleted FROM retention_log ORDER BY run_at DESC LIMIT 10;
```

> The retention run is itself a destructive action, so test it only on dev data
> first. `retention_log` keeps proof of every run.

---

## Part 2c – Daily Report (n8n WF-02)

Every morning at 08:00 (UTC) the workflow posts a summary of **yesterday** to
Slack. It pings `@channel` **only when something looks wrong**; on a normal day
it posts quietly.

### The workflow, node by node

| Node | Type | What it does |
|---|---|---|
| Daily 08:00 | Schedule Trigger | starts the run |
| Yesterday Metrics | Postgres | one query: yesterday **and** the day before - turns, auto-send / human review / no-safe-reply counts, overrides, cost, p95 latency, avg reviewer score, plus the `DAILY_COST_WARN_USD` setting |
| Intent Mix | Postgres | turns per intent |
| Top Routing Reasons | Postgres | the 5 most common routing reasons |
| Build Report | Code (JavaScript) | calculates percentages and day-over-day change, writes the Slack text, applies the attention rules |
| Needs Attention? | IF | splits the flow on `severity` |
| Slack - Attention | HTTP Request | sends the report **with** `@channel` |
| Slack - Normal | HTTP Request | sends the report quietly |

### Attention rules (constants at the top of the *Build Report* node)

| Rule | Default |
|---|---|
| Share of turns with no safe reply | >= 10% |
| AI cost reached the daily warning level | `DAILY_COST_WARN_USD` from `system_settings` |
| Traffic fell vs the previous day | >= 50% (only if the previous day had >= 20 turns) |

### Design notes
- **No schema change.** It only reads `conversation_turn_audit` and `system_settings`.
- **Every query returns exactly one row** (aggregates / `json_agg`), so an empty
  day still produces a report, and no node runs more than once.
- Day boundaries are **UTC**.

### Try it end to end
```bash
./scripts/clear_demo_data.sh          # start clean (dev only)
./scripts/seed_demo_traffic.sh        # fake yesterday + day before, a normal day
```
1. n8n -> **Import from file** -> `workflows/WF-02_daily_report.json`.
2. In the three **Postgres** nodes select the **ShopAssist Postgres** credential.
3. Click **Execute workflow**. Open the **Build Report** node output to read the
   report text.
4. Without a Slack webhook the last node shows an error. That is expected; the
   report itself is already visible in step 3.

Now see the attention path:
```bash
./scripts/clear_demo_data.sh
./scripts/seed_demo_traffic.sh bad    # ~20% of turns with no safe reply
```
Execute again: the report ends with **Needs attention** and goes through
*Slack - Attention*.

Sample output (a bad day):
```
ShopAssist daily report - 2026-11-03
Conversations: 120 (up 20% vs previous day)
Auto-send: 62 (52%) | Human review: 27 (23%) | No safe reply: 31 (26%)
Human overrides: 4
AI cost: $8.06 (up 19%) | avg $0.0672 per turn
Latency p95: 11.4 s | Avg reviewer score: 0.88
Intents: escalation_request 25, ambiguous 22, off_topic 22, ...
Top routing reasons: all_drafts_rejected 31, safety_flag 8, ...

Needs attention
- 25.8% of turns had no safe reply (limit 10%)
```

When you are happy, toggle the workflow to **Active**, and run
`./scripts/clear_demo_data.sh` so fake rows never mix with real data.

---

## Part 3 – Push to GitHub

Create an **empty** repo on GitHub first (no README/.gitignore), then:

```bash
git init
git add .
git status                      # make sure .env is NOT listed
git commit -m "feat(db): audit schema, kill switch and WF-05 cost guard"
git branch -M main
git remote add origin https://github.com/<your-user>/<repo>.git
git push -u origin main

# SDD §15 uses main + develop, with PR review:
git checkout -b develop && git push -u origin develop
```
From now on: work on `feature/...` branches off `develop` and open a PR.

## Notes / decisions

- The day boundary for "daily cost" is **UTC**. Change it in `fn_daily_cost()` /
  `run_cost_guard()` if the team wants local time.
- Only the **daily** threshold is automated here. The **monthly** $200 limit
  from SDD §16 is a natural next addition (same pattern, `SUM` over the month).
- If Slack is down, the alert is lost (SDD §11 asks for a backup email). The
  kill switch itself still works because it happens in SQL, before the alert.
- n8n runs in single-process dev mode. Production uses queue mode (SDD §18) and
  an exact pinned n8n image version instead of `:latest`.

## Next features (same pattern)

1. `kb_gaps` table + weekly gap report (for the RAG owner)
2. Customer feedback column + webhook
3. Error-handler workflow: when any workflow fails, log it and alert (today a
   failed WF-05 / WF-06 / WF-02 run is only visible inside n8n)
