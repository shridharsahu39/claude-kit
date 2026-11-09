---
name: local-data
description: Where a sensitive file goes in .claude/local/, how to name it, and what may reach the repository from it — BRDs, designs, emails, exports, registrar (CAMS, KFin) files, BSE, KRA and bank files, partner API documents and Postman collections, logs and HAR files, screenshots, test identities. Use when a file arrives to be filed, before deriving anything from a file in .claude/local/, and when deciding what a record may say about one.
---

# Filing sensitive data in `.claude/local/`

Anything sensitive that a change needs lives in `.claude/local/`, on the
developer's own machine. That means production data, registrar files, partner
documents, customer documents, designs, BRDs, logs and screenshots. Git ignores the folder, except
its README. Its contents never go into a commit, a change record, a test
fixture, a code comment, a PR, a ticket or an issue.

```text
.claude/local/
  inbox/                            drop anything new here; Claude files it below
  changes/<yyyy-mm-dd>-<slug>/      a change's private inputs, named like its record in .claude/changes/
    brd/  design/  ref/  out/
  exports/<source>-<yyyy-mm-dd>/    data exported from a site or a partner
  rta/<cams|kfin>/<period>/         mutual-fund registrar files as received
  vendor/<provider>/                partners' API documents, file specs, collections, samples
  logs/<source>-<yyyy-mm-dd>/       log exports, request dumps, HAR files
  test-data/<env>.md                UAT test identities
  archive/                          finished changes' folders and retired material
```

## Where each kind of input goes

| You have | Put it in | Name it | What may reach the repo |
| --- | --- | --- | --- |
| A BRD, PRD, change request or SOW | `changes/<record>/brd/` | As received. A new version goes beside the old (`-v2`); never overwrite one | Requirements in your own words, citing the file, its version and date |
| Figma designs, prototypes, design exports | `changes/<record>/design/` | `01-<screen>.png` in flow order; Figma links in `links.md` | Screen descriptions in `design.md`. Never the links: anyone holding a shared link may open the file |
| Copy, terms text or translations from the business | `changes/<record>/brd/` | As received | The final text, once it ships in the code |
| Emails, chats, meeting notes, helpdesk tickets | `changes/<record>/ref/` | `<yyyy-mm-dd>-<from>-<subject>` | The decision, who made it and when; not the message |
| A customer complaint or escalation | `changes/<record>/ref/` | `<yyyy-mm-dd>-<subject>` | The problem in general terms, never the customer |
| Customer documents: KYC images, PAN or Aadhaar copies, cheques, signatures, proposal or claim forms | `changes/<record>/ref/`, only when a case can't be worked without one | As received | Nothing. Delete them when the change is done; fixtures use generated images |
| A site export (CSV, XLSX, Data Import Template) from production, UAT or rehearsal | `exports/<env>-<yyyy-mm-dd>/` | The DocType per file | Counts and distributions, with the export date |
| CAMS files (WBR2, WBR4, WBR9, transaction feeds) or KFin files (MFSD201, 203, 211) | `rta/<cams or kfin>/<period>/`, such as `rta/kfin/2002-to-2026-07/` | As received | Layouts, codes, wording and signs, to build synthetic fixtures. Never a row |
| BSE reports and downloads: order status, allotments, UCC or mandate masters | `exports/bse-<env>-<yyyy-mm-dd>/` | The report's name | Counts. Never a UCC |
| KRA, bank (Finacle) or payment-gateway responses, NACH mandate files, statements | `exports/<source>-<yyyy-mm-dd>/` | As received | Shapes and counts |
| Insurers' or banks' MIS, policy and reconciliation files | `exports/<partner>-<yyyy-mm-dd>/` | As received | Counts and shapes |
| UAT test identities: test UCCs, PANs, mobiles, folios, policy or customer IDs | `test-data/<env>.md` | One file per environment | Nothing: records say "the UAT test account" |
| API documents and file specs: BSE StAR MF, CAMS, KFin, CVL KRA, banks' APIs such as Finacle, insurers, Morningstar, payment gateways, SMS and email providers | `vendor/<provider>/` | `<provider>-<document>-<version>` | The contract in your own words, citing the document and version. Partner documents are often confidential |
| Postman or Insomnia collections and environments, partners' sample requests | `vendor/<provider>/` | As received | Nothing. Strip credentials before keeping a copy; environments often hold live ones |
| SEBI or AMFI circulars | `vendor/regulators/` | `<body>-<circular>-<yyyy-mm-dd>` | The rule and its circular number |
| Log exports: Error Log, SM Proxy Log, the BSE log, relay or server logs | `logs/<source>-<yyyy-mm-dd>/` | As exported | Error messages, counts and timings. The integration logs that keep full requests and responses (SM Proxy Log, the BSE and KRA logs) are the most sensitive files here |
| HAR files, browser storage dumps, cURL commands with headers | `logs/<source>-<yyyy-mm-dd>/` | As exported | Nothing: they hold live cookies and tokens. Delete them when the change is done |
| Screenshots or recordings from production or UAT | `changes/<record>/ref/` | `<yyyy-mm-dd>-<what>` | A description. A screenshot only if every value in it is synthetic |
| Security or audit reports | `changes/<record>/ref/` | As received | Each finding in your own words |
| Your one-off scripts, query results, generated imports, reconciliations | `changes/<record>/out/` | Anything clear | A script may go in its record if it takes its inputs as arguments and holds no data. Results as counts |

**Never here, or anywhere in the repo:** credentials, keys, tokens, OTP codes,
and copies of `.env` or `site_config.json`. They stay where the app reads them:
site config, the relay's `.env`, a password manager. A script that needs one
reads it at run time and never prints it. Database dumps and site backups stay
in the site's `private/backups/`.

## Handling

- **Arrivals.** When a file arrives (in chat, as a download, in `inbox/`), file
  it by the table in the same session and say where it went. Keep its name
  unless the table gives a pattern.
- **Originals are read-only.** Write anything derived to the change's `out/`.
- **Cite, don't copy.** A record cites `.claude/local/<path>` with the file's
  version and date. It must make sense to someone who doesn't have the file.
- **Synthetic fixtures.** Test data in the repo is made up. Production files
  give only shapes: layouts, codes, wording, signs.
- **Snapshots age.** Give an export's date with every finding, and re-export
  before a release decision relies on it.
- **Worktrees.** A worktree has no copy of this folder. Read the main
  checkout's, at `"$(git rev-parse --git-common-dir)/../.claude/local"`. A
  worktree session can't write to the main checkout, so it writes derived files
  to its own `.claude/local/`, which is ignored there too. Copy anything worth
  keeping before the worktree is removed.
- **Retention.** When a change is done, move its folder to `archive/`. Keep the
  latest export of each source, and move older ones to `archive/`.
- **Don't defeat the ignore.** Never `git add -f` here. Never run `git clean -x`
  in this repo: it deletes this folder. Before a commit, `git status --short`
  shows nothing under `.claude/local/` except its README.
