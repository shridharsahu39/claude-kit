---
name: change
description: Start, resume or hand over the change record that every change needs before its first edit — a dated folder in .claude/changes/ with spec, progress, HANDOVER and qa. Use at the start of any code, config or data change, when resuming one, and before yielding.
argument-hint: "<slug> [title]"
---

# Change records

Every change, however small, gets a record before its first edit. An
investigation or a migration gets one too. Reuse a record only when the work
continues that same change; otherwise link the related record.

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
4. **The end-to-end QA runs once, from the record:** the `qa-auditor` agent
   audits the journeys across the whole stack, and the record's `qa.md` maps each
   case to the parts' tests.
5. **A security check per repository:** the `security-reviewer` agent reviews
   each repository's diff against that repository's `.claude/rules/security.md`.
   Its findings go in that part's `qa.md`, or the record's for the owning
   repository.
6. **PRs that point at each other:** each PR's description links the record and
   the other PRs. The record's `HANDOVER.md` gives each repository's branch,
   commit and PR, and the merge and deploy order: together, or which goes first.
7. **Guidance where it governs:** a lasting rule for the frontend goes in the
   frontend's `.claude/rules/`, even when the record is in another repository.

## Starting

1. Create the folder and copy the four templates from this skill's
   `templates/` folder (`${CLAUDE_SKILL_DIR}/templates/`): `spec.md`,
   `progress.md`, `HANDOVER.md` and `qa.md`. In the other repositories of a
   change that spans several, add only the part folder, from
   `templates/part-README.md` and `templates/part-qa.md`.
2. Fill `spec.md` before building: scope, sources, acceptance criteria and
   security notes. If the change starts from a BRD or designs, the `brd-design`
   skill fills it.
3. Add other documents only when the work needs them (`design.md`, a runbook).

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

A change is done when:

1. its QA is recorded in `qa.md`: the cases, the automated tests, the
   `qa-auditor` agent's run for anything a person or a job does, and the
   `performance-auditor` agent's check for a change on a hot path (the `qa`
   and `performance` skills);
2. its security check is recorded in `qa.md`, as
   `.claude/rules/security.md` requires;
3. any lasting rule it settled is in `CLAUDE.md` or `.claude/rules/`;
4. `HANDOVER.md` is current.

When it ships, the `release` skill takes it from there: the checks rerun, the
version, the artifact and the PR.

## What stays out

No credentials, tokens, customer or bank identifiers, raw partner rows,
production exports or real screenshots. Cite local evidence by its path under
`.claude/local/`, and report production data as counts with the export date.
Say plainly whether validation, migration and deployment actually happened.
