# This machine (SprintMoney development)

Every Claude Code session on this machine loads this file, whichever repository
it starts in. It says where things are here; each repository's own `CLAUDE.md`
says how to work in it. Written from sm-kit's `setup-machine` template.

## Where things are

- Frappe bench: `<bench path>`. Run bench commands from there. The team's apps
  are in `apps/`; the upstream apps (`frappe` and others) carry no guidance,
  and shouldn't.
- The MF relay, `sprint-money-backend`: `<path>`.
- The frontend, `sprint-money-frontend`: `<path>`.
- Other team repositories: `<path, or delete this line>`.

## Other stacks

- `<repository>` (`<path>`): `<its stack, e.g. FastAPI + React>`. Its `qa`
  skill says how to run it. Environments: `<e.g. server/.venv, Python 3.12>`.
  `<Or delete this section.>`

## Tools

- `<Where the tools came from: system packages, or ~/.local (uv, Node, gh)
  with ~/.local/bin on the PATH.>`
- `<The database for migration checks, e.g. local MariaDB with
  cm_migration_test, or "none yet: the owner installs it with sudo".>`
- GitHub: `<SSH key and host aliases, or gh over HTTPS>`. Never run
  `gh auth login` or `gh auth switch` for the developer.

## Sites

- Dev site: `<site>`, with developer mode on.
- QA site: `<site>`, kept for the `qa-auditor` and `performance-auditor`
  agents' runs. Its personas are listed in `~/.claude/qa-sites/<site>.md`,
  outside every repository: who each is, never a password.
  `<Or, until one exists:>` No QA site yet: QA runs on the dev site and removes
  everything it created.

## The dev stack

- `<How it starts: a VS Code workspace task, or bench start in your own terminal.>`
- When a task needs it and it isn't running, an agent may start it the same
  way, in the background, since it never exits: `<each part's command, run from
  its folder>`, with each part's output in a log file rather than the agent's
  console, since it carries request lines with record names and the debugger
  PIN. Agents check a part by its port and search its log only for errors.
  Restarting a running stack interrupts the developer, so agents ask first.
  The bench, the relays and the frontends listen on every network interface:
  without a firewall refusing incoming connections, anyone on the same network
  can reach them.

## Worktrees

- A worktree has none of its repository's untracked or ignored files, so it has
  no `.claude/local/`: read the main checkout's.
