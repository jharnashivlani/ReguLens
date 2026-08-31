import json

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="ReguLens Compliance Dashboard",
    page_icon=":material/gavel:",
    layout="wide",
)


@st.cache_resource
def get_conn():
    # In Streamlit-in-Snowflake, the connection is always named "snowflake".
    return st.connection("snowflake")


def q(sql: str, params=None) -> pd.DataFrame:
    df = get_conn().query(sql, params=params)
    df.columns = df.columns.str.lower()
    return df


@st.cache_data(ttl=30)
def get_counts() -> dict:
    sql = """
    SELECT
      (SELECT COUNT(*) FROM REGULENS_DB.SIGNALS.ALERT) AS alerts,
      (SELECT COUNT(*) FROM REGULENS_DB.EVIDENCE.FINDING) AS findings,
      (SELECT COUNT(*) FROM REGULENS_DB.EVIDENCE.SAR_REPORT) AS sar_reports,
      (SELECT COUNT(*) FROM REGULENS_DB.RAW.POLICY_DOC_SECTION) AS policy_sections
    """
    r = q(sql)
    return {k: int(r.iloc[0][k]) for k in r.columns}


def run_demo() -> dict:
    # CALL returns a single VARIANT column; normalize to python dict.
    r = q("CALL REGULENS_DB.APP.SP_RUN_DEMO()")
    v = r.iloc[0][0]
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {"raw": v}
    try:
        return json.loads(json.dumps(v))
    except Exception:
        return {"raw": v}


def policy_search(query_text: str, limit: int = 5) -> pd.DataFrame:
    payload = json.dumps(
        {
            "query": query_text,
            "columns": ["DOC_ID", "SECTION_ID", "SECTION_NO", "HEADING"],
            "limit": int(limit),
        }
    )

    df = q(
        """
        WITH resp AS (
          SELECT PARSE_JSON(
            SNOWFLAKE.CORTEX.SEARCH_PREVIEW('REGULENS_DB.APP.POLICY_SEARCH_SERVICE', ?)
          ) AS j
        )
        SELECT
          value:DOC_ID::STRING AS doc_id,
          value:SECTION_ID::STRING AS section_id,
          value:SECTION_NO::STRING AS section_no,
          value:HEADING::STRING AS heading
        FROM resp, LATERAL FLATTEN(input => j:results)
        """,
        params=[payload],
    )

    return df


def agent_run(question: str) -> dict:
    """Run the ReguLens Cortex Agent via SQL.

    Uses SNOWFLAKE.CORTEX.DATA_AGENT_RUN with the v2 request shape.
    """
    request = json.dumps(
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": question,
                        }
                    ],
                }
            ]
        }
    )

    df = q(
        "SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?) AS RESPONSE",
        params=["REGULENS_DB.APP.REGULENS_AGENT", request],
    )
    raw = df.iloc[0]["response"] if not df.empty else None

    if raw is None:
        return {"error": "No response returned"}
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw}
    try:
        return json.loads(json.dumps(raw))
    except Exception:
        return {"raw": raw}


@st.cache_data(ttl=30)
def get_alert(alert_id: str):
    df = q(
        """
        SELECT ALERT_ID, ALERT_TS, ACCOUNT_ID, CUSTOMER_ID, ALERT_TYPE, SEVERITY, RISK_SCORE, SUMMARY, CONTEXT
        FROM REGULENS_DB.SIGNALS.ALERT
        WHERE ALERT_ID = ?
        """,
        params=[alert_id],
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


@st.cache_data(ttl=30)
def get_alert_reasons(alert_id: str) -> pd.DataFrame:
    return q(
        """
        WITH a AS (
          SELECT CONTEXT:reasons AS reasons
          FROM REGULENS_DB.SIGNALS.ALERT
          WHERE ALERT_ID = ?
        )
        SELECT
          f.key::STRING AS reason,
          f.value::STRING AS value
        FROM a, LATERAL FLATTEN(input => reasons) f
        ORDER BY reason
        """,
        params=[alert_id],
    )


@st.cache_data(ttl=30)
def get_alert_window_txns(alert_id: str, limit: int = 200) -> pd.DataFrame:
    return q(
        """
        WITH a AS (
          SELECT
            ALERT_ID,
            ALERT_TS,
            ACCOUNT_ID,
            COALESCE(CONTEXT:window_hours::NUMBER, 24) AS window_hours
          FROM REGULENS_DB.SIGNALS.ALERT
          WHERE ALERT_ID = ?
        )
        SELECT
          t.TXN_ID,
          t.TXN_TS,
          t.ACCOUNT_ID,
          t.CUSTOMER_ID,
          t.DIRECTION,
          t.AMOUNT,
          t.CURRENCY,
          t.CHANNEL,
          t.PAYMENT_TYPE,
          t.COUNTERPARTY_COUNTRY_CODE,
          t.COUNTERPARTY_RISK_TIER,
          t.PEP_FLAG,
          t.DESCRIPTION
        FROM a
        JOIN REGULENS_DB.CURATED.TXN_ENRICHED t
          ON t.ACCOUNT_ID = a.ACCOUNT_ID
         AND t.TXN_TS BETWEEN DATEADD('hour', -a.window_hours, a.ALERT_TS)
                        AND DATEADD('hour', 1, a.ALERT_TS)
        ORDER BY t.TXN_TS DESC
        LIMIT ?
        """,
        params=[alert_id, int(limit)],
    )


@st.cache_data(ttl=30)
def policy_sections_by_id(section_ids: list[str]) -> pd.DataFrame:
    if not section_ids:
        return pd.DataFrame(columns=["section_id", "doc_id", "section_no", "heading", "body_text"])

    placeholders = ",".join(["?"] * len(section_ids))
    sql = f"""
    SELECT
      SECTION_ID AS section_id,
      DOC_ID AS doc_id,
      SECTION_NO AS section_no,
      HEADING AS heading,
      BODY_TEXT AS body_text
    FROM REGULENS_DB.RAW.POLICY_DOC_SECTION
    WHERE SECTION_ID IN ({placeholders})
    """
    return q(sql, params=section_ids)


@st.cache_data(ttl=30)
def get_evidence_items_for_finding(finding_id: str) -> pd.DataFrame:
    return q(
        """
        SELECT EVIDENCE_ID, CREATED_AT, FINDING_ID, EVIDENCE_TYPE, OBJECT_REF, DESCRIPTION, CITATIONS
        FROM REGULENS_DB.EVIDENCE.EVIDENCE_ITEM
        WHERE FINDING_ID = ?
        ORDER BY CREATED_AT DESC
        """,
        params=[finding_id],
    )


st.markdown("# :material/gavel: ReguLens")
st.caption("Compliance review surface for synthetic AML/fraud signals with audit-ready evidence.")

counts = get_counts()
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
with col_kpi1:
    st.metric("Alerts", counts["alerts"])
with col_kpi2:
    st.metric("Findings", counts["findings"])
with col_kpi3:
    st.metric("SAR reports", counts["sar_reports"])
with col_kpi4:
    st.metric("Policy sections", counts["policy_sections"])

st.divider()

tab_alerts, tab_evidence, tab_policy, tab_copilot = st.tabs(
    ["Alerts", "Evidence", "Policy", "Copilot"]
)

with tab_alerts:
    top = st.columns([1, 1, 2])
    with top[0]:
        if st.button(":material/play_arrow: Run E2E demo", type="primary"):
            st.session_state["last_demo"] = run_demo()
    with top[1]:
        if st.button(":material/refresh: Refresh", type="tertiary"):
            st.cache_data.clear()
            st.rerun()
    with top[2]:
        last_demo = st.session_state.get("last_demo")
        if last_demo:
            st.code(json.dumps(last_demo, indent=2), language="json")

    df_alerts = q(
        """
        SELECT ALERT_ID, ALERT_TS, ACCOUNT_ID, CUSTOMER_ID, ALERT_TYPE, SEVERITY, RISK_SCORE, SUMMARY
        FROM REGULENS_DB.SIGNALS.ALERT
        ORDER BY ALERT_TS DESC
        LIMIT 200
        """
    )

    left, right = st.columns([2, 1])
    with left:
        st.dataframe(df_alerts, width="stretch", hide_index=True)
    with right:
        options = df_alerts["alert_id"].tolist() if not df_alerts.empty else []
        selected = st.selectbox("Alert", options=options)
        if selected:
            st.subheader("Create SAR")
            st.caption("Creates a Finding + SAR report for the selected alert.")
            if st.button(":material/post_add: Create finding + SAR", type="primary"):
                r = q(
                    "CALL REGULENS_DB.APP.SP_CREATE_SAR_FROM_ALERT(?)",
                    params=[selected],
                )
                st.session_state["last_sar_from_alert"] = r.iloc[0][0]
                st.success("Created.")
                st.cache_data.clear()
                st.rerun()

            last = st.session_state.get("last_sar_from_alert")
            if last is not None:
                st.code(json.dumps(last, indent=2), language="json")

            st.divider()
            st.subheader("Selected alert details")
            alert = get_alert(selected)
            if alert is None:
                st.info("Alert not found.")
            else:
                st.markdown(
                    f"**Severity:** `{alert.get('severity')}`  \n"
                    f"**Risk score:** `{alert.get('risk_score')}`  \n"
                    f"**Type:** `{alert.get('alert_type')}`  \n"
                    f"**Account / Customer:** `{alert.get('account_id')}` / `{alert.get('customer_id')}`"
                )
                st.text_area("Summary", value=alert.get("summary") or "", height=90)

                with st.expander("Context (JSON)", expanded=False):
                    st.json(alert.get("context"))

                st.caption("Risk reasons")
                df_reasons = get_alert_reasons(selected)
                st.dataframe(df_reasons, width="stretch", hide_index=True)

                st.caption("Transactions in alert window")
                df_txn = get_alert_window_txns(selected, limit=200)
                st.dataframe(df_txn, width="stretch", hide_index=True)

with tab_evidence:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Findings")
        df_findings = q(
            """
            SELECT FINDING_ID, CREATED_AT, ALERT_ID, ACCOUNT_ID, CUSTOMER_ID, STATUS, SEVERITY, TITLE
            FROM REGULENS_DB.EVIDENCE.FINDING
            ORDER BY CREATED_AT DESC
            LIMIT 100
            """
        )
        st.dataframe(df_findings, width="stretch", hide_index=True)
    with c2:
        st.subheader("SAR Reports")
        df_sar = q(
            """
            SELECT REPORT_ID, CREATED_AT, FINDING_ID, SUBJECT_ACCOUNT_ID, SUBJECT_CUSTOMER_ID, STATUS
            FROM REGULENS_DB.EVIDENCE.SAR_REPORT
            ORDER BY CREATED_AT DESC
            LIMIT 100
            """
        )
        st.dataframe(df_sar, width="stretch", hide_index=True)

    st.subheader("Latest SAR (detail)")
    df_latest = q(
        """
        SELECT REPORT_ID, CREATED_AT, FINDING_ID, SUBJECT_ACCOUNT_ID, SUBJECT_CUSTOMER_ID,
               PERIOD_START, PERIOD_END, STATUS, NARRATIVE, METRICS, POLICY_CITATIONS
        FROM REGULENS_DB.EVIDENCE.SAR_REPORT
        ORDER BY CREATED_AT DESC
        LIMIT 1
        """
    )
    if df_latest.empty:
        st.info("No SAR reports yet. Create one from Alerts.")
    else:
        row = df_latest.iloc[0].to_dict()
        st.markdown(f"**Report:** `{row['report_id']}`  ")
        st.markdown(f"**Subject:** `{row['subject_customer_id']}` / `{row['subject_account_id']}`  ")
        st.markdown(f"**Status:** `{row['status']}`")
        st.text_area("Narrative", value=row.get("narrative") or "", height=160)
        st.code(json.dumps(row.get("metrics"), indent=2), language="json")
        st.code(json.dumps(row.get("policy_citations"), indent=2), language="json")

        st.subheader("Evidence items")
        df_ev = get_evidence_items_for_finding(row.get("finding_id"))
        if df_ev.empty:
            st.info("No evidence items linked to this finding yet.")
        else:
            st.dataframe(df_ev, width="stretch", hide_index=True)

            st.caption("Evidence drill-through")
            ev_ids = df_ev["evidence_id"].tolist()
            selected_ev = st.selectbox("Evidence item", options=ev_ids)
            if selected_ev:
                ev = df_ev[df_ev["evidence_id"] == selected_ev].iloc[0].to_dict()
                st.markdown(
                    f"**Type:** `{ev.get('evidence_type')}`  \n"
                    f"**Object ref:** `{ev.get('object_ref')}`"
                )
                st.write(ev.get("description") or "")
                with st.expander("Citations (JSON)", expanded=False):
                    st.json(ev.get("citations"))

                if ev.get("evidence_type") == "TXN" and ev.get("object_ref"):
                    df_tx = q(
                        """
                        SELECT *
                        FROM REGULENS_DB.CURATED.TXN_ENRICHED
                        WHERE TXN_ID = ?
                        """,
                        params=[ev.get("object_ref")],
                    )
                    st.dataframe(df_tx, width="stretch", hide_index=True)

                if ev.get("evidence_type") == "POLICY" and ev.get("object_ref"):
                    df_pol = policy_sections_by_id([ev.get("object_ref")])
                    if not df_pol.empty:
                        pol = df_pol.iloc[0].to_dict()
                        st.markdown(
                            f"**{pol.get('doc_id')} \u00a7{pol.get('section_no')} ({pol.get('section_id')})**"
                        )
                        st.caption(pol.get("heading") or "")
                        st.write(pol.get("body_text") or "")

with tab_policy:
    st.subheader("Policy Search")
    qtext = st.text_input(
        "Query",
        value="suspicious activity reporting narrative requirements",
    )
    limit = st.slider("Limit", min_value=1, max_value=10, value=5)
    if st.button(":material/search: Search", type="primary"):
        try:
            st.session_state["policy_results"] = policy_search(qtext, limit=limit)
            st.session_state.pop("policy_error", None)
        except Exception as e:
            st.session_state["policy_results"] = pd.DataFrame()
            st.session_state["policy_error"] = str(e)

    err = st.session_state.get("policy_error")
    if err:
        st.error(err)

    res = st.session_state.get("policy_results")
    if res is None:
        st.info("Enter a query and click Search.")
        res = pd.DataFrame(columns=["doc_id", "section_id", "section_no", "heading"])

    st.dataframe(res, width="stretch", hide_index=True)

    section_ids = []
    if not res.empty and "section_id" in res.columns:
        section_ids = [s for s in res["section_id"].dropna().astype(str).tolist() if s]
    sections = policy_sections_by_id(section_ids)
    if sections.empty:
        st.info("No section text available for these results.")
    else:
        by_id = {r["section_id"]: r for r in sections.to_dict(orient="records")}
        for r in res.to_dict(orient="records"):
            sid = r.get("section_id")
            sec = by_id.get(sid)
            if not sec:
                continue
            label = f"{sec.get('doc_id')} \u00a7{sec.get('section_no')} ({sid})"
            heading = sec.get("heading") or r.get("heading") or ""
            body = sec.get("body_text") or ""
            snippet = (body[:600] + "...") if len(body) > 600 else body
            st.markdown(f"**{label}**  ")
            if heading:
                st.caption(heading)
            st.write(snippet)
            with st.expander("Full section", expanded=False):
                st.write(body)


with tab_copilot:
    st.subheader("Copilot")
    st.caption("Ask questions about alerts, SARs, evidence, and related policy sections.")

    if st.button(":material/refresh: Clear chat", type="tertiary"):
        st.session_state.pop("copilot_messages", None)
        st.rerun()

    messages = st.session_state.get("copilot_messages")
    if messages is None:
        messages = []
        st.session_state["copilot_messages"] = messages

    for m in messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    prompt = st.chat_input("Ask ReguLens Copilot")
    if prompt:
        messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                resp = agent_run(prompt)

            text_out = None
            try:
                content = resp.get("content") or []
                parts = [p.get("text") for p in content if p.get("type") == "text" and p.get("text")]
                text_out = "\n\n".join(parts) if parts else None
            except Exception:
                text_out = None

            if not text_out:
                text_out = json.dumps(resp, indent=2)

            st.markdown(text_out)
            with st.expander("Response (raw JSON)", expanded=False):
                st.json(resp)

        messages.append({"role": "assistant", "content": text_out})
