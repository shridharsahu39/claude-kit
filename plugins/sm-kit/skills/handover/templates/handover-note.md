# Handover for a new Claude Code session: <what's being worked on>

Written <dd/mm/yyyy> on <this computer> for a session on <the other computer>.
Read all of it before the first edit.

## 0. First: make sure you have the code

```bash
git fetch origin && git switch <branch> && git pull
git log --oneline -5          # expect <commit> at the top
ls <files that must exist>
```

<If anything is uncommitted or unpushed, list it here, file by file. Say:
"If these are missing, stop and ask the owner to push them. Don't rebuild them.">

## 1. What to read

- The repository's `CLAUDE.md`, `AGENTS.md` and `.claude/rules/`, which load by
  themselves.
- The change records: `<.claude/changes/<yyyy-mm-dd>-<slug>/>`.

### Standing notes (this computer's memory doesn't travel)

- **<Rule>.** <Why, and how to apply it.>
- <…>

## 2. Where things stand

| Release or change | What | State |
| --- | --- | --- |
| <…> | <…> | <merged / in PR #n / committed, not pushed / not started> |

### Checks already run

- <Command and result, with counts, and the database each ran on.>
- **Not run:** <what wasn't checked, and why>.

## 3. The machine

- **Tools:** <name and version of each; where it came from>.
- **Databases:** <the engines, and each disposable test database and its user>.
- **GitHub:** <account; SSH host alias or gh over HTTPS>. Never run `gh auth
  login` or `gh auth switch` for the developer.

## 4. Action plan

1. <Exact step, with the command or file.>
2. <…>

## 5. Questions for the owner (ask; don't decide)

- <…>

## 6. Next

<What comes after, with the owner's requirements as they were given.>
