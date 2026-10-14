"""Internal-system state, expense records and structured-file writers."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

from dataset_text import AS_OF, COMPANY, FX_TO_USD, ROLE_RANK
from gen_core import idem_key, q2, usd

CAP = datetime(2026, 9, 30, 17, 0, 0)


def ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def num(x):
    return float(D(str(x)))


# ------------------------------------------------------------------ expenses
def expense_approver(B, emp_id, usd_val):
    cur = B.emap[emp_id]["manager_id"]
    while cur:
        e = B.emap[cur]
        if e["status"] == "active" and e["approval_limit_usd"] >= usd_val:
            return cur
        cur = e["manager_id"]
    return ""


def build_expenses(B):
    rng = B.rng
    cats = {"meals": (12, 95), "travel": (80, 1400), "lodging": (120, 900), "software": (15, 600),
            "training": (150, 3200), "office": (8, 220)}
    descs = {"meals": "Client meal", "travel": "Travel expense", "lodging": "Hotel stay", "software": "Software subscription",
             "training": "Training course fee", "office": "Office supplies"}
    people = [e for e in B.employees if e["status"] == "active"]
    self_idx, norcpt_idx = {7, 23, 41}, {12, 30, 47, 55}
    rows = []
    for n in range(1, 61):
        e = rng.choice(people)
        if n == 33:
            e = B.emap["EMP-020"]
        cat = rng.choice(list(cats))
        lo, hi = cats[cat]
        cur = rng.choices(["USD", "EUR", "GBP"], [85, 8, 7])[0]
        amount = q2(D(rng.randint(lo * 100, hi * 100)) / 100 / FX_TO_USD[cur])
        u = usd(amount, cur)
        d = datetime(2026, 7, 1) + timedelta(days=rng.randint(0, 85))
        status = rng.choices(["submitted", "approved", "reimbursed", "rejected"], [20, 45, 28, 7])[0]
        receipt = u <= 25 or n not in norcpt_idx
        if u > 25 and n in norcpt_idx:
            receipt = False
        approver, decided = "", ""
        if e["employee_id"] == "EMP-020":
            status = "rejected"
        if status != "submitted":
            approver = expense_approver(B, e["employee_id"], u)
            decided = (d + timedelta(days=rng.randint(1, 6))).date().isoformat()
            if n in self_idx and e["role"] in ROLE_RANK:
                approver = e["employee_id"]
                status = "approved"
        rows.append({"expense_id": f"EXP-{n:04d}", "employee_id": e["employee_id"], "expense_date": d.date().isoformat(),
                     "category": cat, "amount": str(amount), "currency": cur, "description": descs[cat],
                     "receipt_provided": str(receipt).lower(), "status": status, "approver_id": approver, "decision_date": decided})
    B.expenses = rows
    sel = [r["expense_id"] for r in rows if r["approver_id"] == r["employee_id"]]
    if sel:
        B.anomaly("self_approved_expense", sel, "Expense claims approved by the claimant (violates APP-EXP-03).")
    miss = [r["expense_id"] for r in rows if r["receipt_provided"] == "false" and usd(r["amount"], r["currency"]) > 25]
    if miss:
        B.anomaly("missing_receipt_above_threshold", miss, "Claims above 25 USD without a receipt (violates APP-EXP-01).")
    B.anomaly("terminated_employee_claim", ["EXP-0033"], "Claim by terminated employee EMP-020, status rejected per APP-EXP-04.")


# ------------------------------------------------------------------ internal finance application
def build_system(B):
    rng = B.rng
    recs, log = [], []
    seq = 0
    for inv in B.invoices:
        fid = inv["invoice_id"]
        in_sys = (inv["status"] != "received") or fid in B.in_system_force
        if fid in B.not_in_system_force or not in_sys:
            continue
        seq += 1
        v = B.vmap[inv["vendor_id"]]
        req = B.approval_requirement(inv, historical=True)
        created = datetime.strptime(inv["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        rec_id = f"ERP-INV-{seq:06d}"
        status = inv["status"]
        approval = {"required_tier": req["tier"], "required_role": req["role"] or "none", "status": "pending",
                    "approver_id": "", "decided_at": ""}
        payment = {"status": "not_scheduled", "payment_id": "", "authorized_by": "", "paid_at": "", "reference": ""}
        if status in ("approved", "paid", "overdue", "rejected"):
            if req["tier"] == 0 and status != "rejected":
                approver, a_status = "SYSTEM-TIER0", "auto_approved"
            else:
                pool = B.eligible_approvers(inv, req["role"] or "manager", True)
                if inv is B.fixtures.get("APPROVED_UNPAID"):   # keep the payment happy-path free of segregation-of-duties conflicts
                    pool = [p for p in pool if p != "EMP-002"]
                assert pool, (fid, req)
                approver, a_status = rng.choice(pool), ("rejected" if status == "rejected" else "approved")
            dec = min(created + timedelta(days=rng.randint(1, 6), hours=rng.randint(1, 8)), CAP)
            approval.update(status=a_status, approver_id=approver, decided_at=ts(dec))
            log.append({"ts": ts(dec), "actor": approver, "action": f"approval_{a_status}", "record_id": rec_id, "detail": ""})
            if status == "paid":
                pay = min(dec + timedelta(days=rng.randint(1, 25)), CAP)
                tot = usd(inv["total_amount"], inv["currency"])
                payer = "EMP-002" if tot <= 50000 else "EMP-001"
                if approver == payer:
                    payer = "EMP-001" if payer == "EMP-002" else "EMP-002"
                payment.update(status="paid", payment_id=f"SIM-PAY-{seq:06d}", authorized_by=payer, paid_at=ts(pay),
                               reference=f"SIM-REF-{seq:06d}")
                log.append({"ts": ts(pay), "actor": payer, "action": "payment_paid", "record_id": rec_id, "detail": "simulated"})
        elif status == "disputed":
            approval["status"] = "on_hold"
        rec = {"record_id": rec_id, "invoice_id": fid, "vendor_id": inv["vendor_id"], "invoice_number": inv["invoice_number"],
               "invoice_date": inv["invoice_date"], "due_date": inv["due_date"], "currency": inv["currency"],
               "subtotal": num(inv["subtotal"]), "tax_amount": num(inv["tax_amount"]), "total_amount": num(inv["total_amount"]),
               "po_number": inv["po_number"], "department_id": inv["department_id"], "status": status, "approval": approval,
               "payment": payment, "notes": "", "created_by": "EMP-003" if seq % 2 else "EMP-004", "created_at": inv["created_at"],
               "source": "erp_feed", "idempotency_key": idem_key(inv["vendor_id"], inv["invoice_number"])}
        ov = B.system_overrides.get(fid, {})
        for k, val in ov.items():
            if k == "approval_status":
                rec["approval"]["status"] = val
                rec["approval"].update(approver_id="", decided_at="")
            else:
                rec[k] = val
        log.append({"ts": inv["created_at"], "actor": rec["created_by"], "action": "invoice_created", "record_id": rec_id, "detail": ""})
        recs.append(rec)
    log.sort(key=lambda r: (r["ts"], r["record_id"]))
    for n, r in enumerate(log, start=1):
        r["event_id"] = f"EVT-{n:06d}"
    B.system = {
        "metadata": {"system_name": f"{COMPANY} Finance Sandbox (SYNTHETIC)", "schema_version": "1.0", "as_of": AS_OF,
                     "synthetic": True, "next_record_seq": seq + 1,
                     "notes": "Simulated finance/ERP state. All approvals and payments are simulated. Import is idempotent on idempotency_key."},
        "vendors": [{"vendor_id": v["vendor_id"], "name": v["name"], "status": v["status"], "payment_terms": v["payment_terms"],
                     "currency": v["currency"], "country": v["country"]} for v in B.vendors],
        "invoices": recs, "audit_log": log}
    B.sysmap = {r["invoice_id"]: r for r in recs}


# ------------------------------------------------------------------ writers
VENDOR_COLS = ["vendor_id", "name", "contact_email", "contact_phone", "country", "billing_address", "currency", "status",
               "payment_terms", "tax_id", "tax_rate", "onboarded_date"]
INVOICE_COLS = ["invoice_id", "invoice_number", "vendor_id", "vendor_name", "invoice_date", "due_date", "currency", "subtotal",
                "tax_amount", "total_amount", "po_number", "status", "document_filename", "department_id", "payment_method", "created_at"]
PO_COLS = ["po_number", "vendor_id", "department_id", "requester_id", "created_date", "approved_budget", "currency", "status",
           "line_items_json", "invoice_ids"]
EMP_COLS = ["employee_id", "first_name", "last_name", "department_id", "job_title", "email", "manager_id", "role",
            "approval_limit_usd", "can_approve_invoices", "can_authorize_payments", "status", "hire_date"]
DEP_COLS = ["department_id", "name", "cost_center", "head_employee_id", "annual_budget_usd"]
EXP_COLS = ["expense_id", "employee_id", "expense_date", "category", "amount", "currency", "description", "receipt_provided",
            "status", "approver_id", "decision_date"]


def write_csv(path: Path, cols, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_structured(B, root: Path):
    s = root / "structured"
    write_csv(s / "vendors.csv", VENDOR_COLS, B.vendors)
    write_csv(s / "invoices.csv", INVOICE_COLS, B.invoices)
    pos = [{**p, "line_items_json": json.dumps(p["line_items"], separators=(",", ":")), "invoice_ids": ";".join(p["invoice_ids"])}
           for p in B.pos]
    write_csv(s / "purchase_orders.csv", PO_COLS, pos)
    write_csv(s / "employees.csv", EMP_COLS, B.employees)
    write_csv(s / "departments.csv", DEP_COLS, B.departments)
    write_csv(s / "expense_records.csv", EXP_COLS, B.expenses)
    with open(s / "internal_system_records.json", "w", encoding="utf-8") as f:
        json.dump(B.system, f, indent=2, ensure_ascii=False)
        f.write("\n")
