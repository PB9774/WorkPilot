# Architecture

## Runtime Shape

`app.py` is the Streamlit interface. It calls plain service functions in `workpilot_core.py`. SQLite (`sqlite3`) is the single local persistence layer. The in-process importer in `workpilot_core.py` validates and loads the packaged structured tables, internal sandbox snapshot, and document files; it does not execute code found beside the selected data directory.

The model adapter uses the OpenAI Python SDK with Google's OpenAI-compatible Gemini endpoint and function calling. `GEMINI_API_KEY` is optional for import, browsing the catalog, and tests. Without it, the task-run button is disabled and the service fails closed if called directly. The default model is `gemini-3.8-flash`, configurable as `WORKPILOT_MODEL`. Gemini free-tier quotas and model availability are controlled by Google and can change.

## Execution Loop

1. Create and persist the user's request as a `pending` task.
2. Build a small trusted instruction message that explains tool boundaries and the synthetic fixture status, plus dataset names/counts (not dataset contents).
3. Ask the configured model for a response or registered tool call.
4. Parse JSON arguments and dispatch only allowlisted tool names.
5. Limit tool-call iterations (`WORKPILOT_MAX_STEPS`) and elapsed time (`WORKPILOT_MAX_RUNTIME_SECONDS`). Tool results are bounded before being returned to the model.
6. Persist call arguments, result, status, and timestamp. Derive final success from persisted successful tool results, never from model prose alone.

There is no chain-of-thought persistence. Retrieved documents and cells are untrusted data; embedded instructions cannot alter the system boundary or registry.

## Storage

- `vendors`, `invoices`, `purchase_orders`, `employees`, `departments`, `expense_records`: source CSV rows, stored as text by the supplied importer.
- `internal_invoices`: separate copy of the synthetic finance application's current state. Initial seed records are inserted only when absent so a Streamlit rerun does not undo sandbox changes.
- `documents` / `docs_fts`: source package document indexing from the reference importer.
- `app_documents`: bounded searchable copies with source names and provenance for user uploads and packaged source documents.
- `dataset_catalog`: table names, source names, counts, columns, and import timestamps.
- `tasks`, `execution_steps`, `approvals`, `audit_events`: task and guardrail state.

Task and approval transitions are persisted in SQLite. Source tables are read-only to agent tools. Task/tool logs contain bounded arguments/results and should still be treated as potentially sensitive local data.

## Tool Registry and Permissions

Tools are declared in `_tool_schemas()` and dispatched explicitly in `run_task()`. Unknown names, invalid JSON objects, unknown table/field names, oversized results, and unapproved mutations fail closed.

Read tools: dataset inspection, record search, document search/read, deterministic metrics, task status/history. Local file creation: `save_report`, restricted to `OUTPUT_DIR`, with file-readback verification. Mutation: `sandbox_update_invoice_status`, restricted to a small status allowlist in `internal_invoices`.

The model must call `request_approval` first. The approval records a hash of the complete action argument object, including target, parameters, expected effect, and reason. The Python mutation function independently compares the subsequent action hash and refuses any mismatch. Rejection does not execute the update. Successful updates are read back and logged.

## Retrieval, Privacy, and Evidence

The model sees only a dataset catalog initially. Record search is bounded and omits field names likely to contain direct identifiers or secrets (email, phone, address, tax ID, account, IBAN, SSN, password, secret, token, credential). The local UI/database retain imported values. Metrics are computed with `Decimal` and validated against real table columns.

Document search is keyword-based, bounded, and returns source names and excerpts. Imported content is never treated as executable instruction. There is no vector database or OCR.

Reports are written under a configured directory after basename normalization, size checks, and path validation; success means the file can be read back with the exact content. Sandbox success is based on a persisted state readback.

## Browser Boundary

The finance page is served by a standard-library `ThreadingHTTPServer` bound only to `127.0.0.1`. It exposes one read-only page and one status form route. There is no external navigation, upload, download, JavaScript execution, or model-selected selector/URL. The Python browser adapter constructs the URL itself and uses fixed accessible form locators with explicit timeouts.

Before launching Chromium, the tool checks that the approval hash matches the complete action parameters and that the sandbox target exists. The page handler independently repeats that exact approval check before mutation. The browser then inspects the target row, fills the form, submits it, and reads a rendered result whose status is backed by persisted SQLite readback. The server rejects non-local Host headers and unknown paths. The sandbox is a local synthetic evaluation app, not a production finance system.

## Known Technical Limits

- No authentication, multi-user authorization, tenant isolation, or production secret-management integration.
- No comprehensive tool argument model validation beyond explicit checks and JSON schemas supplied to the model.
- No automatic retry strategy for model/tool failures beyond the SDK's single retry; non-idempotent actions are not blindly retried.
- No end-to-end task predicate engine for the dataset's scenario corpus.
- A successful evidence-bearing tool call can support `completed`; richer task-specific postconditions should be defined before expanding consequential workflows.
