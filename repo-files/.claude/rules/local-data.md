# Sensitive data stays in `.claude/local/`

Anything sensitive a change needs lives in `.claude/local/`, on this machine
only: production data, registrar and partner files, customer documents,
designs, BRDs, logs and screenshots. Git ignores the folder, except its README.
Nothing from it goes into a commit, a change record, a test fixture, a code
comment, a PR, a ticket or an issue: cite a file by its path, and report data
as counts with the export date.

- **Filing:** a change's BRD, designs and references go in
  `.claude/local/changes/<yyyy-mm-dd>-<slug>/` (`brd/`, `design/`, `ref/`,
  `out/`). For anything else (exports, registrar files, partner documents,
  logs, test identities), and before deriving anything from a file here, load
  sm-kit's `local-data` skill: it says where each kind of file goes, how to
  name it, and what may reach the repository. Unsure? Put it in `inbox/` and
  say so.
- **Never here, or anywhere in the repository:** credentials, keys, tokens,
  OTP codes, and copies of `.env` or `site_config.json`.
- **Don't defeat the ignore:** never `git add -f` here, and never run
  `git clean -x` in this repository. sm-kit's guard refuses both.
- **Worktrees** have no copy of this folder: read the main checkout's, at
  `"$(git rev-parse --git-common-dir)/../.claude/local"`.
