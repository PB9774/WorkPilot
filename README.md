# WorkPilot AI

WorkPilot is a Python/Streamlit proof of concept for retrieving supplied business data, selecting allowlisted tools with Gemini Flash, persisting execution evidence, and requiring human approval before a local finance-sandbox update.

## Live Demo

Try the deployed app: [WorkPilot AI on Streamlit](https://workpilotpb.streamlit.app/).

The demo uses fictional synthetic Meridian Forge Corp data. Model-driven tasks require the deployed app to have a valid `GEMINI_API_KEY` configured in Streamlit secrets.

## Start Here

The workspace already contains a complete evaluation dataset. It is **synthetic** data for fictional Meridian Forge Corp, not real company or public Kaggle data. Its seeded anomalies and expected outcomes are intended for controlled testing. Do not use them as evidence about a real business.

The app can import and inspect data without an API key. A Gemini API key is required only for model-driven task planning.

## Available Data

Data root: `workpilot_dataset/workpilot/data`. Paths in the table are relative to that directory.

| Source                                        | Contents                                                                               |
| --------------------------------------------- | -------------------------------------------------------------------------------------- |
| `structured/vendors.csv`                      | 26 vendor records; active, pending, and suspended states                               |
| `structured/invoices.csv`                     | 133 invoice rows, including registered duplicate, conflict, and missing-field fixtures |
| `structured/purchase_orders.csv`              | 58 purchase orders with budgets, line items, and invoice links                         |
| `structured/employees.csv`, `departments.csv` | 21 employees and 7 departments, including approval roles and limits                    |
| `structured/expense_records.csv`              | 60 expense claims for policy checks                                                    |
| `structured/internal_system_records.json`     | 95 starting records for the separate finance sandbox copy                              |
| `documents/`, `knowledge/`                    | Invoice/PO documents, emails, contracts, and policies in PDF/TXT/Markdown              |
| `scenarios/`                                  | 62 tasks, expected outcomes, 20 failure scenarios, and a malformed CSV fixture         |

The dataset clock is `2026-10-01`; use it when interpreting overdue and derived-date fixtures. [Dataset README](workpilot_dataset/workpilot/data/README.md) summarizes the fixture set. [Data dictionary](workpilot_dataset/workpilot/data/DATA_DICTIONARY.md) describes schemas and predicate types. [Manifest](workpilot_dataset/workpilot/data/manifest.json) records provenance flags, file hashes, counts, and anomaly references.

The app keeps source tables separate from app state. CSV/JSON imports retain their original fields; unrelated schemas are not joined automatically. Imported document text is untrusted content and is not treated as instructions. The app does not fabricate missing values.

## Repository Map

| Path                                   | Responsibility                                                                                                              |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `app.py`                               | Streamlit task, data import/catalog, approval, evidence, and history views                                                  |
| `workpilot_core.py`                    | SQLite import/persistence, bounded Gemini tool loop, retrieval, approval checks, report verification, and localhost sandbox |
| `tests/test_workpilot_core.py`         | Offline app tests, including mocked Gemini calls and a Playwright sandbox mutation                                          |
| `workpilot_dataset/workpilot/data/`    | Supplied synthetic evaluation data and its data documentation                                                               |
| `workpilot_dataset/workpilot/scripts/` | Dataset generator, validator, fixtures, and standalone reference importer                                                   |
| `workpilot_dataset/workpilot/tests/`   | Dataset integrity and determinism tests                                                                                     |
| `ARCHITECTURE.md`                      | Runtime, permissions, persistence, and browser boundaries                                                                   |
| `DATASET_GUIDE.md`                     | Import formats, provenance, and custom-data instructions                                                                    |
| `.env.example`                         | Supported environment variables; Streamlit does not load it automatically                                                   |

## Setup

Python 3.10 or newer is supported. From the workspace root, create the environment and install dependencies:

```powershell
py -3.10 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

The runtime uses Streamlit for the UI, the OpenAI Python SDK with Google's Gemini-compatible endpoint for model tool calls, `pypdf` for text-layer PDFs, Playwright/Chromium for the restricted local browser action, and SQLite from the Python standard library. Pytest runs the automated tests.

To enable model-driven tasks, create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey) and set it in the shell. Never commit it:

```powershell
$env:GEMINI_API_KEY = "your-key"
$env:WORKPILOT_MODEL = "gemini-3.8-flash"
```

The app connects to Google's OpenAI-compatible Gemini endpoint. Gemini free-tier model access and rate limits can change; check the current [Gemini API pricing and limits](https://ai.google.dev/gemini-api/docs/pricing) if requests are refused.

## Run The App

Bind the unauthenticated demo to loopback:

```powershell
streamlit run app.py --server.address 127.0.0.1
```

Open `http://127.0.0.1:8501`. In **Data**, inspect the bundled catalog or upload multiple CSV/JSON/PDF/TXT/Markdown files. In **Tasks**, submit an objective and review persisted tool evidence. Mutations pause for exact-action approval and are restricted to the local sandbox invoice-status form.

### Example Prompts

In the **Tasks** tab, try prompts such as:

- `Find the latest Redwood IT Hardware invoice and report its invoice number, amount, and status.`
- `Search the invoice processing policy for duplicate-invoice checks and summarize the relevant guidance.`
- `Compare invoice INV-0132 in the source data with the finance sandbox and report any status mismatch.`
- `Calculate the total invoice amount grouped by currency.`

These examples use the bundled synthetic dataset and the app's current read and analysis tools. Results are recorded in the execution evidence and task history.

Optional paths and limits can be set before launch:

```powershell
$env:WORKPILOT_DATA_DIR = "C:\\authorized-data\\workpilot-data"
$env:WORKPILOT_DB = ".workpilot\\workpilot.sqlite3"
$env:WORKPILOT_OUTPUT_DIR = "data\\outputs"
$env:WORKPILOT_MAX_STEPS = "8"
$env:WORKPILOT_MAX_RUNTIME_SECONDS = "90"
```

An initial data directory must contain the six named CSVs under `structured/`. `structured/internal_system_records.json`, `documents/`, and `knowledge/` are optional. Additional user datasets can have unrelated columns and are imported through the Data tab. Scanned PDFs without extractable text are rejected; OCR and Excel are not supported.

## Work On The Repo

1. Keep real/private source data outside version control; `.gitignore` excludes local databases, imported-data directories, reports, and secrets.
2. Put app behavior in `workpilot_core.py` and UI wiring in `app.py`. Keep model-selected actions inside `_tool_schemas()` and explicit backend dispatch; never pass arbitrary SQL, Python, shell, URLs, or JavaScript to the model.
3. Add deterministic tests under `tests/`. Use temporary SQLite state and mock the model client; normal tests must not need credentials or make paid calls.
4. For dataset-generator changes, update `scripts/generate_dataset.py` and validate generated output. The committed dataset README is generator-controlled and its hash is stored in `manifest.json`.
5. Run the app tests, dataset tests, and dataset validator before submitting changes.

## Verification Commands

```powershell
python -m pytest tests workpilot_dataset/workpilot/tests -q
python workpilot_dataset/workpilot/scripts/validate_dataset.py
```

The app tests make no Gemini API call. They cover data/document retrieval, schema inspection, upload rejection/idempotency, numeric aggregation, report readback and path confinement, approval enforcement/rejection, mutation idempotency, task persistence, dynamic tool-result feedback, and the actual local Playwright form. The dataset validator independently checks its 98 data/manifest rules.

## Current Scope

Implemented tools cover dataset inspection/search, document retrieval, deterministic metrics, report saving, task history, approval requests, and one approved sandbox status update. The system uses one bounded orchestrator, not multiple agents.

Not implemented: full verification for all 62 scenario tasks, invoice creation/payment scheduling/vendor editing, external integrations, OCR, Excel import, authentication, multi-user/tenant isolation, and production deployment. A successful model response is not proof; completion depends on recorded tool evidence and relevant readback checks. See [ARCHITECTURE.md](ARCHITECTURE.md) before extending mutation behavior.
