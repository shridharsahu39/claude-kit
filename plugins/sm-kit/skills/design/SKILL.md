---
name: design
description: Architect a change before coding — reuse or extend before new, one job per module, data, concurrency, contract, security — into design.md, with the database, backend and frontend practices. Use when the change skill routes a task to design.
---

# Design before code

A change the routing table marks *design* gets a `design.md` in its record,
from [templates/design.md](templates/design.md), and the `design-reviewer`'s
approval, before the first edit.

## Steps

1. **Map what exists** (yourself, or one `Explore` agent when it spans
   repositories you haven't read). For each thing the change needs, find the
   function, endpoint, component, table or job that already does it or
   nearly does. `git grep -n` the names, the DocType, the route, the label.
2. **Decide reuse / extend / new** for each, in the design's reuse table.
   Extend only when every existing caller keeps its behaviour (list them).
   New only when extending would break a caller or mix two concerns.
3. **Lay out the modules**: one concern each, in its layer (data → service →
   API → UI), dependencies pointing down, no cycle.
4. **Read the practices for the layers you touch**, and only those:
   [db.md](db.md), [backend.md](backend.md), [frontend.md](frontend.md).
   Apply what fits this change; don't paste them into the design.
5. **List outside callers** the change touches (crons, webhooks, callbacks,
   public methods, partner routes) and who calls each. Changing or retiring
   one is the owner's decision.
6. **Write the security of the design**: who may call each entry point, how
   records are scoped to the caller, which fields a caller may set and see.
7. **Get the review**: the `design-reviewer` agent, briefed with the record's
   path and the repositories. Give it the design and the code, not your
   reasoning about why it's right. Fix "Changes needed", rerun once, record
   the verdict in `design.md`.
8. **The owner's yes** on the design (in chat is enough; note it as a
   decision), then build.

Keep `design.md` to what a builder needs: tables and lists, file paths,
contracts. No essay, no restated spec: cite `AC-n` and `D-n`.
