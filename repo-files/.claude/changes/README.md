# Change records

One dated folder per change: `<yyyy-mm-dd>-<slug>/`, with `spec.md`,
`progress.md`, `HANDOVER.md` and `qa.md`. sm-kit's `change` skill says how to
start, keep and finish one, and holds the templates.

There's no index to edit, so branches don't conflict over one. Each record's
`HANDOVER.md` opens with its status; to list them:

```bash
grep -H -m1 '^\*\*Status:\*\*' .claude/changes/*/HANDOVER.md
```

A record is history. Its status and checks describe the day it was written;
verify the code, schema and deployment before relying on it.
