"""Core record builders for the synthetic enterprise dataset (stdlib only)."""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta
from decimal import Decimal as D, ROUND_HALF_UP

from dataset_text import (APPROVAL_LIMITS, AS_OF, COMPANY_DOMAIN, FX_TO_USD, PO_TOLERANCE, ROLE_RANK,
                          SEED, TIER_BOUNDS)

ASOF = date.fromisoformat(AS_OF)


def q2(x) -> D:
    return D(x).quantize(D("0.01"), ROUND_HALF_UP)


def usd(amount, cur) -> D:
    return q2(D(amount) * FX_TO_USD[cur])


def norm_num(s: str) -> str:
    return "".join(ch for ch in (s or "").upper() if ch.isalnum())


def idem_key(vendor_id: str, number: str) -> str:
    return hashlib.sha1(f"{vendor_id}|{norm_num(number)}".encode()).hexdigest()[:16]


def base_tier(total_usd: D):
    for bound, tier, role in TIER_BOUNDS:
        if bound is None or total_usd <= bound:
            return tier, role
    raise AssertionError


def required_tier(total_usd: D, has_po: bool):
    tier, _ = base_tier(total_usd)
    if not has_po:
        tier = min(tier + 1, 4)
    role = [r for _, t, r in TIER_BOUNDS if t == tier][0]
    return tier, role


# ----------------------------------------------------------------- static master data
DEPARTMENTS = [
    ("DEP-001", "Finance", "CC-1000", "EMP-001", 1800000), ("DEP-002", "Engineering", "CC-2000", "EMP-005", 4200000),
    ("DEP-003", "Operations", "CC-3000", "EMP-008", 3100000), ("DEP-004", "Marketing", "CC-4000", "EMP-011", 1500000),
    ("DEP-005", "Human Resources", "CC-5000", "EMP-014", 900000), ("DEP-006", "IT", "CC-6000", "EMP-016", 2600000),
    ("DEP-007", "Procurement", "CC-7000", "EMP-021", 700000)]

EMPLOYEES = [  # id, first, last, dept, title, role, manager, status
    (1, "Elena", "Voss", "DEP-001", "Chief Financial Officer", "cfo", None, "active"),
    (2, "Daniel", "Okafor", "DEP-001", "Finance Manager", "finance_manager", 1, "active"),
    (3, "Sofia", "Marlowe", "DEP-001", "Accounts Payable Clerk", "finance_clerk", 2, "active"),
    (4, "Hiro", "Tanabe", "DEP-001", "Accounts Payable Clerk", "finance_clerk", 2, "active"),
    (5, "Grace", "Lindqvist", "DEP-002", "Director of Engineering", "director", 1, "active"),
    (6, "Rahul", "Mehta", "DEP-002", "Engineering Manager", "manager", 5, "active"),
    (7, "Chloe", "Bennett", "DEP-002", "Software Engineer", "employee", 6, "active"),
    (8, "Omar", "Haddad", "DEP-003", "Director of Operations", "director", 1, "active"),
    (9, "Lena", "Fischer", "DEP-003", "Operations Manager", "manager", 8, "active"),
    (10, "Tomas", "Novak", "DEP-003", "Logistics Coordinator", "employee", 9, "active"),
    (11, "Isabel", "Cortez", "DEP-004", "Marketing Director", "director", 1, "active"),
    (12, "Jamal", "Pierce", "DEP-004", "Marketing Manager", "manager", 11, "active"),
    (13, "Yuki", "Sato", "DEP-004", "Campaign Specialist", "employee", 12, "active"),
    (14, "Naomi", "Brooks", "DEP-005", "HR Director", "director", 1, "active"),
    (15, "Victor", "Alvarez", "DEP-005", "HR Manager", "manager", 14, "on_leave"),
    (16, "Anika", "Rao", "DEP-006", "IT Director", "director", 1, "active"),
    (17, "Ben", "Carter", "DEP-006", "IT Manager", "manager", 16, "active"),
    (18, "Mia", "Johansson", "DEP-006", "Systems Administrator", "employee", 17, "active"),
    (19, "Paula", "Reyes", "DEP-007", "Procurement Officer", "procurement_officer", 21, "active"),
    (20, "Gregory", "Hale", "DEP-004", "Former Marketing Manager", "manager", 11, "terminated"),
    (21, "Nadia", "Petrov", "DEP-007", "Procurement Manager", "manager", 1, "active"),
]

TAX = {"US": D("0.08"), "DE": D("0.19"), "GB": D("0.20"), "CA": D("0.13"), "IN": D("0.18")}
TAX_TYPE = {"US": "EIN", "DE": "VAT", "GB": "VAT", "CA": "BN", "IN": "GSTIN"}
PAY_METHODS = {"USD": ["ach", "check", "card"], "EUR": ["sepa", "wire"], "GBP": ["bacs", "wire"],
               "CAD": ["eft", "wire"], "INR": ["neft", "wire"]}
PHONE = {"US": "+1-555-01{n:02d}", "CA": "+1-555-01{n:02d}", "GB": "+44 20 7946 0{n:03d}",
         "DE": "+49 30 55501{n:02d}", "IN": "+91 99999 0{n:04d}"}

CATALOG = {
    "office": [("Printer paper A4 (case of 10 reams)", 42), ("Ergonomic office chair", 289), ("Toner cartridge, high yield", 118)],
    "consulting": [("Senior consultant hours", 165), ("Project management hours", 140), ("Workshop facilitation (day rate)", 1450)],
    "logistics": [("Pallet freight, regional", 385), ("Container handling fee", 620), ("Warehouse storage (per pallet/month)", 34)],
    "printing": [("Brochure print run (500 units)", 460), ("Business cards (box of 250)", 38), ("Large-format banner", 215)],
    "facilities": [("Facility maintenance visit", 340), ("HVAC filter replacement", 95), ("Landscaping service (monthly)", 780)],
    "hosting": [("Managed cloud hosting (monthly)", 2450), ("Premium support plan (monthly)", 900), ("Additional storage block (1 TB)", 120)],
    "security": [("Security guard shift (8h)", 260), ("CCTV monitoring (monthly)", 640), ("Access badge batch (50)", 310)],
    "travel": [("Business airfare, economy", 520), ("Hotel night, business rate", 175), ("Ground transport package", 95)],
    "analytics": [("Analytics platform seat (annual)", 1200), ("Data engineering hours", 120), ("Dashboard build (fixed fee)", 3800)],
    "staffing": [("Temp admin staff (weekly)", 980), ("Recruiter placement fee", 5500), ("Background checks (each)", 65)],
    "leasing": [("Forklift lease (monthly)", 1350), ("Delivery van lease (monthly)", 920), ("Pallet jack lease (monthly)", 110)],
    "telecom": [("Business internet 1 Gbps (monthly)", 890), ("SIP trunk lines (monthly)", 420), ("Mobile plan (per line/month)", 48)],
    "catering": [("Team lunch catering (per head)", 24), ("Executive boardroom catering", 380), ("Event reception package", 2100)],
    "software": [("Design software licence (annual)", 520), ("DevOps tooling seat (annual)", 780), ("Security suite licence (annual)", 95)],
    "marketing": [("Social media campaign", 3200), ("Content writing (per article)", 260), ("Brand photography day", 1800)],
    "legal": [("Contract review hours", 310), ("Compliance advisory hours", 340), ("Trademark filing", 1250)],
    "maintenance": [("Machine servicing visit", 450), ("Replacement parts kit", 380), ("Emergency call-out", 690)],
    "training": [("Leadership workshop seat", 890), ("Safety certification course", 240), ("E-learning licence (annual)", 75)],
    "cleaning": [("Office cleaning (monthly)", 1150), ("Deep clean, per floor", 430), ("Washroom supplies restock", 160)],
    "hardware": [("Business laptop 14in", 1380), ("27in monitor", 340), ("Docking station", 185)],
    "courier": [("Same-day courier run", 58), ("International parcel, 5kg", 96), ("Document pick-up (monthly)", 120)],
    "datacentre": [("Rack space (per unit/month)", 165), ("Cross-connect (monthly)", 210), ("Remote hands (per hour)", 95)],
}

# name, country, currency, status, category, depts, terms, street, city, postcode
VENDOR_SPECS = [
    ("Apex Office Supplies Ltd", "US", "USD", "active", "office", ["DEP-003", "DEP-001", "DEP-005"], 30, "1200 Commerce Way", "Columbus", "OH 43004"),
    ("Apex Office Supply Ltd.", "US", "USD", "pending", "office", ["DEP-003"], 30, "88 Harbor Street", "Columbus", "OH 43215"),
    ("Brightwave Consulting LLC", "US", "USD", "active", "consulting", ["DEP-002", "DEP-004"], 30, "410 Market Square", "Austin", "TX 78701"),
    ("Bright Wave Consulting Inc", "US", "USD", "active", "consulting", ["DEP-002", "DEP-004"], 45, "77 Lakeview Drive", "Denver", "CO 80202"),
    ("Cobalt Logistics GmbH", "DE", "EUR", "active", "logistics", ["DEP-003"], 30, "Hafenstrasse 14", "Hamburg", "20457"),
    ("Cobalt Logistik GmbH", "DE", "EUR", "suspended", "logistics", ["DEP-003"], 30, "Industriering 9", "Bremen", "28195"),
    ("Delta Print & Packaging Co", "US", "USD", "active", "printing", ["DEP-004", "DEP-003"], 30, "301 Mill Road", "Dayton", "OH 45402"),
    ("Evergreen Facilities Services", "CA", "CAD", "active", "facilities", ["DEP-003", "DEP-006"], 30, "55 Birch Avenue", "Calgary", "AB T2P 1J9"),
    ("Fenwick Cloud Hosting Ltd", "GB", "GBP", "active", "hosting", ["DEP-002", "DEP-006"], 30, "12 Canal Quay", "Manchester", "M1 4BT"),
    ("Granite Peak Security LLC", "US", "USD", "active", "security", ["DEP-003", "DEP-006"], 30, "9 Summit Park", "Boise", "ID 83702"),
    ("Harborline Travel Group", "GB", "GBP", "active", "travel", ["DEP-004", "DEP-001", "DEP-005"], 30, "3 Dockside Row", "Bristol", "BS1 5TY"),
    ("Indigo Analytics Pvt Ltd", "IN", "INR", "active", "analytics", ["DEP-002", "DEP-004"], 45, "Plot 22, Tech Park Road", "Pune", "411057"),
    ("Juniper Staffing Solutions", "US", "USD", "pending", "staffing", ["DEP-005"], 30, "640 Alder Street", "Portland", "OR 97204"),
    ("Keystone Equipment Leasing", "US", "USD", "active", "leasing", ["DEP-003"], 45, "18 Quarry Lane", "Pittsburgh", "PA 15222"),
    ("Lumen Telecom Services", "CA", "CAD", "active", "telecom", ["DEP-006"], 30, "200 Bay Centre", "Toronto", "ON M5J 2T3"),
    ("Maple & Pine Catering", "CA", "CAD", "active", "catering", ["DEP-004", "DEP-005"], 15, "14 Orchard Close", "Ottawa", "ON K1P 5G4"),
    ("Nimbus Software Licensing GmbH", "DE", "EUR", "active", "software", ["DEP-002", "DEP-006"], 30, "Lindenallee 7", "Munich", "80331"),
    ("Orchid Marketing Studio", "GB", "GBP", "active", "marketing", ["DEP-004"], 30, "41 Foundry Mews", "London", "EC2A 3QR"),
    ("Pinnacle Legal Advisors LLP", "GB", "GBP", "active", "legal", ["DEP-001", "DEP-007"], 30, "8 Chancery Walk", "Leeds", "LS1 4AP"),
    ("Quartz Maintenance Co", "US", "USD", "suspended", "maintenance", ["DEP-003"], 30, "77 Foundry Park", "Toledo", "OH 43604"),
    ("Redwood IT Hardware Inc", "US", "USD", "active", "hardware", ["DEP-006", "DEP-002"], 30, "5500 Cedar Parkway", "Raleigh", "NC 27601"),
    ("Sterling Courier Services Ltd", "GB", "GBP", "active", "courier", ["DEP-003", "DEP-004"], 15, "26 Wharf Road", "Glasgow", "G1 2AB"),
    ("Tandem Training Institute", "US", "USD", "pending", "training", ["DEP-005"], 30, "120 College Row", "Madison", "WI 53703"),
    ("Umbra Cleaning Services", "US", "USD", "active", "cleaning", ["DEP-003"], 30, "47 Birchwood Court", "Tampa", "FL 33602"),
    ("Vantage Data Centers India Pvt Ltd", "IN", "INR", "suspended", "datacentre", ["DEP-006"], 60, "Sector 62, Infocity", "Noida", "201309"),
    ("Willow Creek Printing", "CA", "CAD", "pending", "printing", ["DEP-004"], 30, "9 Mill Pond Road", "Halifax", "NS B3J 1S9"),
]


class Builder:
    def __init__(self):
        self.rng = random.Random(SEED)
        self.vendors, self.employees, self.departments = [], [], []
        self.pos, self.invoices, self.expenses = [], [], []
        self.fixtures: dict = {}
        self.anomalies: list = []
        self.docs: list = []
        self.system_overrides: dict = {}      # invoice_id -> dict of overrides for the internal record
        self.in_system_force: set = set()     # invoice_ids that must exist in the internal system
        self.not_in_system_force: set = set()
        self.build_masters()

    # ------------------------------------------------------------ masters
    def build_masters(self):
        for d in DEPARTMENTS:
            self.departments.append({"department_id": d[0], "name": d[1], "cost_center": d[2],
                                     "head_employee_id": d[3], "annual_budget_usd": d[4]})
        for i, (n, f, l, dept, title, role, mgr, status) in enumerate(EMPLOYEES):
            self.employees.append({
                "employee_id": f"EMP-{n:03d}", "first_name": f, "last_name": l, "department_id": dept,
                "job_title": title, "email": f"{f.lower()}.{l.lower()}@{COMPANY_DOMAIN}",
                "manager_id": f"EMP-{mgr:03d}" if mgr else "", "role": role,
                "approval_limit_usd": APPROVAL_LIMITS[role],
                "can_approve_invoices": str(role in ROLE_RANK).lower(),
                "can_authorize_payments": str(role in ("finance_manager", "cfo")).lower(),
                "status": status, "hire_date": (date(2018, 1, 15) + timedelta(days=97 * i)).isoformat()})
        for i, (name, cc, cur, status, cat, depts, terms, street, city, pc) in enumerate(VENDOR_SPECS, start=1):
            slug = "".join(ch for ch in name.lower() if ch.isalpha())
            self.vendors.append({
                "vendor_id": f"VND-{i:03d}", "name": name, "contact_email": f"ar@{slug}.example",
                "contact_phone": PHONE[cc].format(n=i), "country": cc,
                "billing_address": f"{street}, {city}, {pc}, {cc} (FICTIONAL)", "currency": cur,
                "status": status, "payment_terms": f"Net {terms}",
                "tax_id": f"SYN-{TAX_TYPE[cc]}-{i:08d}", "tax_rate": str(TAX[cc]),
                "onboarded_date": (date(2024, 3, 1) + timedelta(days=41 * i)).isoformat(),
                "_cat": cat, "_depts": depts, "_terms": terms})
        self.vmap = {v["vendor_id"]: v for v in self.vendors}
        self.emap = {e["employee_id"]: e for e in self.employees}

    def dept_name(self, dept_id):
        return next(d['name'] for d in self.departments if d['department_id'] == dept_id)

    def V(self, n):  # vendor by number
        return self.vmap[f"VND-{n:03d}"]

    # ------------------------------------------------------------ helpers
    def lines_total(self, lines):
        return q2(sum(D(q) * D(p) for _, q, p in lines))

    def mk_lines(self, lines):
        return [{"description": d, "quantity": int(q), "unit_price": str(q2(p)),
                 "line_total": str(q2(D(q) * D(p)))} for d, q, p in lines]

    def new_po(self, vendor_id, dept, requester, lines, status, created, fixture=None, budget=None):
        v = self.vmap[vendor_id]
        sub = self.lines_total(lines)
        po = {"po_number": f"PO-2026-{len(self.pos) + 1:04d}", "vendor_id": vendor_id, "department_id": dept,
              "requester_id": requester, "created_date": created, "approved_budget": str(budget or q2(sub * (1 + D(v['tax_rate'])))),
              "currency": v["currency"], "status": status, "line_items": self.mk_lines(lines), "invoice_ids": []}
        self.pos.append(po)
        self.pomap = {p["po_number"]: p for p in self.pos}
        return po

    def new_invoice(self, vendor_id, lines, inv_date, status, po=None, dept=None, number=None, fixture=None, doc=None):
        v = self.vmap[vendor_id]
        idx = len(self.invoices) + 1
        inv_date = inv_date if isinstance(inv_date, date) else date.fromisoformat(inv_date)
        sub = self.lines_total(lines)
        tax = q2(sub * D(v["tax_rate"]))
        rng = self.rng
        dept = dept or (po["department_id"] if po else rng.choice(v["_depts"]))
        inv = {
            "invoice_id": f"INV-{idx:04d}",
            "invoice_number": number if number is not None else f"{v['name'][:3].upper()}-{inv_date:%y%m}-{idx:04d}",
            "vendor_id": vendor_id, "vendor_name": v["name"], "invoice_date": inv_date.isoformat(),
            "due_date": (inv_date + timedelta(days=v["_terms"])).isoformat(), "currency": v["currency"],
            "subtotal": str(sub), "tax_amount": str(tax), "total_amount": str(sub + tax),
            "po_number": po["po_number"] if po else "", "status": status, "document_filename": "",
            "department_id": dept, "payment_method": rng.choice(PAY_METHODS[v["currency"]]),
            "created_at": (datetime(inv_date.year, inv_date.month, inv_date.day, rng.randint(7, 17), rng.randint(0, 59), rng.randint(0, 59))
                           + timedelta(days=rng.randint(0, 2))).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "_lines": [{"description": d, "quantity": int(q), "unit_price": q2(p)} for d, q, p in lines],
            "_fixture": fixture, "_doc": None, "_notes": ""}
        self.invoices.append(inv)
        self.imap = {i["invoice_id"]: i for i in self.invoices}
        if fixture:
            self.fixtures[fixture] = inv
        if po:
            po["invoice_ids"].append(inv["invoice_id"])
        return inv

    def anomaly(self, kind, records, description, documents=()):
        self.anomalies.append({"anomaly_id": f"ANOM-{len(self.anomalies) + 1:03d}", "type": kind,
                               "records": list(records), "documents": list(documents), "description": description})

    # ------------------------------------------------------------ ordinary data
    def pick_lines(self, v, small=False, pieces=None):
        rng = self.rng
        items = CATALOG[v["_cat"]]
        factor = D(str(round(rng.uniform(0.92, 1.10), 2)))
        cur = v["currency"]
        chosen = rng.sample(items, k=rng.randint(1, 3)) if not small else []
        if small:
            ok = [it for it in items if D(it[1]) * D("1.2") <= D("440")]
            if not ok:
                ok = [min(items, key=lambda x: x[1])]
            chosen = [rng.choice(ok)]
        lines = []
        for desc, p_usd in chosen:
            price = q2(D(p_usd) * factor / FX_TO_USD[cur])
            if cur == "INR":
                price = D(int(price / 10) * 10)
            if small:
                maxq = max(1, int(D("430") / (D(p_usd) * D("1.2"))))
                qty = rng.randint(1, min(maxq, 8))
            else:
                qty = (rng.randint(5, 60) if p_usd < 100 else rng.randint(2, 25) if p_usd < 500
                       else rng.randint(1, 12) if p_usd < 2000 else rng.randint(1, 4))
            lines.append((desc, qty, price))
        return lines

    def date_for_status(self, status, terms):
        rng = self.rng
        if status == "paid":
            return date(2026, 1, 5) + timedelta(days=rng.randint(0, 200))
        if status == "overdue":
            latest = date(2026, 9, 24) - timedelta(days=terms)
            return latest - timedelta(days=rng.randint(0, 40))
        if status in ("approved",):
            return ASOF - timedelta(days=rng.randint(4, max(5, terms - 1)))
        if status in ("pending_approval", "received"):
            return ASOF - timedelta(days=rng.randint(3, max(4, min(25, terms - 1))))
        if status == "rejected":
            return date(2026, 5, 1) + timedelta(days=rng.randint(0, 120))
        return date(2026, 6, 1) + timedelta(days=rng.randint(0, 85))   # disputed

    def status_for_vendor(self, v):
        rng = self.rng
        if v["status"] == "pending":
            return "received"
        if v["status"] == "suspended" or v["name"].startswith("Redwood"):
            return rng.choice(["paid"] * 4 + ["rejected", "disputed"])
        return rng.choices(["paid", "approved", "pending_approval", "received", "overdue", "rejected", "disputed"],
                           [35, 14, 12, 10, 14, 5, 10])[0]

    def build_ordinary(self, n_po=28, n_total=100):
        rng = self.rng
        eligible = [v for v in self.vendors if v["status"] in ("active", "suspended")]
        weights = [1 if v["status"] == "suspended" else 3 for v in eligible]
        planned = []
        for i in range(n_po):
            v = rng.choices(eligible, weights)[0]
            dept = rng.choice(v["_depts"])
            cands = [e["employee_id"] for e in self.employees if e["department_id"] == dept and e["status"] == "active"
                     and e["role"] in ("employee", "manager", "director", "finance_clerk", "procurement_officer")]
            lines = self.pick_lines(v)
            planned.append((v, dept, rng.choice(cands), lines))
        # last four POs: 2 draft, 2 cancelled (never invoiced); one cancelled PO requested by the terminated employee
        specials = {n_po - 4: "draft", n_po - 3: "draft", n_po - 2: "cancelled", n_po - 1: "cancelled"}
        for i, (v, dept, req, lines) in enumerate(planned):
            st = specials.get(i, "approved")
            if i == n_po - 2:
                req = "EMP-020"
            po = self.new_po(v["vendor_id"], dept, req, lines, st, "2026-01-02")
            if st in ("draft", "cancelled"):
                po["created_date"] = (date(2026, 2, 1) + timedelta(days=rng.randint(0, 180))).isoformat()
                continue
            status_list = []
            two = len(lines) >= 2 or (len(lines) == 1 and lines[0][1] >= 4)
            if two and rng.random() < 0.38:
                if len(lines) >= 2:
                    parts = [lines[:1], lines[1:]]
                else:
                    q1 = lines[0][1] // 2
                    parts = [[(lines[0][0], q1, lines[0][2])], [(lines[0][0], lines[0][1] - q1, lines[0][2])]]
                st2 = self.status_for_vendor(v)
                d2 = self.date_for_status(st2, v["_terms"])
                d1 = max(date(2026, 1, 5), d2 - timedelta(days=rng.randint(20, 70)))
                invs = [(parts[0], "paid", d1), (parts[1], st2, d2)]
            else:
                st1 = self.status_for_vendor(v)
                invs = [(lines, st1, self.date_for_status(st1, v["_terms"]))]
            first = min(d for _, _, d in invs)
            po["created_date"] = max(date(2026, 1, 2), first - timedelta(days=rng.randint(7, 35))).isoformat()
            for ls, st_, d_ in invs:
                self.new_invoice(v["vendor_id"], ls, d_, st_, po=po)
        # no-PO ordinary invoices (<= ~500 USD equivalent)
        while len(self.invoices) < n_total:
            v = rng.choice(self.vendors)
            if v["name"].startswith("Redwood") and rng.random() < 0.8:
                continue
            st = self.status_for_vendor(v)
            self.new_invoice(v["vendor_id"], self.pick_lines(v, small=True), self.date_for_status(st, v["_terms"]), st)
        # Redwood: keep ordinary invoices before the "latest" fixture date
        for inv in self.invoices:
            assert not (inv["vendor_id"] == "VND-021" and inv["invoice_date"] > "2026-08-31"), inv["invoice_id"]
        self.n_ordinary = len(self.invoices)

    # ------------------------------------------------------------ assessment helpers (policy engine for ground truth)
    def po_flags(self, inv, historical=False):
        if not inv["po_number"]:
            return ["NO_PO"]
        po = self.pomap.get(inv["po_number"])
        if not po:
            return ["PO_NOT_FOUND"]
        flags = []
        if po["vendor_id"] != inv["vendor_id"]:
            flags.append("PO_VENDOR_MISMATCH")
        if not historical and po["status"] not in ("approved", "partially_invoiced"):
            flags.append("PO_CANCELLED")
        others = sum(D(i["total_amount"]) for i in self.invoices if i["po_number"] == po["po_number"]
                     and i["invoice_id"] != inv["invoice_id"] and i["status"] != "rejected" and i["currency"] == po["currency"])
        if D(inv["total_amount"]) + others > D(po["approved_budget"]) + PO_TOLERANCE:
            flags.append("PO_OVERRUN")
        return flags

    def approval_requirement(self, inv, historical=False):
        v = self.vmap[inv["vendor_id"]]
        tot_usd = usd(inv["total_amount"], inv["currency"])
        flags = self.po_flags(inv, historical)
        po_clean = not any(f.startswith("PO_") for f in flags) and "NO_PO" not in flags
        tier, role = required_tier(tot_usd, bool(inv["po_number"]) and po_clean)
        blocked = [f for f in flags if f != "NO_PO"]
        if v["status"] == "pending":
            blocked.append("VENDOR_PENDING")
        if v["status"] == "suspended" and not historical:
            blocked.append("VENDOR_SUSPENDED")
        return {"total_usd": tot_usd, "tier": tier, "role": role, "flags": flags, "blocked_by": blocked}

    def eligible_approvers(self, inv, tier_role, historical=False):
        if tier_role is None:
            return []
        po = self.pomap.get(inv["po_number"]) if inv["po_number"] else None
        need = ROLE_RANK[tier_role]
        tot = usd(inv["total_amount"], inv["currency"])
        out = []
        for e in self.employees:
            r = ROLE_RANK.get(e["role"], 0)
            if e["status"] != "active" or r < need or e["approval_limit_usd"] < tot:
                continue
            if po and po["requester_id"] == e["employee_id"]:
                continue
            if r <= 2 and e["department_id"] != inv["department_id"]:
                continue
            out.append(e["employee_id"])
        return out
