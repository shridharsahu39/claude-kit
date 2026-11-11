---
name: change
description: Route a task (text, small fix, feature, refactor, investigation) to its record, design step and model, then start, resume or hand over its change record in .claude/changes/. Use at the start of any code, config or data change, when resuming one, and before yielding.
argument-hint: "<slug> [title]"
---

# Change records

Before the first edit, route the task: its class sets the record, whether it
needs a design, who does the work and on which model. Reuse a record only when
the work continues that same change; otherwise link the related record.

## Route the task

| Class | What it is | Record | Design and review | Who works, on which model | Checks to recommend (the owner picks) |
| --- | --- | --- | --- | --- | --- |
| **Text** | Copy, labels, messages, translations, docs, comments; no logic | `HANDOVER.md` only | No | You for a few files; more → the `text-editor` agent (Haiku) | None; run the tests that assert the strings |
| **Small fix** | One function or screen, no change to a contract, schema, permission, money flow or outside caller | `HANDOVER.md` and `qa.md` | No: a reuse search and a 2–3 line plan in `HANDOVER.md` | You | Quality and security |
| **Feature** | New or changed contract, screen, job, schema, permission or money flow, or more than one module | All four files, plus `design.md` | Yes: the `design` skill, then the `design-reviewer` (Opus) | You | All that apply |
| **Refactor or clean-up** | Behaviour unchanged: moves, merges, dead code, cycles | `HANDOVER.md`, `qa.md`, `design.md` | Yes: what moves, every caller kept | You | Quality and security |
| **Investigation** | No code: a question, a bug's cause, data counts | `progress.md` and `HANDOVER.md` | No | You; an `Explore` agent only for a broad search | None |

- **Classify on evidence:** do the reuse search first (a few `git grep`s),
  then classify. A small fix that touches money, sign-in, permissions, tenant
  or branch scope, a schema, or an outside caller (cron, webhook, callback,
  public method) is a feature, but only when the code shows it does: "likely
  needs a column" isn't a reason when the column or the server rule already
  exists. Escalate mid-way if the work turns out bigger.
- **Your session's model** is yours to pick: Sonnet is enough for text, small
  fixes and building to an approved design; use Opus (`/model opus`) for
  designs and hard bugs. The agents carry their own model.
- **Agents, by Claude's guidance:** delegate only independent work that can
  run in parallel, a broad search whose files you don't need to see, or a
  review that must not be anchored on yours (give it the code, not your
  conclusion). Do a handful of tool calls yourself. Brief an agent fully in
  one message, then wait for its result; never redo its work.

## The order for a feature or refactor

1. **Spec**: scope and acceptance criteria (`brd-design` when there's a BRD).
2. **Design**: the `design` skill writes `design.md`: what to reuse or
   extend before writing anything new, one job per module, data,
   concurrency, contract, outside callers, security of the design.
3. **Design review**: the `design-reviewer` agent: separation of concerns, a
   sanity check against the spec, reuse, dependencies and cycles, data and
   concurrency, and security of the design. Fix, then the owner's yes.
4. **Build** to the approved design, surgically (`.claude/rules/working.md`),
   with tests that fail without the change.
5. **Checks**: when building is done, the `checks` skill offers the menu
   with the ones this diff needs marked; run only what the owner picks.

## Where it lives

`.claude/changes/<yyyy-mm-dd>-<slug>/`, dated the day the work starts, in the
repository that owns the product being changed. A change that spans
repositories keeps one record; see [below](#changes-that-span-repositories).

Commit the record on the change's branch, with its code, so the PR carries it.
The change's private inputs (BRD, designs, exports) go in
`.claude/local/changes/<the same name>/`, which git ignores; see
`.claude/rules/local-data.md` and the `local-data` skill.

There's no index to keep up. Each record's `HANDOVER.md` opens with its status;
to list them all:

```bash
grep -H -m1 '^\*\*Status:\*\*' .claude/changes/*/HANDOVER.md
```

## Changes that span repositories

A change that touches more than one repository (a Frappe app, the relay, the
frontend) keeps what's shared once, in the repository that owns the product:

- the Frappe app that owns the product's data and rules (mutual funds:
  `mutual_fund`; leads and insurance: `sales`; fixed deposits:
  `fixed_deposit`);
- if no Frappe app changes, the relay; if only the frontend changes, the
  frontend.

[The team's repositories](repositories.md)
(`${CLAUDE_SKILL_DIR}/repositories.md`) lists each one, what it holds and its
base branch.

That record holds the spec (requirements, acceptance criteria, decisions), the
design with the contract between the layers, the end-to-end QA, and every
part's status in its handover.

Each other repository gets a **part folder** with the same name, holding only
its own work:

- `README.md`, from `templates/part-README.md`: where the record is, this
  repository's part and PR, and its tasks (`F-1`, `R-1`, …), each tied to the
  record's acceptance criteria.
- `qa.md`, from `templates/part-qa.md`: this repository's automated tests and
  their runs, and the security check of its diff.

A part never restates a requirement or a decision: it cites them by id (`AC-3`,
`D-12`) and links the record. Nothing is copied between repositories. Each part
ships with its repository's PR, so a reviewer there sees what the PR does, the
tasks it closes, its tests and its security check.

Then:

1. **One branch name** in every repository the change touches, so the pieces
   are easy to find and to test together.
2. **The contract in one place:** the record's `design.md` gives each layer's
   part (the Frappe method, the relay route, the frontend call and its state)
   and what each side sends and gets back. Change a contract on every side in
   the same change. When the repositories can't deploy at once, keep it
   backward compatible until the last one ships.
3. **Each repository's guidance:** before editing another repository, read its
   `CLAUDE.md` and the `.claude/rules/` files for the area. A session loads only
   its own repository's guidance by itself.
4. **The end-to-end QA runs once, from the record, in the checks:** the
   `qa-auditor` agent audits the journeys across the whole stack, and the record's `qa.md` maps each
   case to the parts' tests.
5. **A security check per repository, in the checks:** the
   `security-reviewer` agent reviews
   each repository's diff against that repository's `.claude/rules/security.md`.
   Its findings go in that part's `qa.md`, or the record's for the owning
   repository.
6. **PRs that point at each other:** each PR's description links the record and
   the other PRs. The record's `HANDOVER.md` gives each repository's branch,
   commit and PR, and the merge and deploy order: together, or which goes first.
7. **Guidance where it governs:** a lasting rule for the frontend goes in the
   frontend's `.claude/rules/`, even when the record is in another repository.

## Starting

1. Create the folder and copy the templates the routing table names from
   this skill's `templates/` folder (`${CLAUDE_SKILL_DIR}/templates/`):
   `spec.md`, `progress.md`, `HANDOVER.md`, `qa.md`; `design.md` comes from
   the `design` skill. In the other repositories of a
   change that spans several, add only the part folder, from
   `templates/part-README.md` and `templates/part-qa.md`.
2. Fill `spec.md` before building: scope, sources, acceptance criteria and
   security notes. If the change starts from a BRD or designs, the `brd-design`
   skill fills it.
3. Add other documents only when the work needs them (a runbook).

## Avoid rework

Most repeated work comes from finding out late. Before building, and while
building:

1. **Settle the design with the owner first** (features and refactors):
   `design.md`, the `design-reviewer`'s approval, then the owner's yes, before
   the first line of code. Say who sees what, and what shows when there's no
   data (a section without records isn't shown).
2. **Reuse before writing.** Search for the function, endpoint or component
   that already does it. Extend it when every caller keeps its behaviour;
   write a new one only when extending would break a caller or mix concerns.
3. **Scan dependencies when a release line starts** and whenever one changes
   (`pip-audit`, `npm audit`), not only at release. An upgrade found at the end
   reopens every check.
4. **Test on the production database engine from the first test** (the `qa`
   skill's fast test databases make that cheap), not only at release.
5. **Freeze before the final runs.** While editing, run the target tests.
   Start the full suites (both engines) and the browser checks only after the
   last change. A change made while they run means running them again.

## While working

- Add a `progress.md` entry at each decision or milestone.
- Keep `HANDOVER.md` ready for the next person: its status line, what's left,
  the exact next action, each repository's branch and commit, the checks
  actually run, and migrations or deployments owed. Update it before yielding.
- Number decisions (`D-1`, …), with the reason and date, and say when the owner
  made one.
- Moving the work to another computer or a fresh session: the `handover` skill
  writes the note that carries what the record can't (unpushed work, standing
  notes from memory, the machine's set-up).

## Finishing

A change is done when the checks the owner picked from the `checks` menu
have run, and, for each that ran:

1. **quality:** the `code-quality-reviewer`'s rows are applied, approved by
   the owner (anything an outside caller may reach), or recorded as
   follow-ups; names say what they hold; nothing got slower;
2. **security:** the `security-reviewer`'s findings are in `qa.md`, as
   `.claude/rules/security.md` requires, each fixed or accepted by the owner;
3. **QA and performance:** the cases and automated tests, and the
   `qa-auditor`'s and `performance-auditor`'s runs where they apply, are in
   `qa.md` (the `qa` and `performance` skills);
4. any lasting rule it settled is in `CLAUDE.md` or `.claude/rules/`;
5. `HANDOVER.md` is current.

Keep the record itself lean: cite requirement and decision ids (`AC-3`,
`D-2`) instead of restating them, put the run counts in `qa.md` and not the
output, and keep `HANDOVER.md` to what the next session needs.

When it ships, the `release` skill takes it from there: the checks rerun, the
version, the artifact and the PR.

## What stays out

No credentials, tokens, customer or bank identifiers, raw partner rows,
production exports or real screenshots. Cite local evidence by its path under
`.claude/local/`, and report production data as counts with the export date.
Say plainly whether validation, migration and deployment actually happened.
