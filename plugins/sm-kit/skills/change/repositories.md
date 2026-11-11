# The team's repositories

All but the last table are private repositories in the team's GitHub
organisation. Each has its own `CLAUDE.md` and `.claude/`; read them
before editing there. Where each is checked out on a machine is in that
developer's `~/.claude/CLAUDE.md`.

A change's branch starts from the repository's base branch, and its PR goes
back into it.

## Products and platform

| Repository | What it is | Base branch |
| --- | --- | --- |
| `mutual_fund` | Mutual funds: BSE StAR MF, registrar (CAMS and KFin) processing, portfolios. Holds the records of MF changes that span the relay and the frontend | `v2` (`develop` is an old, unused line) |
| `sbm` | SBM Bank's provider strategies and Finacle integrations | `develop` |
| `sales` | The sales portal backend: leads, partners, targets, DIY Life | `feat-frappe-v16`, the Frappe 16 line; `develop` still takes fixes for the older line |
| `sprint_money_core` | OTP, consent, OAuth tokens, messaging, logging, the SM Proxy Log | `feat-frappe-v16`, as for `sales` |
| `fixed_deposit` | Suryoday's fixed-deposit journey | `develop` |
| `ktk` | Karnataka Bank's app | `develop` |
| `masters` | Insurer reference data | `develop` (a `feat-frappe-v16` line also exists) |
| `global_customer_sso` | Customer single sign-on for the bank channels | `develop` |
| `insurance_crm_integrations` | Insurance partners' API integrations | `develop` |
| `sprint-money-backend` | The Node relay: one service per product, in front of the Frappe apps | `develop` |
| `sprint-money-frontend` | The React apps, white-labelled per bank | `develop` |

## Other Frappe apps

| Repository | What it is | Base branch |
| --- | --- | --- |
| `campaign_ops` | Campaign operations; the Frappe scaffold only | `develop` |
| `corporate_crm` | A CRM for banks selling to corporates; schema only | `develop` |
| `credit_life_protect` | Karnataka Bank's group credit-life journey | `develop` |
| `csb` | CSB Bank: seed data for the sales app | `develop` |
| `customer_360` | Bank staff's customer view and service requests | `develop` |
| `fino` | Fino Bank; the Frappe scaffold only | `develop` |
| `frappe_admin_module` | Desk dashboards built from tiles | `version-16` |
| `frappe_saml_integration` | Sign-in through a SAML identity provider | `develop` |
| `guaranteed_income` | Guaranteed-income plans' Frappe side | `develop` |
| `health` | Health insurance's Frappe side | `develop` |
| `loan_against_securities` | Loans against securities; the Frappe scaffold only | `develop` |
| `mutual_fund_new` | A partial re-model of the MF schema; not the live app, and it can't share a site with `mutual_fund` | `develop` |
| `sm_whatsapp` | WhatsApp journeys and messaging | `develop` |
| `spm_group_products` | Group products: Bajaj Allianz Personal Accident | `develop` |
| `suryoday` | Suryoday Bank's API gateway integration | `develop` |
| `term` | Term insurance's Frappe side | `develop` |
| `timedesk` | Department routing and turnaround tracking on Helpdesk | `develop` |
| `vehicle` | Motor insurance | `develop` |

## Outside the organisation

Team repositories kept elsewhere. `tools/sync.py` accepts them through its
`TEAM_OUTSIDE` list. None of them is a Frappe app: each one's own `qa` skill
replaces the Frappe parts of the kit's `qa` and `performance` skills.

| Repository | What it is | Base branch |
| --- | --- | --- |
| `fseduventures/classmanager-espo` | ClassManager: a FastAPI monolith (`server/`) and a React UI (`frontend/`) for coaching institutes, hosted on MilesWeb (cPanel Passenger, MySQL). Alembic migrations; SQLite for tests, plus a local MariaDB. Its WhatsApp client is in `client-side/whatsapp/` | `main` |
