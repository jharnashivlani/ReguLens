-- ReguLens demo: signal -> evidence -> audit-ready report
--
-- Run in Snowsight Worksheet, or via CLI (see run-regulens-demo.ps1).
--
-- Judge-facing checklist:
-- - Pipelines (native): tasks/streams/procs in REGULENS_DB.APP
-- - Semantic view + VQRs: REGULENS_DB.SEMANTIC.REGULENS_SV (ask a VQR question; see DATA_AGENT_RUN output)
-- - Retrieval: REGULENS_DB.APP.POLICY_SEARCH_SERVICE
-- - Agent (governed): REGULENS_DB.APP.REGULENS_AGENT (DATA_AGENT_RUN)
-- - Actions (custom tools): agent can run SP_RUN_DEMO / create finding / create SAR with confirmation
-- - MCP: REGULENS_DB.APP.REGULENS_MCP_SERVER exposes the agent as an MCP tool

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE REGULENS_DB;

-- 1) Run the end-to-end orchestration.
CALL REGULENS_DB.APP.SP_RUN_DEMO();

-- 2) Inspect latest run log and the evidence objects it created.
SELECT RUN_TS, SCORE_TS, ALERT_ID, FINDING_ID, REPORT_ID, RESULT:status::STRING AS STATUS
FROM REGULENS_DB.APP.DEMO_RUN_LOG
ORDER BY RUN_TS DESC
LIMIT 1;

SELECT ALERT_ID, ALERT_TS, ACCOUNT_ID, CUSTOMER_ID, SEVERITY, RISK_SCORE, SUMMARY
FROM REGULENS_DB.SIGNALS.ALERT
ORDER BY CREATED_AT DESC
LIMIT 5;

SELECT FINDING_ID, CREATED_AT, ALERT_ID, ACCOUNT_ID, CUSTOMER_ID, STATUS, SEVERITY, TITLE
FROM REGULENS_DB.EVIDENCE.FINDING
ORDER BY CREATED_AT DESC
LIMIT 5;

SELECT REPORT_ID, CREATED_AT, FINDING_ID, SUBJECT_ACCOUNT_ID, SUBJECT_CUSTOMER_ID, STATUS,
       METRICS, POLICY_CITATIONS
FROM REGULENS_DB.EVIDENCE.SAR_REPORT
ORDER BY CREATED_AT DESC
LIMIT 3;

-- 3) Policy retrieval sanity (Cortex Search).
WITH resp AS (
  SELECT PARSE_JSON(
    SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
      'REGULENS_DB.APP.POLICY_SEARCH_SERVICE',
      '{
        "query": "suspicious activity report narrative requirements",
        "columns": ["DOC_ID","SECTION_ID","SECTION_NO","HEADING"],
        "limit": 5
      }'
    )
  ) AS j
)
SELECT
  value:DOC_ID::STRING AS doc_id,
  value:SECTION_ID::STRING AS section_id,
  value:SECTION_NO::STRING AS section_no,
  value:HEADING::STRING AS heading
FROM resp, LATERAL FLATTEN(input => j:results);

-- 4) Quick health snapshot.
SHOW TASKS IN SCHEMA REGULENS_DB.APP;
SHOW CORTEX SEARCH SERVICES IN SCHEMA REGULENS_DB.APP;
SHOW SEMANTIC VIEWS IN SCHEMA REGULENS_DB.SEMANTIC;
SHOW AGENTS IN SCHEMA REGULENS_DB.APP;
SHOW MCP SERVERS IN SCHEMA REGULENS_DB.APP;

-- 5) Copilot (Cortex Agent) smoke test (SQL invocation is most reliable).
SELECT
  SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'REGULENS_DB.APP.REGULENS_AGENT',
    '{"messages":[{"role":"user","content":[{"type":"text","text":"How many SAR reports were created today?"}]}]}'
  ) AS agent_response;

-- 5b) Proof moments (determinism + action + citation).
-- A) Deterministic/VQR: look for verified_query_used:true in the agent response.
-- B) Action: requires explicit confirmation.
-- C) Citation: policy retrieval in the answer (or use SEARCH_PREVIEW above).
SELECT
  SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'REGULENS_DB.APP.REGULENS_AGENT',
    '{"messages":[{"role":"user","content":[{"type":"text","text":"Create a finding for alert ALERT_12345. I confirm you may proceed."}]}]}'
  ) AS agent_response;

SELECT
  SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'REGULENS_DB.APP.REGULENS_AGENT',
    '{"messages":[{"role":"user","content":[{"type":"text","text":"Which policy section supports filing a SAR for structuring-like behavior? Cite the section."}]}]}'
  ) AS agent_response;

-- 6) Copilot actions (custom tools) smoke test.
-- NOTE: The agent requires explicit confirmation phrasing.
SELECT
  SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'REGULENS_DB.APP.REGULENS_AGENT',
    '{"messages":[{"role":"user","content":[{"type":"text","text":"Please run the end-to-end demo pipeline now. I confirm you may proceed."}]}]}'
  ) AS agent_response;

SELECT 'ALERT' AS OBJ, COUNT(*) AS N FROM REGULENS_DB.SIGNALS.ALERT
UNION ALL SELECT 'FINDING', COUNT(*) FROM REGULENS_DB.EVIDENCE.FINDING
UNION ALL SELECT 'SAR_REPORT', COUNT(*) FROM REGULENS_DB.EVIDENCE.SAR_REPORT
UNION ALL SELECT 'ACCOUNT_RISK_SCORES', COUNT(*) FROM REGULENS_DB.SIGNALS.ACCOUNT_RISK_SCORES;
