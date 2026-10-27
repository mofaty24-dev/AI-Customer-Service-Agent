# ShopAssist AI – Database & Automation (DB/Automation Lead)

First deliverable of the data layer for **ShopAssist AI** (SDD-001 v1.0).
It contains the audit schema, the kill switch, and **WF-05 Cost Guard**, an n8n
workflow that watches daily AI spend and shuts automation down automatically.

| Piece | SDD reference |
|---|---|
| `conversation_turn_audit` table (immutable, idempotent) | §9.2, §11 |
| `system_settings` – `AUTOMATION_ENABLED` kill switch | §6.2 step 2, §15 |
| `run_cost_guard()` + n8n workflow **WF-05** | §16 (daily cost > $12 / $200 per month) |
| pgvector extension enabled (for RAG later) | §4.3 |

## Repo layout

```
.
├── docker-compose.yml            # PostgreSQL 16 + pgvector, and n8n (dev)
├── .env.example                  # copy to .env (never commit .env)
├── db/
│   ├── migrations/               # 001..003, applied in order, once each
│   └── tests/cost_guard_test.sql # self-cleaning SQL tests (7 checks)
├── workflows/WF-05_cost_guard.json   # import into n8n
└── scripts/
    ├── migrate.sh                # apply pending migrations
    ├── test.sh                   # run SQL tests
    ├── simulate_spend.sh         # fake spend, to demo the guard
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
2. Retention job – delete audit rows older than 12 months
3. WF-02 Daily Report v2 (intent mix, auto-send rate, override rate)
4. Customer feedback column + webhook
