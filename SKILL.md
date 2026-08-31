---
name: regulens-ops
description: ReguLens operational runbook skill: verify objects, run the demo pipeline, and run agent smoke tests (DATA_AGENT_RUN) for hackathon demos.
---

# ReguLens ops

Use this skill when the user wants a repeatable, hackathon-friendly operational flow for the ReguLens demo.

## Workflow

1) Confirm Snowflake context.
- Use role `ACCOUNTADMIN`.
- Use warehouse `COMPUTE_WH`.
- Use database `REGULENS_DB`.

2) Smoke-check objects exist.
- `SHOW TASKS IN SCHEMA REGULENS_DB.APP;`
- `SHOW CORTEX SEARCH SERVICES IN SCHEMA REGULENS_DB.APP;`
- `SHOW SEMANTIC VIEWS IN SCHEMA REGULENS_DB.SEMANTIC;`
- `SHOW AGENTS IN SCHEMA REGULENS_DB.APP;`
- `SHOW MCP SERVERS IN SCHEMA REGULENS_DB.APP;` (optional)

3) Run the end-to-end demo pipeline.
- Prefer `CALL REGULENS_DB.APP.SP_RUN_DEMO();`
- Report the returned `alert_id`, `finding_id`, and `report_id`.

4) Run agent smoke tests via SQL (authoritative path).
- Validate the agent can answer a verified query:

```sql
SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'REGULENS_DB.APP.REGULENS_AGENT',
  '{"messages":[{"role":"user","content":[{"type":"text","text":"How many SAR reports were created today?"}]}]}'
) AS agent_response;
```

- Validate the agent can execute an action tool (only if the user confirms):

```sql
SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
  'REGULENS_DB.APP.REGULENS_AGENT',
  '{"messages":[{"role":"user","content":[{"type":"text","text":"Please run the end-to-end demo pipeline now. I confirm you may proceed."}]}]}'
) AS agent_response;
```

5) Summarize results.
- Provide a single markdown summary including:
  - whether tasks/search service/semantic view/agent exist
  - latest IDs created by `SP_RUN_DEMO`
  - agent smoke test status

## Publishing (shareable skill)

This is a project skill located under `.snowflake/cortex/skills/`.
To share it with teammates:
- Publish to a Snowflake stage from CoCo Desktop (Agent Settings -> Skills -> select `regulens-ops` -> Publish to stage).
- Or publish to the Skills Catalog (Agent Settings -> Skills -> select `regulens-ops` -> Publish to Skills Catalog) and share the returned `snow://skill_catalog/...` URI.
