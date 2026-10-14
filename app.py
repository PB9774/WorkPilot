from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st

import workpilot_core as core


st.set_page_config(page_title="WorkPilot AI", page_icon="W", layout="wide")
st.title("WorkPilot AI")
st.caption("Bounded company-data operator · local SQLite state · tool calls and outcomes are recorded")

try:
    catalog = core.initialize(Path(os.getenv("WORKPILOT_DATA_DIR", core.DEFAULT_DATA)))
except Exception as exc:
    st.error(f"Initialization failed: {exc}")
    st.stop()

with st.sidebar:
    st.subheader("Runtime")
    st.metric("Datasets", len(catalog))
    st.metric("Structured rows", sum(catalog.values()))
    st.caption(f"Groq model: {os.getenv('WORKPILOT_MODEL', 'openai/gpt-oss-20b')}")
    if not core.get_groq_api_key():
        st.warning("Task planning needs GROQ_API_KEY. Dataset import, inspection, and tests work offline.")

tasks_tab, data_tab, history_tab = st.tabs(["Tasks", "Data", "History"])

with tasks_tab:
    st.subheader("New task")
    with st.form("new_task", clear_on_submit=True):
        request = st.text_area("Business objective", height=100, placeholder="Find invoices for a vendor and compare their statuses with the finance sandbox.")
        submitted = st.form_submit_button("Run task", type="primary", disabled=not core.get_groq_api_key())
    if submitted and request.strip():
        task_id = core.create_task(request.strip())
        core.run_task(task_id)
        st.session_state["active_task_id"] = task_id
        st.rerun()

    approvals = core.pending_approvals()
    if approvals:
        st.subheader("Pending approval")
        for approval in approvals:
            args = json.loads(approval["arguments_json"])
            with st.container(border=True):
                st.write(f"**Action:** {args.get('action', approval['tool_name'])} · **Target:** {args.get('target', 'not specified')}")
                st.write(f"**Parameters:** `{json.dumps(args.get('parameters', {}), ensure_ascii=False)}`")
                st.write(f"**Expected effect:** {args.get('expected_effect', '')}")
                st.write(f"**Reason:** {args.get('reason', '')}")
                approve_col, reject_col = st.columns(2)
                if approve_col.button("Approve exact action", key=f"approve_{approval['approval_id']}"):
                    core.decide_approval(approval["approval_id"], True)
                    st.session_state["resume_task_id"] = approval["task_id"]
                    st.rerun()
                if reject_col.button("Reject", key=f"reject_{approval['approval_id']}"):
                    core.decide_approval(approval["approval_id"], False)
                    st.rerun()

    resume_id = st.session_state.pop("resume_task_id", None)
    if resume_id:
        core.run_task(resume_id)
        st.session_state["active_task_id"] = resume_id
        st.rerun()

    active_id = st.session_state.get("active_task_id")
    if active_id:
        active = next((task for task in core.list_tasks() if task["task_id"] == active_id), None)
        if active:
            st.subheader("Execution")
            st.write(f"**Status:** `{active['status']}`  ·  **Task:** `{active_id}`")
            if active["summary"]:
                st.markdown(active["summary"])
            for step in core.task_steps(active_id):
                with st.expander(f"{step['step_number']}. {step['tool_name']} · {step['status']}"):
                    st.write("Arguments")
                    st.json(step["arguments"])
                    st.write("Observed result")
                    st.json(step["result"])

with data_tab:
    st.subheader("Import source files")
    st.caption("The bundled Meridian Forge records are synthetic evaluation data. Imported files retain their source filename; no records are fabricated.")
    uploads = st.file_uploader("CSV, JSON, PDF, TXT, or Markdown", type=["csv", "json", "pdf", "txt", "md"], accept_multiple_files=True)
    if st.button("Import selected files", disabled=not uploads):
        for upload in uploads or []:
            outcome = core.import_upload(upload.name, upload.getvalue())
            if outcome.get("ok"):
                st.success(json.dumps(outcome, ensure_ascii=False))
            else:
                st.error(f"{upload.name}: {outcome['error']}")
    st.subheader("Dataset catalog")
    datasets = core.available_datasets()
    for dataset in datasets:
        with st.expander(f"{dataset['source_name']} · {dataset['row_count']} rows"):
            st.write(f"SQLite table: `{dataset['table_name']}`")
            st.dataframe(core.inspect_dataset(dataset["table_name"])["fields"], use_container_width=True, hide_index=True)
            st.caption(f"Imported {dataset['imported_at']}")
    with core.connect() as db:
        doc_rows = db.execute("SELECT source_name, length(content) AS characters, provenance FROM app_documents ORDER BY source_name").fetchall()
    st.subheader(f"Indexed documents · {len(doc_rows)}")
    st.dataframe([{"Source": row["source_name"], "Characters": row["characters"], "Provenance": row["provenance"]} for row in doc_rows], use_container_width=True, hide_index=True)

with history_tab:
    st.subheader("Persisted task history")
    for task in core.list_tasks(100):
        with st.expander(f"{task['status']} · {task['request'][:110]} · {task['task_id'][:8]}"):
            st.write(task["request"])
            st.write(task["summary"] or "No final summary recorded.")
            st.caption(f"Created {task['created_at']} · Updated {task['updated_at']}")
            if st.button("Open execution", key=f"open_{task['task_id']}"):
                st.session_state["active_task_id"] = task["task_id"]
                st.rerun()