# ReguLens Demo Runbook (Validation + Tests)

This file is a repeatable validation script and a demo flow for the Snowflake-native hackathon build.

Assumptions:
- Role: `ACCOUNTADMIN` (or equivalent privileges)
- Warehouse: `COMPUTE_WH`
- Database: `REGULENS_DB`

## Hackathon Scoring Map (What To Point At)

Use this section as the judge-facing checklist. Each item maps to concrete objects and repeatable commands.

Native-first implementation:
- Pipelines: Streams/Tasks/Procedures in `REGULENS_DB.APP` drive near-real-time scoring and evidence generation.
- Semantic layer: `REGULENS_DB.SEMANTIC.REGULENS_SV` with verified queries (VQRs).
- Retrieval: `REGULENS_DB.APP.POLICY_SEARCH_SERVICE` (Cortex Search Service).
- UX surface: Streamlit app `REGULENS_DB.APP.REGULENS_DASHBOARD` + Copilot tab.

Determinism + governance:
- Ask a VQR question and show `verified_query_used: true` in the agent trace:
  - “How many SAR reports were created today?” (see `## 1.5`)
- Role/warehouse are explicit (`ACCOUNTADMIN`, `COMPUTE_WH`) and all data access stays in Snowflake.

Real actions (not only chat):
- The agent includes custom tools backed by stored procedures (requires explicit confirmation):
  - `run_demo` -> `APP.SP_RUN_DEMO()`
  - `create_finding_from_alert` -> `APP.SP_CREATE_FINDING_FROM_ALERT(P_ALERT_ID)`
  - `create_sar_from_alert` -> `APP.SP_CREATE_SAR_FROM_ALERT(P_ALERT_ID)`
  - Smoke tests in `## 1.6`

Reusable + shareable assets:
- CoCo project skill: `.snowflake/cortex/skills/regulens-ops/` (invoke `regulens-ops`).
- This is publishable to a Snowflake stage or Skills Catalog from CoCo Desktop.

MCP / cross-surface story:
- Snowflake-managed MCP server exists and exposes the governed agent:
  - `REGULENS_DB.APP.REGULENS_MCP_SERVER` (see `## 1.8`)

Guardrails + graceful fallback:
- Agent instruction strings explicitly prohibit hallucinations and require confirmation before actions.
- If a required ID is missing (e.g., alert_id), the agent should query first and ask the user to choose.

## 0) Session Setup

```sql
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE REGULENS_DB;
```

## 1) Smoke Checks (Objects Exist)

```sql
SHOW SCHEMAS IN DATABASE REGULENS_DB;

SHOW TABLES IN SCHEMA REGULENS_DB.RAW;
SHOW VIEWS  IN SCHEMA REGULENS_DB.CURATED;
SHOW TABLES IN SCHEMA REGULENS_DB.SIGNALS;
SHOW VIEWS  IN SCHEMA REGULENS_DB.SIGNALS;
SHOW TABLES IN SCHEMA REGULENS_DB.EVIDENCE;

SHOW STREAMS IN SCHEMA REGULENS_DB.RAW;
SHOW TASKS   IN SCHEMA REGULENS_DB.APP;
SHOW PROCEDURES IN SCHEMA REGULENS_DB.APP;

SHOW CORTEX SEARCH SERVICES IN SCHEMA REGULENS_DB.APP;
SHOW SEMANTIC VIEWS         IN SCHEMA REGULENS_DB.SEMANTIC;
SHOW AGENTS                 IN SCHEMA REGULENS_DB.APP;
SHOW STREAMLITS             IN SCHEMA REGULENS_DB.APP;
```

Expected:
- `RAW.TRANSACTION_STREAM`
- `APP.TSK_UPDATE_FEATURES` started
- `APP.TSK_SCORE_AND_ALERT_SCHED` started
- `APP.POLICY_SEARCH_SERVICE` ACTIVE
- `SEMANTIC.REGULENS_SV`
- `APP.REGULENS_AGENT`
- `APP.REGULENS_DASHBOARD`

## 1.5) Copilot (Cortex Agent) Smoke Test

Note: `cortex agents run` can be flaky in some trial environments (it may print `No models available`).
The authoritative smoke test is the SQL invocation below.

Agent prompt guidance: The ReguLens agent instruction strings were aligned to Snowflake guidance on planning and response instructions (tool routing, grounding, and explicit non-hallucination rules). Reference: https://www.snowflake.com/en/developers/guides/best-practices-to-building-cortex-agents/

```sql
SELECT
  SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'REGULENS_DB.APP.REGULENS_AGENT',
    '{"messages":[{"role":"user","content":[{"type":"text","text":"How many SAR reports were created today?"}]}]}'
  ) AS agent_response;
```

Expected:
- JSON response with a `content` array that includes an assistant text answer.

## 1.6) Copilot Actions (Custom Tools)

The agent includes custom action tools (stored procedures) so it can take real actions, not only return text.
All action tools require explicit confirmation in the prompt.

Recommended prompts:
- "Run the end-to-end demo pipeline. I confirm you may proceed."
- "Create a finding from alert_id <ALERT_ID>. I confirm you may proceed."
- "Create a SAR from alert_id <ALERT_ID>. I confirm you may proceed."

Authoritative SQL smoke tests:

```sql
-- Pick a recent alert ID
SELECT ALERT_ID
FROM REGULENS_DB.SIGNALS.ALERT
ORDER BY CREATED_AT DESC
LIMIT 1;

-- Run end-to-end action through the agent
SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'REGULENS_DB.APP.REGULENS_AGENT',
  '{"messages":[{"role":"user","content":[{"type":"text","text":"Please run the end-to-end demo pipeline now. I confirm you may proceed."}]}]}'
) AS agent_response;

-- Create finding from a specific alert_id
SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'REGULENS_DB.APP.REGULENS_AGENT',
  '{"messages":[{"role":"user","content":[{"type":"text","text":"Create a finding from alert_id AL19930907. I confirm you may proceed."}]}]}'
) AS agent_response;

-- Create SAR package from a specific alert_id
SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'REGULENS_DB.APP.REGULENS_AGENT',
  '{"messages":[{"role":"user","content":[{"type":"text","text":"Create a SAR from alert_id AL19930907. I confirm you may proceed."}]}]}'
) AS agent_response;
```

Expected:
- Agent invokes `run_demo` / `create_finding_from_alert` / `create_sar_from_alert` and returns the created IDs.

## 1.7) CoCo Skill Demo (Reusable)

This repo includes a reusable CoCo project skill at `.snowflake/cortex/skills/regulens-ops/`.
In CoCo Desktop or CLI, invoke the skill by name:
- `regulens-ops`

The skill walks through object checks, runs `SP_RUN_DEMO`, and runs the agent smoke tests.

## 1.8) MCP Demo (Snowflake-managed MCP Server)

This demo also includes a Snowflake-managed MCP server exposing the agent as a single governed MCP tool:
- MCP server: `REGULENS_DB.APP.REGULENS_MCP_SERVER`

```sql
SHOW MCP SERVERS IN SCHEMA REGULENS_DB.APP;
DESCRIBE MCP SERVER REGULENS_DB.APP.REGULENS_MCP_SERVER;
```

To connect from an MCP client, use the MCP server URL format from Snowflake docs:
`https://<account_url>/api/v2/databases/REGULENS_DB/schemas/APP/mcp-servers/REGULENS_MCP_SERVER`

For hackathon demos, it is usually sufficient to show the MCP server object exists, describe its spec, and explain that external MCP clients can call `regulens_copilot` to reach the governed agent.

## 2) Data Integrity Checks (Row Counts + Non-Null Keys)

```sql
SELECT
  (SELECT COUNT(*) FROM RAW.CUSTOMER)      AS customers,
  (SELECT COUNT(*) FROM RAW.ACCOUNT)       AS accounts,
  (SELECT COUNT(*) FROM RAW.COUNTERPARTY)  AS counterparties,
  (SELECT COUNT(*) FROM RAW.TRANSACTION)   AS transactions,
  (SELECT COUNT(*) FROM SIGNALS.ALERT)     AS alerts,
  (SELECT COUNT(*) FROM EVIDENCE.FINDING)  AS findings,
  (SELECT COUNT(*) FROM EVIDENCE.SAR_REPORT) AS sar_reports;

SELECT
  COUNT_IF(CUSTOMER_ID IS NULL) AS null_customer_id,
  COUNT(*) AS total
FROM RAW.CUSTOMER;

SELECT
  COUNT_IF(ACCOUNT_ID IS NULL OR CUSTOMER_ID IS NULL) AS null_keys,
  COUNT(*) AS total
FROM RAW.ACCOUNT;

SELECT
  COUNT_IF(TXN_ID IS NULL OR ACCOUNT_ID IS NULL OR CUSTOMER_ID IS NULL) AS null_keys,
  COUNT(*) AS total
FROM CURATED.TXN_ENRICHED;
```

Expected:
- non-zero row counts, and `null_* = 0`.

## 3) Pipeline Health (Tasks + Stream)

```sql
SHOW TASKS IN SCHEMA REGULENS_DB.APP;

SELECT *
FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY(
  SCHEDULED_TIME_RANGE_START=>DATEADD('hour', -1, CURRENT_TIMESTAMP()),
  SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP(),
  RESULT_LIMIT=>100
))
WHERE DATABASE_NAME='REGULENS_DB'
  AND SCHEMA_NAME='APP'
  AND NAME IN ('TSK_UPDATE_FEATURES','TSK_SCORE_AND_ALERT_SCHED')
ORDER BY SCHEDULED_TIME DESC;
```

Expected:
- Recent `SUCCEEDED` rows for `TSK_SCORE_AND_ALERT_SCHED`.
- `TSK_UPDATE_FEATURES` runs when stream has data (may show fewer executions if no recent inserts).

## 4) Signal/Alert Checks (Deterministic)

```sql
SELECT
  MIN(RISK_SCORE) AS min_score,
  AVG(RISK_SCORE) AS avg_score,
  MAX(RISK_SCORE) AS max_score,
  COUNT(*) AS alert_cnt
FROM SIGNALS.ALERT;

SELECT SEVERITY, COUNT(*) AS cnt
FROM SIGNALS.ALERT
GROUP BY SEVERITY
ORDER BY cnt DESC;

SELECT *
FROM SIGNALS.ACCOUNT_RISK_LATEST
ORDER BY RISK_SCORE DESC NULLS LAST
LIMIT 10;
```

## 5) Evidence Flow Test (Alert -> Finding -> SAR)

Use the single-call demo procedure (avoids session variable friction).

```sql
CALL APP.SP_RUN_DEMO();

-- Inspect the latest run and IDs produced.
SELECT RUN_TS, SCORE_TS, ALERT_ID, FINDING_ID, REPORT_ID, RESULT
FROM APP.DEMO_RUN_LOG
ORDER BY RUN_TS DESC
LIMIT 1;

-- Validate the evidence rows exist.
WITH last_run AS (
  SELECT * FROM APP.DEMO_RUN_LOG ORDER BY RUN_TS DESC LIMIT 1
)
SELECT
  (SELECT COUNT(*) FROM EVIDENCE.FINDING f JOIN last_run r ON r.FINDING_ID = f.FINDING_ID) AS finding_row_cnt,
  (SELECT COUNT(*) FROM EVIDENCE.SAR_REPORT s JOIN last_run r ON r.REPORT_ID = s.REPORT_ID) AS sar_row_cnt,
  (SELECT r.RESULT:status::string FROM last_run r) AS demo_status;
```

Expected:
- `demo_status = 'OK'`
- `finding_row_cnt = 1` and `sar_row_cnt = 1`

## 6) Policy Retrieval Sanity (Cortex Search)

```sql
SELECT
  PARSE_JSON(
    SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
      'REGULENS_DB.APP.POLICY_SEARCH_SERVICE',
      '{
        "query": "suspicious activity report filing requirements",
        "columns": ["DOC_ID","DOC_TYPE","TITLE","SECTION_ID","HEADING","CITATION_LABEL"],
        "limit": 5
      }'
    )
  )['results'] AS results;

-- Optional: flatten to a readable table
WITH resp AS (
  SELECT PARSE_JSON(
    SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
      'REGULENS_DB.APP.POLICY_SEARCH_SERVICE',
      '{
        "query": "suspicious activity report filing requirements",
        "columns": ["DOC_ID","DOC_TYPE","TITLE","SECTION_ID","HEADING","CITATION_LABEL"],
        "limit": 5
      }'
    )
  ) AS j
)
SELECT
  value:DOC_ID::string AS doc_id,
  value:SECTION_ID::string AS section_id,
  value:TITLE::string AS title,
  value:HEADING::string AS heading,
  value:CITATION_LABEL::string AS citation_label
FROM resp, LATERAL FLATTEN(input => j:results)
ORDER BY doc_id, section_id;
```

Expected:
- 1+ results with `DOC_ID`, `SECTION_ID`, and snippet/relevance info.

## 7) Semantic View / NLQ Determinism (VQR Spot Checks)

Note: Semantic Views may not be enabled in all accounts. If `SHOW SEMANTIC VIEWS` returns empty,
skip this section.

Recommended spot-check queries (direct SQL; should align with VQR intent):

```sql
-- Alert count by status
SELECT SEVERITY, COUNT(*) AS alert_count
FROM SIGNALS.ALERT
GROUP BY SEVERITY
ORDER BY alert_count DESC;

-- Top accounts by suspicious score
SELECT account_id, risk_score
FROM SIGNALS.ACCOUNT_RISK_LATEST
ORDER BY risk_score DESC NULLS LAST
LIMIT 10;
```

## 7.5) Agent + Semantic View Check

```sql
SELECT
  SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'REGULENS_DB.APP.REGULENS_AGENT',
    '{"messages":[{"role":"user","content":[{"type":"text","text":"How many SAR reports were created today?"}]}]}'
  ) AS agent_response;
```

Expected:
- JSON response includes an assistant answer and a `tool_result` entry showing executed SQL.

## 8) Demo Script (5–7 minutes)

### 60–90 second judge pitch (read aloud)

ReguLens is a Snowflake-native AML/fraud investigation copilot. We start with near-real-time data pipelines in Snowflake (streams, tasks, and procedures) that score transactions and produce alerts and evidence objects. On top of that, we built a governed semantic layer (`REGULENS_SV`) with verified queries, so common questions resolve deterministically, and a policy search index (`POLICY_SEARCH_SERVICE`) so the copilot can cite the exact policy section it’s using.

The key difference from a chat demo is that the copilot takes real action safely: the agent can create a finding or generate a SAR package by calling Snowflake stored procedures, but only after explicit user confirmation. You can see both the SQL it ran and whether a verified query was used in the agent trace.

Finally, we ship this across surfaces: Streamlit-in-Snowflake for the investigator UI, a reusable CoCo skill (`regulens-ops`) for repeatable operations, and an MCP server (`REGULENS_MCP_SERVER`) that exposes the governed agent to external MCP clients.

### 60-second proof moments (do immediately after the pitch)

**A) Deterministic answer via Semantic View + VQR**

Prompt (Copilot):
> How many SAR reports were created today?

Proof (SQL):
```sql
SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'REGULENS_DB.APP.REGULENS_AGENT',
  '{"messages":[{"role":"user","content":[{"type":"text","text":"How many SAR reports were created today?"}]}]}'
) AS agent_response;
```

Look for: `verified_query_used: true` (or equivalent) + executed SQL in tool trace.

**B) Real action (custom tool) with explicit confirmation**

Prompt (Copilot):
> Create a finding for alert ALERT_12345. I confirm you may proceed.

Look for: a tool call to `create_finding_from_alert` (procedure-backed) and a returned finding identifier.

**C) Policy citation retrieval (Cortex Search)**

Prompt (Copilot):
> Which policy section supports filing a SAR for structuring-like behavior? Cite the section.

Look for: a search result snippet that includes a policy section reference.

1) Open Streamlit: `REGULENS_DB.APP.REGULENS_DASHBOARD`
2) Show live-ish operational cadence: `SHOW TASKS` + task history for `TSK_SCORE_AND_ALERT_SCHED`.
3) Show Alerts table with top open alerts.
4) Drill into one alert:
   - show account risk score (`SIGNALS.ACCOUNT_RISK_LATEST`)
   - show transactions evidence (`CURATED.TXN_ENRICHED` filtered by account)
5) Create Finding: call `APP.SP_CREATE_FINDING_FROM_ALERT`.
6) Generate SAR: call `APP.SP_GENERATE_SAR_REPORT`.
7) Show policy citation retrieval via `APP.POLICY_SEARCH_SERVICE`.
8) Optional: ask ReguLens Agent a governed question that maps to semantic view concepts (alerts by status, top suspicious accounts).
