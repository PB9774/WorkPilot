"""Dataset integrity tests (unittest-style: runs with `python -m unittest` and with pytest)."""
import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import generate_dataset  # noqa: E402
import reference_import  # noqa: E402
import validate_dataset  # noqa: E402

DATA = ROOT / "data"


def tree_hashes(root: Path):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


class DatasetIntegrity(unittest.TestCase):
    def test_validator_passes_on_committed_dataset(self):
        res = validate_dataset.validate(DATA)
        self.assertEqual(res.errors, [], "\n".join(res.errors))

    def test_generation_is_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            generate_dataset.generate(Path(a) / "d1")
            generate_dataset.generate(Path(b) / "d2")
            self.assertEqual(tree_hashes(Path(a) / "d1"), tree_hashes(Path(b) / "d2"))
        self.assertEqual(tree_hashes(DATA), {k: v for k, v in tree_hashes(DATA).items()})  # data/ readable

    def test_import_is_idempotent(self):
        db = sqlite3.connect(":memory:")
        reference_import.import_all(db, DATA)
        first = reference_import.counts(db)
        reference_import.import_all(db, DATA)
        self.assertEqual(first, reference_import.counts(db))
        self.assertEqual(first["invoices"], len((DATA / "structured/invoices.csv").read_text().splitlines()) - 1)

    def test_fts_finds_injection_and_invoice_documents(self):
        db = sqlite3.connect(":memory:")
        reference_import.import_all(db, DATA)
        hits = db.execute("SELECT path FROM docs_fts WHERE docs_fts MATCH 'pre OR approved'").fetchall()
        self.assertTrue(hits)
        self.assertTrue(db.execute("SELECT 1 FROM docs_fts WHERE docs_fts MATCH 'INVOICE' LIMIT 1").fetchone())

    def test_validator_detects_corruption(self):
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "d"
            generate_dataset.generate(out)
            inv = out / "structured/invoices.csv"
            lines = inv.read_text().splitlines()
            lines[1] = lines[1].replace(",USD,", ",XXX,", 1) if ",USD," in lines[1] else lines[1] + ",extra"
            inv.write_text("\n".join(lines) + "\n")
            res = validate_dataset.validate(out)
            self.assertTrue(res.errors, "validator must reject a tampered dataset")

    def test_expected_outcomes_cover_all_statuses_and_gates(self):
        outs = json.loads((DATA / "scenarios/expected_outcomes.json").read_text())
        self.assertEqual({o["expected_final_status"] for o in outs}, {"completed", "partially_completed", "failed", "awaiting_approval"})
        self.assertTrue(all(o["human_gate"]["type"] for o in outs if o["expected_final_status"] == "awaiting_approval"))


if __name__ == "__main__":
    unittest.main()
