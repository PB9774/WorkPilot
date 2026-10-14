#!/usr/bin/env python3
"""Reference (stdlib-only) idempotent import of the dataset into SQLite + FTS5.

Shows the intended ingestion shape for ingestion.py / retrieval.py; it is a demo, not part of the agent.
    python scripts/reference_import.py --db /tmp/workpilot.db      # run twice: row counts do not change
"""
import argparse, csv, json, sqlite3
from pathlib import Path

CSV_TABLES = {  # file -> (table, primary key)
    "vendors.csv": ("vendors", "vendor_id"), "invoices.csv": ("invoices", "invoice_id"), "purchase_orders.csv": ("purchase_orders", "po_number"),
    "employees.csv": ("employees", "employee_id"), "departments.csv": ("departments", "department_id"), "expense_records.csv": ("expense_records", "expense_id")}


def pdf_text(p):
    try:
        import fitz
        return "".join(pg.get_text() for pg in fitz.open(p))
    except Exception:
        try:
            from pypdf import PdfReader
            return "\n".join(pg.extract_text() or "" for pg in PdfReader(str(p)).pages)
        except Exception:
            return ""


def import_all(db: sqlite3.Connection, data: Path):
    for fn, (table, pk) in CSV_TABLES.items():
        with open(data / "structured" / fn, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        cols = list(rows[0])
        db.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(f'{c} TEXT' + (' PRIMARY KEY' if c == pk else '') for c in cols)})")
        upd = ", ".join(f"{c}=excluded.{c}" for c in cols if c != pk)
        db.executemany(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) ON CONFLICT({pk}) DO UPDATE SET {upd}",
                       [[r[c] for c in cols] for r in rows])
    db.execute("""CREATE TABLE IF NOT EXISTS internal_invoices (record_id TEXT PRIMARY KEY, invoice_id TEXT, vendor_id TEXT, invoice_number TEXT,
                  status TEXT, total_amount REAL, idempotency_key TEXT UNIQUE, payload TEXT)""")
    for r in json.loads((data / "structured/internal_system_records.json").read_text())["invoices"]:
        db.execute("""INSERT INTO internal_invoices VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(idempotency_key) DO NOTHING""",
                   (r["record_id"], r["invoice_id"], r["vendor_id"], r["invoice_number"], r["status"], r["total_amount"], r["idempotency_key"], json.dumps(r)))
    db.execute("CREATE TABLE IF NOT EXISTS documents (path TEXT PRIMARY KEY, doc_type TEXT, content TEXT)")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(path UNINDEXED, content)")
    for p in sorted((data / "documents").rglob("*")):
        if p.suffix not in (".pdf", ".txt", ".md"):
            continue
        rel = str(p.relative_to(data))
        text = pdf_text(p) if p.suffix == ".pdf" else p.read_text(encoding="utf-8")
        db.execute("INSERT INTO documents VALUES (?,?,?) ON CONFLICT(path) DO UPDATE SET content=excluded.content", (rel, p.parent.name, text))
        db.execute("DELETE FROM docs_fts WHERE path=?", (rel,))
        db.execute("INSERT INTO docs_fts (path, content) VALUES (?,?)", (rel, text))
    db.commit()


def counts(db):
    names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'docs_fts_%' ORDER BY name")]
    return {n: db.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in names}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=":memory:")
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent / "data"))
    a = ap.parse_args()
    con = sqlite3.connect(a.db)
    import_all(con, Path(a.data))
    print(counts(con))
