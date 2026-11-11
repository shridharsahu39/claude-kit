---
name: checks
description: After development, offer the owner the check menu (code quality, security, test suites, migration, browser QA, performance, Cloudflare audit) with the ones the diff calls for marked, then run only what they pick. Use when building is done, or when the owner asks for the checks.
argument-hint: "[record path] [quality|security|tests|migration|browser|performance]"
---

# The checks: a menu, not a ritual

No check runs because it exists. Each costs tokens and time; run the ones this
change needs, picked by the owner.

## 1. Recommend, then ask

When building is done (target tests passing, last edit made):

1. Run the recommender over every repository the change touches. It reads
   the diff, uses no model, and prints the menu with reasons:
   `python3 "${CLAUDE_SKILL_DIR}/suggest.py" --base <base branch> <repo> [<repo> …]`
2. Adjust with what you know that a diff can't show (a query on a table of 50
   rows isn't a hot path; a text change that a test asserts needs that test).
3. Ask the owner once, with a multi-select question: each check, recommended
   ones first and marked "(Recommended)", with the one-line reason. Nothing
   recommended → say so and ask whether to finish without checks.
4. With an argument (`/sm-kit:checks security`), skip the question and run
   that.

## 2. Run only what was picked, in this order

Code first, so later checks see the final code. A later code edit means the
picked checks run again.

| Check | How | Cost |
| --- | --- | --- |
| **quality** | The `code-quality-reviewer` agent on the diff of every repository. Apply its **yes** rows and rerun the target tests; ask the owner, as one list with evidence, about **owner** rows (anything an outside caller may reach: crons, webhooks, callbacks, public methods, hooks, patches, queue jobs, config keys, columns); record **no** rows as follow-ups. | One agent |
| **security** | The `security-reviewer` agent on the final diff. Fix each finding or record why not; a high one blocks handover unless the owner accepts it. Rerun once on the fixes. | One agent |
| **tests** | The full suites, quietly, failures only, on every database engine the repository uses (the `qa` skill and the repository's own). | No agent |
| **migration** | On a disposable copy, never a shared site: a fresh install from an empty database, then migrating a copy of the QA site's data; every patch runs once and twice is harmless; old code still runs on the new schema; record time on the copy. The repository's `qa` skill gives the commands. | No agent |
| **browser** | The `qa-auditor` agent, for the journeys the change touches. | One agent, browser |
| **performance** | The `performance-auditor` agent, after the browser QA (both use the QA site). | One agent, load |
| **cloudflare** | Never from here: tell the owner to type `/sm-kit:cloudflare-security-audit`. It audits the whole repository with many agents. | Many agents |

Run agents one after another when one's fixes change what the next sees
(quality → security); browser and performance never at the same time.

## 3. Record

In the record's `qa.md` (each part's `qa.md` for its repository): the menu as
offered, what the owner picked, and each check's result as counts and ids, not
output. Update `HANDOVER.md`'s checks line. Tell the owner in a few lines:
what was fixed, what waits on them, what failed.
