# ReguLens Compliance Dashboard (Streamlit)

This is a Snowflake-connected Streamlit app that surfaces:
- alerts (`REGULENS_DB.SIGNALS.ALERT`)
- evidence (`REGULENS_DB.EVIDENCE.FINDING`, `REGULENS_DB.EVIDENCE.SAR_REPORT`)
- policy citations (Cortex Search over `REGULENS_DB.RAW.POLICY_DOC_SECTION` via `REGULENS_DB.APP.POLICY_SEARCH_SERVICE`)

## Deploy

This repo includes a `snowflake.yml` suitable for `snow streamlit deploy`.

Notes:
- The Snowflake container runtime requires a `compute_pool`.
- Keep `requirements.txt` present (it can be empty). The runtime will fail to boot if no dependency manifest is present.
- Trial accounts typically cannot create External Access Integrations, so avoid depending on PyPI installs.

## Local run (optional)

This app is primarily meant for Streamlit-in-Snowflake.

If you run it locally, you need:
- Python + Streamlit installed locally
- `.streamlit/secrets.toml` with a Snowflake connection named `snowflake`

