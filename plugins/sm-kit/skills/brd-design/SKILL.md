---
name: brd-design
description: Combine a BRD with its design files (Figma exports, screenshots, PDFs of screens) into one change record — requirements, screen-by-screen design, acceptance criteria, QA cases and the open questions. Use when the owner hands over a BRD, designs, or both, for a new feature or a change.
argument-hint: "<yyyy-mm-dd-slug>"
---

# From a BRD and designs to a change record

The owner drops a change's inputs into the developer-local folder, which git
ignores, under the same name as the change record:

```text
.claude/local/changes/<yyyy-mm-dd>-<slug>/
  brd/       the BRD as received: PDF, DOCX, XLSX or Markdown; v1, v2… kept side by side
  design/    one PNG or PDF per screen, numbered in flow order (01-home.png, 02-amount.png),
             plus links.md for Figma or prototype links
  ref/       optional: emails, meeting notes, vendor replies
  out/       what you derive: extracted text, matrices, scratch scripts
```

If the files arrive another way (in chat, or in `.claude/local/inbox/`), move
them there first and say where. The inputs never go into the repo: the record
cites them by file name, version and date. The `local-data` skill has the
conventions.

## Steps

1. **Read everything.** PDFs with Read, a few pages at a time; Word with the
   `docx` skill; spreadsheets with the `xlsx` skill. Read every design image and
   every page of a design PDF. Note each input's version and date.
2. **Extract.**
   - Requirements as `BR-1`, `BR-2`…, each with its BRD section.
   - Screens as `S-1`, `S-2`…, each with its file or frame name: fields and
     validation, states (empty, loading, error, success), copy, actions and
     where each leads.
3. **Ground both in the code.** For each requirement and screen, find what it
   touches in each repository involved (for mutual funds: the MF app, the relay
   and the frontend): endpoints, DocTypes, jobs, pages.
   Mark each as exists, changes or new. Designs often assume data or states the
   system doesn't have.
4. **Cross-check.** List:
   - gaps: a requirement no screen shows, or a screen element no requirement
     asks for;
   - conflicts: BRD against design, either against current behaviour, a
     regulation, or a standing rule in the guidance of a repository it touches
     (customer-facing words, theme colours, no hidden text);
   - assumptions you had to make.
5. **Security and data.** Note what personal or financial data is captured,
   shown or sent, who may see it, which roles act, and what needs consent or an
   audit trail. This feeds the change's security check.
6. **Write the record** (start it with the `change` skill if it doesn't exist):
   - `spec.md`: scope; a Sources table (file, version, date); requirements
     `BR-n` with their source; acceptance criteria `AC-n`, each tracing to its
     `BR` and `S`; decisions.
   - `design.md`: per screen, its purpose, fields and validation, states, copy
     and actions; then the API contract, data-model changes, jobs and edge
     cases.
   - `qa.md`: test cases from the acceptance criteria, security cases included.
   - `progress.md`: the task list.
   - In `spec.md`, a coverage table: `BR` → `S` → `AC` → `QA`, with every gap
     marked.
7. **Ask before building.** Put the open questions to the owner in plain words,
   each with your recommendation. Record the answers as decisions (`D-1`…) and
   build only after that.

## Rules

- Where the BRD and the design disagree, don't pick one silently: ask.
- Keep customer data, real screenshots and confidential figures out of the
  record. Describe a screen; don't paste it.
- A later BRD or design version goes in beside the old one. Re-run the
  cross-check and record what changed as a decision.
