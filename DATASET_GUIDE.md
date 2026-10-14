# Dataset Guide

## Supplied Data

`workpilot_dataset/workpilot/data` is already present in this workspace. Its own README and manifest identify it as a seeded, fully synthetic evaluation dataset for fictional Meridian Forge Corp. It includes CSVs for vendors, invoices, purchase orders, employees, departments, and expenses; JSON finance state; policies; contracts; email and invoice documents; scenarios; expected outcomes; and deliberate anomaly/prompt-injection fixtures.

Do not present these records as genuine Kaggle data or real company activity. Use authorized genuine data for operational claims. Keep private downloads outside version control; `.gitignore` excludes common local data, output, environment, and SQLite locations.

## Supported User Imports

- CSV: header row required; every row must have the same number of fields. Original columns and source filename are retained. Values are stored as text; missing values remain empty rather than being invented.
- JSON: object or list of objects. Fields are unioned across rows; absent keys remain empty. Nested values are stored as their JSON string representation.
- TXT and Markdown: indexed with source filename and a user-supplied provenance marker.
- Text-based PDF: extracted with `pypdf`. Image-only/scanned files that yield no text are rejected with a clear message; OCR is not enabled.

Structured imports are stored in separate dynamically named SQLite tables and catalog entries, so unrelated schemas are not forced into a universal model. Repeat upload of the same filename and bytes is detected. Dataset tables and documents are searchable through bounded registered tools.

## Inspect and Import

Start the app with `streamlit run app.py`, then use the Data tab to inspect bundled sources, column names, row counts, and indexed document sources. Use the upload control for multiple CSV/JSON and document files. Each accepted source retains its filename; the import timestamp and columns are visible in the catalog.

For a separate initial dataset directory, set `WORKPILOT_DATA_DIR` to a directory containing `structured/` with the six supported WorkPilot CSV files. `documents/`, `knowledge/`, and `structured/internal_system_records.json` are optional. The importer validates known CSV headers and primary keys and does not execute scripts from beside the data. Extra user-provided tables are imported through the UI and do not need the bundled table names.

## Provenance and Limits

Packaged documents are indexed with paths relative to the configured dataset directory. User documents record their uploaded filename. The application does not verify external source URLs or licenses, and it does not fabricate either. Record source URLs, license, and description separately when they are known and supplied.

The manifest and data dictionary are the source of truth for fixture counts, synthetic status, evaluation date, anomaly registry, and scenario ground truth. A missing or unreadable document remains missing or unreadable; the system may disclose the structured source as an alternative but must not pretend it read a missing document.
