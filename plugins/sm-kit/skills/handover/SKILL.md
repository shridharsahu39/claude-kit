---
name: handover
description: Hand work over to another computer or a fresh Claude Code session, or pick it up on the other side — what's unpushed, the standing notes that live only in this machine's memory, the tools the work needs, and the exact first steps. Use when the developer says they're moving to another machine, asks for a handover note, or opens a handover note from another computer.
argument-hint: "[out | in <path to the note>]"
---

# Handing work over between computers

A change's `HANDOVER.md` tells the next person where *that change* stands. It
travels with the branch. Three things don't travel:

- **Uncommitted or unpushed work**, which exists only on the first computer.
- **Claude's memory** (`~/.claude/projects/<project>/memory/`). The standing
  notes there (owner preferences, "test on MariaDB too", "one PR at a time",
  files never to open) aren't on the other machine.
- **The machine itself**: tools, environments, databases, SSH keys and logins.

This skill writes one note that covers all three, and reads it on the other
side.

## Handing over (`out`)

1. **Inventory every repository the work touches.** For each one, run:

   ```bash
   git status --short
   git branch -vv
   git log --oneline @{u}..
   git stash list
   ```

   This shows modified and untracked files, the branch and commit, commits not
   pushed, and stashes.
2. **Get the work across through git, not by copying.** Ask the developer to
   commit and push, or to let you do it, staging explicit paths after reading
   the staged diff for secrets. If something has to stay uncommitted, the note
   lists it, file by file. The other side then stops and asks rather than
   rebuilding it.
3. **Bring each change's `HANDOVER.md` up to date** (the `change` skill): its
   status, the checks actually run, and the exact next action.
4. **Carry the memory over.** Read the memory index and the files it points to.
   Copy into the note every standing instruction the other side needs, as
   plain rules with their reasons. Leave out anything that's only about this
   machine, and anything sensitive.
5. **Describe the machine.** Say which tools and versions the work needs, which
   databases (and their disposable test copies), how git reaches GitHub
   (account and host aliases), and what was installed without sudo. The
   `setup-machine` skill installs these on the other side.
6. **Write the note** from [the template](templates/handover-note.md)
   (`${CLAUDE_SKILL_DIR}/templates/handover-note.md`). Save it to
   `.claude/local/handover-<yyyy-mm-dd>-<to>.md`, which git ignores. It names
   accounts and machines, so it never goes in a commit. The developer carries
   it across: copy and paste, a USB stick, or the chat.
7. **Tell the developer** what's still on this machine only, and what they must
   do before leaving it, such as push or rotate a key that was exposed.

## Picking up (`in`)

1. **Read the whole note before the first edit.**
2. **Step 0: make sure the code is here.** Fetch, switch to the branch, and
   check the files and commits the note lists. If any are missing, stop and
   ask the developer to push them from the other computer. Never rebuild work
   that exists elsewhere.
3. **Save the standing notes to this machine's memory**, one fact per file,
   and add each to the index. Check first for memories that already cover
   them.
4. **Check the tools.** Run `--version` on each tool the note lists. If any
   are missing, use the `setup-machine` skill. Sign-ins (`gh auth login`, SSH
   keys) are the developer's to do.
5. **Rerun the checks** the note says were run: tests, typecheck, and the
   database runs. Then compare the counts with the note's. A difference is
   worth a line to the developer before going on.
6. **Ask the note's open questions** before acting on anything they cover.
   Then follow its action plan, step by step.

## What stays out of the note

Passwords, keys, tokens and OTPs; the contents of files the guidance says
never to open; real customer, student or bank data. Name such a file by its
path and say "never open". If a secret appeared in chat or in a script, say
that it must be rotated, and never repeat its value.
