---
name: release
description: Ship a finished change as a release — the readiness checks (tests on every database engine, a fresh install, migrations), the version bump and deploy notes, committing by explicit paths after a secret scan, building and scanning the release artifact, pushing to the one open PR, and stating what wasn't verified. Use when a change is done and is to ship, when asked to build a release or a release ZIP, or before telling the owner a release is ready.
argument-hint: "<version>"
---

# Releasing a change

The repository's `CLAUDE.md` says what its release is: a ZIP for cPanel, a
tag, or a deploy. It also names the build tool and where the version lives.
This skill gives the order of the steps and the checks between them. Never say
a release is ready on evidence you didn't gather in this session, or that the
change's `qa.md` doesn't record.

## Before you start

- Every change going into the release has met its record's "done" bar: QA
  and the security check recorded in `qa.md`, and `HANDOVER.md` current (the
  `change` skill).
- Owner decisions that the change's `HANDOVER.md` lists as open have been
  answered, or the owner has agreed to ship without them.
- `git status` is clean apart from this release's own files.

## Steps

1. **Version.** Bump the version where the repository keeps it, once per
   release. Never reuse or re-tag a version that was published.
2. **Deploy notes.** Add the release to the repository's deployment document:
   the migrations and their revision ids, new dependencies, new settings and
   their defaults, steps after the deploy, and the companion programs and
   their versions.
3. **Checks, rerun now:**
   - the whole test suite, with its counts;
   - the same suite on a disposable local copy of the production database
     engine (MariaDB or MySQL), when the tests normally run on another
     (SQLite);
   - a fresh install: every migration chain from an empty database, then the
     repository's schema-drift check (`alembic check`, for example);
   - for a schema change, an upgrade from the previous release with data in
     it, a rerun after a stop part-way, and the downgrade;
   - the frontend's typecheck, and the tests of any companion program.

   If a check can't run here (no MariaDB on this machine, say), stop. Ask
   whether to ship without it, and record the answer.
4. **Names and structure.** List the files the release adds or renames
   (`git diff --name-status <base>...HEAD`) and check that:
   - each name says what it holds, in the product's words: a reader shouldn't
     need to open it or know the release history;
   - the release grew no file past about 500 lines, or into two subjects;
   - the guidance it touched (`CLAUDE.md`, `AGENTS.md`, rules) says each rule
     once.

   Rename or split what doesn't pass, with every import and reference, and
   rerun the tests. Speed comes first: never trade a query, a request or bundle
   weight for a shorter file. Say in the PR what was renamed or split.
5. **Commit by explicit paths.** Stage the files by name, never with `git add
   -A` or `.`, and leave out other people's work. Read the staged diff for
   secrets and personal data:

   ```bash
   git diff --cached | grep '^+' | grep -n -i -E 'password\s*[=:]\s*\S|secret_key\s*=|api[_-]?key\s*[=:]\s*\w{12,}|BEGIN [A-Z ]*PRIVATE|://[^/@ ]+:[^/@ ]+@|token\s*=\s*\S{16,}'
   git diff --cached | grep '^+' | grep -o -E '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' | sort -u
   ```

   Every hit must be a test placeholder (`example.com`, `9999999999`,
   `ABCPE1234F`). A real mobile, PAN, email or name blocks the commit. The
   guard checks it again.
6. **Build the artifact** with the repository's own tool, from the committed
   tree. Then list its contents and check for files that must never ship:

   ```bash
   unzip -l <artifact>.zip | grep -i -E 'config\.env$|\.env$|setup\.txt|\.sqlite|\.db$|uploads/|\.venv|\.claude|\.pem|\.key$'
   ```

   That should print nothing. Then confirm the release's migrations and its
   built UI are in the artifact.
7. **Push to the one open PR.** Add to the open PR for this line of work, and
   update its title and description to cover every release it now carries:
   what changed, the migrations, the checks run and what wasn't verified.
   Never open a second, stacked PR. A PR is opened only when none is open, and
   it targets the base branch the repository's `CLAUDE.md` names.
8. **Update the record.** In each change's `HANDOVER.md`, set the status,
   branch, commit and PR link, and the migrations and deployments owed. Commit
   that as its own small commit ("Handover: PR link").
9. **Tell the owner:**
   - the artifact's path and version;
   - the deploy steps, from the deploy notes;
   - **what wasn't verified**: the production database version and its
     limits, live providers (email, WhatsApp, payment), and the host's own
     limits (upload size, Python version).

## Never

- Overwrite or re-tag a published release, or build an artifact from
  uncommitted files.
- Print a secret while checking for one: grep for its presence, never its
  value.
- Deploy. The owner deploys and records it in the deployment log.
