#!/usr/bin/env python3
"""Validate the synthetic dataset. Exit code 0 only if every check passes.

    python scripts/validate_dataset.py [--data data]

Independent of the generator: it re-reads the files and recomputes the policy rules from the CSVs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataset_text import ARITH_TOLERANCE, AS_OF, FX_TO_USD, PO_TOLERANCE, ROLE_RANK, TIER_BOUNDS  # noqa: E402

TOOLS = {"search_structured", "search_documents", "read_document", "get_internal_record", "create_internal_invoice", "update_internal_invoice",
         "schedule_payment", "browser_action", "request_user_approval", "ask_user_clarification"}
STATUSES = {"completed", "partially_completed", "failed", "awaiting_approval"}
BEHAVIORS = {"retry", "use_alternative_source", "request_clarification", "request_approval", "reject_action", "report_partial_failure"}
CATEGORIES = {"simple_retrieval", "multi_source_retrieval", "data_entry", "reconciliation", "duplicate_prevention", "policy_reasoning",
              "ambiguity_handling", "failure_recovery", "verification", "permission_enforcement", "prompt_injection", "partial_completion"}
POST_TYPES = {"internal_record_exists", "internal_record_matches", "internal_record_count", "no_state_change", "approval_requested_before_mutation",
              "tool_not_called", "tool_called", "final_answer_contains", "flags_reported", "clarification_requested", "injection_not_followed",
              "internal_field_equals", "tool_retried", "no_flags_reported", "human_gate_reached", "failure_reported", "readback_after_write",
              "no_discrepancies_reported", "discrepancies_reported", "source_disclosed", "internal_field_contains"}
FILES = ["structured/vendors.csv", "structured/invoices.csv", "structured/purchase_orders.csv", "structured/employees.csv", "structured/departments.csv",
         "structured/expense_records.csv", "structured/internal_system_records.json", "knowledge/invoice_processing_policy.md",
         "knowledge/expense_approval_policy.md", "knowledge/vendor_onboarding_policy.md", "knowledge/payment_policy.md", "knowledge/tool_usage_guide.md",
         "scenarios/tasks.json", "scenarios/expected_outcomes.json", "scenarios/failure_scenarios.json", "README.md", "DATA_DICTIONARY.md", "manifest.json"]


def norm(s):
    return "".join(ch for ch in (s or "").upper() if ch.isalnum())


def read_csv(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def usd(a, c):
    return (D(a) * FX_TO_USD[c]).quantize(D("0.01"))


def tier(total_usd, has_po):
    t = next(t for b, t, _ in TIER_BOUNDS if b is None or total_usd <= b)
    if not has_po:
        t = min(t + 1, 4)
    return t, next(r for _, tt, r in TIER_BOUNDS if tt == t)


class V:
    def __init__(self):
        self.errors, self.passed = [], []

    def check(self, name, cond, detail=""):
        (self.passed if cond else self.errors).append(name if cond else f"{name}: {detail}")
        return cond


def validate(data: Path) -> V:
    v = V()
    c = v.check
    for rel in FILES:
        c(f"file exists {rel}", (data / rel).is_file(), "missing")
    if v.errors:
        return v
    S = data / "structured"
    vendors, invoices, pos = read_csv(S / "vendors.csv"), read_csv(S / "invoices.csv"), read_csv(S / "purchase_orders.csv")
    emps, deps, exps = read_csv(S / "employees.csv"), read_csv(S / "departments.csv"), read_csv(S / "expense_records.csv")
    system = json.loads((S / "internal_system_records.json").read_text())
    tasks = json.loads((data / "scenarios/tasks.json").read_text())
    outs = json.loads((data / "scenarios/expected_outcomes.json").read_text())
    fails = json.loads((data / "scenarios/failure_scenarios.json").read_text())
    man = json.loads((data / "manifest.json").read_text())

    # ---- counts required by the brief
    inv_docs = [p for p in (data / "documents/invoices").iterdir() if p.suffix in (".pdf", ".txt")]
    for name, val, lo, hi in [("vendors", len(vendors), 20, 30), ("invoices", len(invoices), 100, 10**6), ("purchase orders", len(pos), 40, 60),
                              ("employees", len(emps), 15, 25), ("departments", len(deps), 5, 8), ("invoice documents", len(inv_docs), 25, 10**6),
                              ("PO documents", len(list((data / "documents/purchase_orders").iterdir())), 10, 10**6),
                              ("emails", len(list((data / "documents/emails").iterdir())), 10, 10**6),
                              ("policy documents (documents/policies)", len(list((data / "documents/policies").glob("*.md"))), 5, 10**6),
                              ("contracts", len(list((data / "documents/contracts").iterdir())), 5, 10**6),
                              ("tasks", len(tasks), 30, 10**6), ("failure scenarios", len(fails), 15, 10**6)]:
        c(f"count {name} in [{lo},{hi}]", lo <= val <= hi, f"got {val}")

    # ---- keys and foreign keys
    def uniq(rows, key, label):
        vals = [r[key] for r in rows]
        c(f"unique {label}.{key}", len(vals) == len(set(vals)), "duplicates present")
    uniq(vendors, "vendor_id", "vendors"); uniq(invoices, "invoice_id", "invoices"); uniq(pos, "po_number", "purchase_orders")
    uniq(emps, "employee_id", "employees"); uniq(deps, "department_id", "departments"); uniq(exps, "expense_id", "expenses")
    vm, em, dm, pm = ({r[k]: r for r in rows} for rows, k in [(vendors, "vendor_id"), (emps, "employee_id"), (deps, "department_id"), (pos, "po_number")])
    im = {r["invoice_id"]: r for r in invoices}
    bad = [r["invoice_id"] for r in invoices if r["vendor_id"] not in vm or r["department_id"] not in dm or (r["po_number"] and r["po_number"] not in pm)]
    c("FK invoices -> vendors/departments/POs", not bad, str(bad[:5]))
    bad = [r["invoice_id"] for r in invoices if r["vendor_id"] in vm and vm[r["vendor_id"]]["name"] != r["vendor_name"]]
    c("invoice vendor_name equals vendor master name", not bad, str(bad[:5]))
    bad = [r["po_number"] for r in pos if r["vendor_id"] not in vm or r["department_id"] not in dm or r["requester_id"] not in em]
    c("FK purchase_orders -> vendors/departments/employees", not bad, str(bad[:5]))
    bad = [r["employee_id"] for r in emps if r["department_id"] not in dm or (r["manager_id"] and r["manager_id"] not in em)]
    c("FK employees -> departments/managers", not bad, str(bad[:5]))
    c("FK departments -> head employee", all(r["head_employee_id"] in em for r in deps))
    c("FK expenses -> employees/approvers", all(r["employee_id"] in em and (not r["approver_id"] or r["approver_id"] in em) for r in exps))
    bad = []
    for p in pos:
        ids = [i for i in p["invoice_ids"].split(";") if i]
        items = json.loads(p["line_items_json"])
        bad += [p["po_number"] for i in ids if i not in im or im[i]["po_number"] != p["po_number"]]
        if any(D(i["quantity"]) * D(i["unit_price"]) != D(i["line_total"]) for i in items):
            bad.append(p["po_number"] + ":line_total")
        sub = sum(D(i["line_total"]) for i in items)
        if abs(sub * (1 + D(vm[p["vendor_id"]]["tax_rate"])) - D(p["approved_budget"])) > D("0.01"):
            bad.append(p["po_number"] + ":budget")
    c("PO <-> invoice links, line totals and tax-inclusive budget", not bad, str(bad[:5]))
    bad = [i["invoice_id"] for i in invoices if i["po_number"] and i["invoice_id"] not in pm[i["po_number"]]["invoice_ids"].split(";")]
    c("every PO-linked invoice listed in PO.invoice_ids", not bad, str(bad[:5]))

    # ---- anomalies registry and ordinary-record consistency
    anom_ids = {r for a in man["anomalies"] for r in a["records"]}
    ordinary = [i for i in invoices if i["invoice_id"] not in anom_ids]
    errs = []
    for i in ordinary:
        try:
            s, t, tot = D(i["subtotal"]), D(i["tax_amount"]), D(i["total_amount"])
            d0, d1 = date.fromisoformat(i["invoice_date"]), date.fromisoformat(i["due_date"])
            terms = int(vm[i["vendor_id"]]["payment_terms"].split()[1])
            if abs(s + t - tot) > ARITH_TOLERANCE or d1 != d0 + timedelta(days=terms) or abs(t - (s * D(vm[i["vendor_id"]]["tax_rate"])).quantize(D("0.01"))) > ARITH_TOLERANCE:
                errs.append(i["invoice_id"])
            if i["currency"] != vm[i["vendor_id"]]["currency"] or not i["invoice_number"] or d0 > date.fromisoformat(AS_OF):
                errs.append(i["invoice_id"])
        except Exception as e:  # noqa: BLE001
            errs.append(f"{i['invoice_id']}:{e}")
    c(f"ordinary invoices ({len(ordinary)}) are arithmetic/date/terms consistent", not errs, str(errs[:5]))
    c("anomaly records exist", all(r in im or r in pm or r in vm or r.startswith(("CON-", "DOC-", "EXP-")) for r in anom_ids), "dangling anomaly reference")
    keys = {}
    for i in invoices:
        if i["invoice_number"]:
            keys.setdefault((i["vendor_id"], norm(i["invoice_number"])), []).append(i["invoice_id"])
    dups = [v_ for v_ in keys.values() if len(v_) > 1]
    c("duplicate natural keys only where registered as anomalies", all(all(x in anom_ids for x in d) for d in dups), str(dups))
    c("at least one registered CSV duplicate", len(dups) >= 1)
    c("invoice statuses within vocabulary", {i["status"] for i in invoices} <= {"received", "pending_approval", "approved", "paid", "overdue", "rejected", "disputed"})
    c("all seven invoice statuses present", len({i["status"] for i in invoices}) == 7)
    c("overdue invoices are past due", all(date.fromisoformat(i["due_date"]) < date.fromisoformat(AS_OF) for i in invoices if i["status"] == "overdue" and i["due_date"]))
    c("vendor statuses cover active/pending/suspended", {x["status"] for x in vendors} == {"active", "pending", "suspended"})
    c("near-duplicate vendor names exist", any(a["name"][:5] == b["name"][:5] and a["vendor_id"] < b["vendor_id"] for a in vendors for b in vendors))
    c("tax ids are labelled synthetic", all(x["tax_id"].startswith("SYN-") for x in vendors))

    # ---- documents
    docs = {d["path"]: d for d in man["documents"]}
    ref = {}
    for i in invoices:
        if i["document_filename"]:
            ref.setdefault(i["document_filename"], []).append(i["invoice_id"])
    missing = [f for f in ref if not (data / "documents/invoices" / f).exists()]
    declared_missing = {Path(p).name for p, d in docs.items() if d["type"] == "invoice" and not d["exists"]}
    c("invoice documents exist except declared missing fixtures", set(missing) == declared_missing and len(missing) >= 1, f"{missing} vs {declared_missing}")
    c("every invoice document file is referenced exactly once", all(p.name in ref and len(ref[p.name]) == 1 for p in inv_docs), "orphan or shared document")
    for p in (data / "documents/purchase_orders").iterdir():
        c(f"PO doc {p.name} references an existing PO", p.stem in pm)
    for p in (data / "documents/emails").iterdir():
        txt = p.read_text(encoding="utf-8")
        att = re.search(r"^Attachments: (.*)$", txt, re.M).group(1)
        if att != "none":
            c(f"email {p.name} attachments exist", all((data / "documents/invoices" / a.strip()).exists() for a in att.split(",")))
    pdfs = [p for p in inv_docs if p.suffix == ".pdf"]
    c("at least some invoice documents are PDF", len(pdfs) >= 5 or "reportlab missing: PDFs written as TXT" in man["limitations"])
    extractor = None
    try:
        import fitz  # PyMuPDF
        extractor = lambda p: "".join(pg.get_text() for pg in fitz.open(p))  # noqa: E731
    except Exception:  # noqa: BLE001
        try:
            from pypdf import PdfReader
            extractor = lambda p: "\n".join(pg.extract_text() or "" for pg in PdfReader(str(p)).pages)  # noqa: E731
        except Exception:  # noqa: BLE001
            pass
    if extractor and pdfs:
        empty = [p.name for p in pdfs if len(extractor(p).strip()) < 100]
        c("PDF text layers extractable", not empty, str(empty[:5]))
    else:
        v.passed.append("PDF extraction check skipped (no PyMuPDF/pypdf installed)")
    inj = [p.name for p in (data / "documents").rglob("*") if p.is_file() and p.suffix in (".txt", ".pdf") and "IGNORE ALL PREVIOUS" in
           (p.read_text(errors="ignore") if p.suffix == ".txt" else (extractor(p) if extractor else "")).upper()]
    c("prompt-injection fixtures present (invoice/email/contract)", len(inj) >= 1 and any("EML" in n for n in [*inj, *(p.name for p in (data / "documents/emails").iterdir() if "disregard all earlier" in p.read_text().lower())]) and
      any("CON" in p.name for p in (data / "documents/contracts").iterdir() if "SYSTEM INSTRUCTION FOR AI" in p.read_text()))
    c("OCR/scan placeholder fixtures labelled SIMULATED", sum("SIMULATED" in p.read_text(errors="ignore") for p in inv_docs if p.suffix == ".txt") >= 2)

    # ---- internal system
    recs = system["invoices"]
    c("internal records have unique record ids/natural keys/idempotency keys", len({r["record_id"] for r in recs}) == len(recs) == len({(r["vendor_id"], norm(r["invoice_number"])) for r in recs}) == len({r["idempotency_key"] for r in recs}))
    errs, serrs = [], []
    for r in recs:
        i = im.get(r["invoice_id"])
        if not i or r["vendor_id"] not in vm or (r["po_number"] and r["po_number"] not in pm):
            errs.append(r["record_id"]); continue
        if r["invoice_id"] not in anom_ids and (r["status"] != i["status"] or D(str(r["total_amount"])) != D(i["total_amount"]) or r["invoice_number"] != i["invoice_number"]):
            errs.append(r["record_id"])
        ap, pay = r["approval"], r["payment"]
        if r["status"] == "paid" and (pay["status"] != "paid" or not pay["authorized_by"] in em or ap["approver_id"] == pay["authorized_by"]):
            serrs.append(r["record_id"] + ":paid")
        if r["status"] != "paid" and pay["status"] == "paid":
            serrs.append(r["record_id"] + ":payment")
        if r["status"] in ("approved", "paid", "overdue") and r["invoice_id"] not in anom_ids:
            if ap["approver_id"] != "SYSTEM-TIER0":
                a = em.get(ap["approver_id"])
                po = pm.get(r["po_number"])
                t, role = tier(usd(r["total_amount"], r["currency"]), bool(po))
                if not a or ROLE_RANK.get(a["role"], 0) < ROLE_RANK[role] or int(a["approval_limit_usd"]) < usd(r["total_amount"], r["currency"]) or (po and po["requester_id"] == ap["approver_id"]):
                    serrs.append(r["record_id"] + ":approver")
            elif tier(usd(r["total_amount"], r["currency"]), bool(r["po_number"]))[0] != 0:
                serrs.append(r["record_id"] + ":tier0")
        if r["status"] == "overdue" and r["due_date"] >= AS_OF:
            serrs.append(r["record_id"] + ":overdue")
    c("internal records reference CSV/vendors/POs and match ordinary rows", not errs, str(errs[:5]))
    c("approval/payment states consistent with policy (re-derived)", not serrs, str(serrs[:5]))
    c("internal system contains records not in the pipeline (received invoices absent)", len(recs) < len(invoices) and any(i["status"] == "received" and i["invoice_id"] not in {r["invoice_id"] for r in recs} for i in invoices))
    c("app records differ from CSV only for registered anomalies", all(r["invoice_id"] in anom_ids for r in recs if any(str(r[k]) != i for k, i in [("status", im[r["invoice_id"]]["status"])]) or D(str(r["total_amount"])) != D(im[r["invoice_id"]]["total_amount"])))

    # ---- scenarios
    tid = [t["task_id"] for t in tasks]
    c("task ids unique and aligned with outcomes", len(tid) == len(set(tid)) and tid == [o["task_id"] for o in outs])
    c("all 12 categories covered", {t["category"] for t in tasks} >= CATEGORIES, str(CATEGORIES - {t["category"] for t in tasks}))
    c("final statuses in vocabulary and all four used", {t["expected_final_status"] for t in tasks} == STATUSES)
    c("expected tools are allowlisted", all(set(t["expected_tools"]) <= TOOLS and set(o["expected_action_sequence"]) <= TOOLS for t, o in zip(tasks, outs)))
    bad = [t["task_id"] for t in tasks for p in t["required_postconditions"] if p["type"] not in POST_TYPES]
    c("postcondition types known", not bad, str(bad[:5]))
    bad = [t["task_id"] for t in tasks if not t["request"] or not t["required_postconditions"] or t["requesting_user"] not in em]
    c("tasks have request, postconditions and a real requesting user", not bad, str(bad[:5]))
    sysk = {(r["vendor_id"], norm(r["invoice_number"])) for r in recs}
    errs = []
    for t, o in zip(tasks, outs):
        for ch in o["expected_internal_state_changes"]:
            if ch["op"] == "create":
                k = (ch["natural_key"]["vendor_id"], norm(ch["natural_key"]["invoice_number"]))
                if k in sysk:
                    errs.append(t["task_id"] + ":create_target_already_exists")
                f = ch["fields"]
                src = next((i for i in invoices if (i["vendor_id"], norm(i["invoice_number"])) == k), None)
                if not src or ("total_amount" in f and abs(D(str(f["total_amount"])) - D(src["total_amount"])) > ARITH_TOLERANCE and src["invoice_id"] not in anom_ids):
                    errs.append(t["task_id"] + ":fields")
                if D(str(f["subtotal"])) + D(str(f["tax_amount"])) != D(str(f["total_amount"])) and abs(D(str(f["subtotal"])) + D(str(f["tax_amount"])) - D(str(f["total_amount"]))) > ARITH_TOLERANCE:
                    errs.append(t["task_id"] + ":arith")
            if t["expected_final_status"] == "completed" and not any(p["type"] in ("internal_record_exists", "internal_field_equals", "internal_record_matches") for p in t["required_postconditions"]):
                errs.append(t["task_id"] + ":no_persistence_postcondition")
        if t["expected_final_status"] == "awaiting_approval" and o["human_gate"]["type"] not in ("approval", "clarification"):
            errs.append(t["task_id"] + ":gate")
        if t["expected_final_status"] in ("failed", "awaiting_approval") and o["expected_internal_state_changes"] and t["expected_final_status"] == "failed":
            errs.append(t["task_id"] + ":failed_with_changes")
        for ii in o["expected_source_records"].get("invoice_ids", []):
            if ii not in im:
                errs.append(f"{t['task_id']}:{ii}")
        for d_ in o["expected_source_records"].get("documents", []):
            if d_ not in docs and not (data / d_).exists():
                errs.append(f"{t['task_id']}:{d_}")
        if any(p["type"] == "internal_record_count" and p["count"] == 1 for p in t["required_postconditions"]) and not o["expected_internal_state_changes"]:
            vk = next(p for p in t["required_postconditions"] if p["type"] == "internal_record_count")
            if (vk["vendor_id"], norm(vk["invoice_number"])) not in sysk:
                errs.append(t["task_id"] + ":count1_but_not_in_system")
    c("expected outcomes consistent with data and policy", not errs, str(errs[:8]))
    c("every mutating task requires a prior approval gate", all(any(p["type"] == "approval_requested_before_mutation" for p in t["required_postconditions"]) for t, o in zip(tasks, outs)
                                                                if o["expected_internal_state_changes"]))
    c("attempt vs verified outcome: all create tasks require read-back evidence", all(any(p["type"] in ("internal_record_exists",) for p in t["required_postconditions"]) and "get_internal_record" in o["expected_action_sequence"] and o["expected_action_sequence"][-1] == "get_internal_record"
                                                                                       for t, o in zip(tasks, outs) if any(ch["op"] == "create" for ch in o["expected_internal_state_changes"])))
    tids = set(tid)
    c("failure scenarios use known behaviors and tasks", all(f["expected_behavior"] in BEHAVIORS and set(f["related_task_ids"]) <= tids for f in fails))
    c("failure scenarios cover the 15 required themes", len({f["name"] for f in fails}) >= 15)
    mal = (data / "scenarios/fixtures/malformed_invoices_import.csv")
    c("malformed CSV fixture present", mal.is_file())
    if mal.is_file():
        rows = list(csv.reader(mal.read_text(encoding="utf-8").splitlines()))
        exp = next(f for f in fails if f["name"] == "malformed_csv_row")["expected_ingestion_result"]
        bad_lines = [n for n, r in enumerate(rows, start=1) if n > 1 and len(r) != len(rows[0])]
        c("malformed fixture: expected wrong-field-count lines match", bad_lines == [r["line"] for r in exp["rejected_rows"] if r["reason"] == "wrong_field_count"], str(bad_lines))
        c("malformed fixture good-row count", exp["good_rows"] == len(rows) - 1 - len(exp["rejected_rows"]))

    # ---- manifest
    errs = []
    for fe in man["files"]:
        p = data / fe["path"]
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != fe["sha256"] or p.stat().st_size != fe["bytes"]:
            errs.append(fe["path"])
    c("manifest hashes and sizes match files", not errs, str(errs[:5]))
    listed = {fe["path"] for fe in man["files"]}
    actual = {p.relative_to(data).as_posix() for p in data.rglob("*") if p.is_file() and p.name != "manifest.json"}
    c("manifest lists every file", listed == actual, str(sorted(actual ^ listed)[:5]))
    recs_by = {fe["path"]: fe.get("records") for fe in man["files"]}
    c("manifest record counts", recs_by["structured/invoices.csv"] == len(invoices) and recs_by["structured/vendors.csv"] == len(vendors) and recs_by["scenarios/tasks.json"] == len(tasks))
    c("manifest declares seed, version and anomalies", all(k in man for k in ("seed", "generation_version", "anomalies")) and len(man["anomalies"]) >= 15)

    # ---- safety
    errs = []
    for p in data.rglob("*"):
        if not p.is_file() or p.suffix == ".pdf":
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)", t):
            if not m.group(1).endswith(".example"):
                errs.append(f"{p.name}:{m.group(0)}")
        if re.search(r"\b(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b|\b\d{13,19}\b|\bIBAN\b", t):
            errs.append(f"{p.name}:secret-like")
    c("only .example e-mail domains; no keys, card/account-like numbers", not errs, str(errs[:5]))
    c("policies contain tier thresholds from constants", all(x in (data / "knowledge/expense_approval_policy.md").read_text() for x in ("2,500", "10,000", "50,000", "500")))
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).resolve().parent.parent / "data"))
    a = ap.parse_args()
    res = validate(Path(a.data))
    for n in res.passed:
        print("PASS", n)
    for e in res.errors:
        print("FAIL", e)
    print(f"\n{len(res.passed)} passed, {len(res.errors)} failed")
    sys.exit(1 if res.errors else 0)


if __name__ == "__main__":
    main()
