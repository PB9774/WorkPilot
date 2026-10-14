import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import workpilot_core as core


DATA = core.DEFAULT_DATA


class WorkPilotCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.db_path = root / "app.sqlite3"
        self.output_dir = root / "outputs"
        self.db_patch = patch.object(core, "DB_PATH", self.db_path)
        self.output_patch = patch.object(core, "OUTPUT_DIR", self.output_dir)
        self.db_patch.start()
        self.output_patch.start()
        core.initialize(DATA)

    def tearDown(self):
        self.output_patch.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_bundled_dataset_import_and_search(self):
        counts = core.initialize(DATA)
        self.assertGreater(counts["invoices"], 100)
        result = core._execute_read_tool("search_records", {"dataset": "invoices", "field": "invoice_id", "value": "INV-0101"})
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["records"][0]["invoice_id"], "INV-0101")
        schema = core.inspect_dataset("invoices")
        fields = {field["name"]: field for field in schema["fields"]}
        self.assertEqual(fields["total_amount"]["inferred_type"], "number")
        self.assertGreater(fields["due_date"]["missing_values"], 0)

    def test_document_search_returns_source_provenance(self):
        result = core._execute_read_tool("search_documents", {"query": "invoice processing"})
        self.assertTrue(result["matches"])
        self.assertTrue(all(match["source_name"] for match in result["matches"]))

    def test_document_text_redacts_common_direct_identifiers(self):
        value = core._redact_text("Reach person@example.test or +1-555-0101; tax SYN-VAT-1234.")
        self.assertNotIn("person@example.test", value)
        self.assertNotIn("SYN-VAT-1234", value)
        self.assertIn("[REDACTED_EMAIL]", value)
        self.assertIn("[REDACTED_TAX_ID]", value)

    def test_user_csv_import_and_malformed_json(self):
        imported = core.import_upload("regional_sales.csv", b"region,revenue\nNorth,120\nSouth,80\n")
        self.assertTrue(imported["ok"])
        rows = core._execute_read_tool("search_records", {"dataset": imported["table"], "query": "North"})
        self.assertEqual(rows["records"][0]["revenue"], "120")
        duplicate = core.import_upload("regional_sales.csv", b"region,revenue\nNorth,120\nSouth,80\n")
        self.assertTrue(duplicate["duplicate"])
        rejected = core.import_upload("bad.json", b"{not json")
        self.assertFalse(rejected["ok"])
        malformed = core.import_upload("broken.csv", b"a,b\n1,2\n3\n")
        self.assertFalse(malformed["ok"])

    def test_grouped_metrics_are_deterministic_and_completion_needs_evidence(self):
        imported = core.import_upload("regional_sales.csv", b"region,revenue\nNorth,120\nSouth,80\nNorth,30\n")
        metrics = core._execute_read_tool("compare_groups", {
            "dataset": imported["table"], "group_field": "region", "value_field": "revenue", "operation": "sum"
        })
        self.assertEqual(metrics["groups"]["North"]["value"], "150.00")
        task_id = core.create_task("Evidence-derived status")
        self.assertEqual(core._evidence_status(task_id), "failed")
        core._record_step(task_id, 1, "compare_groups", {}, metrics)
        self.assertEqual(core._evidence_status(task_id), "completed")

    def test_recovered_unknown_dataset_attempt_does_not_keep_task_partial(self):
        task_id = core.create_task("Retry with the correct table")
        core._record_step(task_id, 1, "inspect_dataset", {"dataset": "invoices.csv"}, {"error": "Unknown dataset. Use a table name from the catalog."}, "failed")
        core._record_step(task_id, 2, "inspect_dataset", {"dataset": "invoices"}, {"fields": []})
        self.assertEqual(core._evidence_status(task_id), "completed")

    def test_unrecovered_failure_keeps_task_partial(self):
        task_id = core.create_task("Report a failed tool")
        core._record_step(task_id, 1, "search_records", {}, {"records": []})
        core._record_step(task_id, 2, "read_document", {}, {"error": "Document source not found."}, "failed")
        self.assertEqual(core._evidence_status(task_id), "partially_completed")

    def test_report_saving_is_confined_and_verified(self):
        result = core._save_report({"filename": "summary.md", "content": "# Verified\n"})
        self.assertTrue(result["verified"])
        self.assertTrue((self.output_dir / "summary.md").is_file())
        traversal = core._save_report({"filename": "../../outside.md", "content": "blocked"})
        self.assertTrue(traversal["verified"])
        self.assertEqual(Path(traversal["path"]).parent, self.output_dir)

    def test_sandbox_mutation_requires_exact_approved_arguments(self):
        task_id = core.create_task("Update the sandbox test invoice")
        approval_args = {
            "action": "sandbox_update_invoice_status",
            "target": "INV-0001",
            "parameters": {"status": "approved"},
            "expected_effect": "Sandbox status is approved",
            "reason": "Explicit test approval",
        }
        with core.connect() as db:
            approval_id = "test-approval"
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,NULL)",
                       (approval_id, task_id, "request_approval", core._hash_args(approval_args), json.dumps(approval_args), "pending", core._now()))
        changed_args = {**approval_args, "parameters": {"status": "rejected"}}
        refused = core._sandbox_update_invoice_status(task_id, changed_args)
        self.assertIn("error", refused)
        core.decide_approval(approval_id, True)
        applied = core._sandbox_update_invoice_status(task_id, approval_args)
        self.assertTrue(applied["verified"])
        core.initialize(DATA)
        repeated = core._sandbox_update_invoice_status(task_id, approval_args)
        self.assertTrue(repeated["already_applied"])
        with core.connect() as db:
            audit_count = db.execute("SELECT COUNT(*) FROM audit_events WHERE task_id=? AND event_type='sandbox_invoice_status_updated'", (task_id,)).fetchone()[0]
        self.assertEqual(audit_count, 1)
        readback = core._execute_read_tool("search_records", {"dataset": "internal_invoices", "field": "invoice_id", "value": "INV-0001"})
        self.assertEqual(readback["records"][0]["status"], "approved")

    def test_rejected_approval_does_not_mutate(self):
        task_id = core.create_task("Reject a sandbox mutation")
        args = {"action": "sandbox_update_invoice_status", "target": "INV-0001", "parameters": {"status": "rejected"}, "expected_effect": "", "reason": ""}
        with core.connect() as db:
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,NULL)",
                       ("reject-me", task_id, "request_approval", core._hash_args(args), json.dumps(args), "pending", core._now()))
        core.decide_approval("reject-me", False)
        result = core._sandbox_update_invoice_status(task_id, args)
        self.assertIn("error", result)
        invoice = core._execute_read_tool("search_records", {"dataset": "internal_invoices", "field": "invoice_id", "value": "INV-0001"})
        self.assertEqual(invoice["records"][0]["status"], "paid")

    def test_task_and_execution_steps_persist(self):
        task_id = core.create_task("Persist this task")
        core._record_step(task_id, 1, "inspect_dataset", {}, {"datasets": []})
        self.assertEqual(len(core.task_steps(task_id)), 1)
        self.assertEqual(core._execute_read_tool("get_task_status", {"task_id": task_id})["status"], "pending")

    def test_model_selects_tool_and_receives_its_actual_result(self):
        call = SimpleNamespace(id="call-1", function=SimpleNamespace(
            name="search_records",
            arguments=json.dumps({"dataset": "invoices", "field": "invoice_id", "value": "INV-0101"}),
        ))
        responses = [
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))]),
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Found INV-0101 in invoices.csv.", tool_calls=None))]),
        ]
        observed_messages = []

        class FakeCompletions:
            def create(self, **kwargs):
                observed_messages.append(kwargs["messages"])
                return responses.pop(0)

        fake_groq = types.ModuleType("groq")
        fake_groq.Groq = lambda **kwargs: SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
        task_id = core.create_task("Find invoice INV-0101")
        with patch.dict(sys.modules, {"groq": fake_groq}):
            result = core.run_task(task_id, api_key="test-key", model="test-model")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(observed_messages), 2)
        tool_results = [message for message in observed_messages[1] if message["role"] == "tool"]
        self.assertIn("INV-0101", tool_results[0]["content"])
        self.assertEqual(core.task_steps(task_id)[0]["tool_name"], "search_records")


if __name__ == "__main__":
    unittest.main()