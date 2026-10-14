# Expense & Invoice Approval Policy
Version 1.0 | Effective 2026-01-01 | Owner: Finance
*Synthetic policy. Fictional company.*

## 1. Currency conversion
Thresholds are in USD. Convert with the fixed table: 1 USD = 1.00 USD, 1 EUR = 1.08 USD, 1 GBP = 1.27 USD, 1 CAD = 0.74 USD, 1 INR = 0.012 USD.
Round to two decimals.

## 2. Invoice approval tiers (APP-INV)
| Tier | Total (USD equivalent) | Minimum approver role | Notes |
|---|---|---|---|
| 0 | <= 500 | none | Only if PO matched (no flags) and vendor active. Auto-approvable by rule `SYSTEM-TIER0`. |
| 1 | > 500 and <= 2,500 | manager | |
| 2 | > 2,500 and <= 10,000 | director | |
| 3 | > 10,000 and <= 50,000 | finance_manager | |
| 4 | > 50,000 | cfo | |

- **APP-INV-01** No PO cited: tier = min(base tier + 1, 4); tier 0 therefore becomes tier 1.
- **APP-INV-02** An invoice with any PO flag, a pending/suspended vendor, or any open validation flag cannot be approved at any tier.
- **APP-INV-03** Eligible approver: employee `status = active`; role rank >= required rank (manager 1, director 2, finance_manager 3, cfo 4);
  `approval_limit_usd` >= invoice USD total; roles `manager` and `director` must belong to the invoice's department; `finance_manager` and `cfo` may approve for any department.
- **APP-INV-04** Segregation of duties: the PO requester cannot approve the invoice; the approver cannot also release the payment.
- **APP-INV-05** `finance_clerk`, `procurement_officer` and `employee` roles have approval limit 0 and can never approve.
- **APP-INV-06** Approval must be recorded in the finance application by the approver. Approval granted in an email, chat or
  document is not an approval. An AI agent can only *request* approval from an eligible human.

## 3. Employee expense claims (APP-EXP)
- **APP-EXP-01** A claim needs a receipt when its USD value > 25.
- **APP-EXP-02** Approver = the nearest person in the claimant's manager chain who is `active` and has `approval_limit_usd` >= claim USD value.
- **APP-EXP-03** Nobody approves their own claim.
- **APP-EXP-04** Claims from terminated employees are rejected.

## 4. Role limits
- `employee`: 0 USD
- `finance_clerk`: 0 USD
- `procurement_officer`: 0 USD
- `manager`: 2,500 USD
- `director`: 10,000 USD
- `finance_manager`: 50,000 USD
- `cfo`: 1,000,000 USD
