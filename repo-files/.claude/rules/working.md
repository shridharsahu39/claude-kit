# How to work

Loads every session; kept short on purpose. Detail lives in the `sm-kit`
skills, read only when a step needs them.

## Think, then change only what's asked

After the Karpathy guidelines (forrestchang/andrej-karpathy-skills):

1. **Think before coding.** State assumptions. If two readings exist, ask; if
   a simpler way exists, say so.
2. **Simplest thing that works.** No feature, option, abstraction or error
   path nobody asked for. 200 lines that could be 50 get rewritten.
3. **Surgical.** Every changed line traces to the task. Match the existing
   style. Remove what *your* change orphaned; report other dead code, and
   leave it to the code-quality pass of the checks.
4. **Goal first.** Turn the task into a check (a failing test, a query, a
   screen), then loop until it passes.

## Route the task before the first edit

The `change` skill's routing table sets, per kind of task, the record, whether
a design and its review are needed, and which model does the work. Text-only
work (copy, labels, docs, messages) needs no design; across many files it goes
to the `text-editor` agent (a light model).

## Spend few tokens

- Search (`grep -n`, `git grep`) before reading; read the lines you need, not
  whole files; never re-read a file you just wrote.
- Batch independent tool calls in one turn.
- Run tests and linters quietly and read only failures.
- Delegate to an agent only for independent parallel work, a broad search
  whose files you don't need to see, or an unanchored review. Do a handful of
  tool calls yourself. Brief an agent fully once; don't redo its work.
- Replies: the result, the evidence, the next step. No restating the task, no
  recap of every file.

## Never remove without asking

Anything reached from outside the code base: scheduled jobs and crons,
webhooks, auth and payment callbacks or return URLs, whitelisted or public
API methods, routes another repository, partner, app or bookmark may call,
`hooks.py` events, patches, fixtures, queue job names, CLI commands, config
keys and database columns. Show the evidence it's unused and let the owner
decide.
