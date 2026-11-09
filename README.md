# claude-kit

SprintMoney's shared Claude Code set-up. It's two things:

- **The `sm-kit` plugin** (`plugins/sm-kit/`), served from this repository as
  the `sprintmoney` plugin marketplace. It brings every team repository the same
  skills, agents and guard:
  - skills: `change` (change records and their templates, and the list of
    [the team's repositories](plugins/sm-kit/skills/change/repositories.md)),
    `qa` (how every change is tested), `performance` (performance and scale
    checks, with a load generator that runs only against this machine),
    `brd-design` (a BRD and its designs combined into a spec), `local-data`
    (filing sensitive files) and `setup-machine` (a developer's
    `~/.claude/CLAUDE.md` and QA site);
  - agents: `security-reviewer` (an independent read-only review of a diff),
    `qa-auditor` (an independent end-to-end QA audit of a change) and
    `performance-auditor` (an independent performance and scale check);
  - a guard, a hook on every Bash command, that refuses `git clean -x`,
    `git stash --all`, force-adding `.claude/local/` and deleting it, and
    checks each commit Claude makes for local data, data
    files, secrets and personal data. Its own git never lets a repository's
    config run a command ([guard.py](plugins/sm-kit/hooks/guard.py) says
    exactly what it does).
- **The files each repository keeps in step** (`repo-files/`), which
  [tools/sync.py](tools/sync.py) copies in: `.claude/settings.json` (turns the
  plugin on), `.claude/.gitignore`, the short `local-data` rule, the Frappe
  practice rule's body and the Frappe security rule's core, and the READMEs of
  `.claude/changes/` and `.claude/local/`.

What stays in each repository is its own: `CLAUDE.md`, its rules (security,
architecture and topic rules), its own `qa` skill where it has one, and its
change records.

Plugins can't carry `CLAUDE.md` or rules, which is why those stay copied. Plugin
names can't start with `claude-`, which is why the plugin is `sm-kit`.

## For a developer: installing

**You don't clone or install this repository.** Claude Code fetches the kit
from GitHub by itself and keeps its own copy in `~/.claude/plugins/` (the
marketplace in `marketplaces/sprintmoney/`, the plugin in
`cache/sprintmoney/sm-kit/`). Each update replaces that copy, so never edit it.
What turns the kit on is each team repository's `.claude/settings.json`.

### Before your first session

1. **Claude Code** 2.1.275 or later (`claude --version`), signed in with the
   organization's Claude account.
2. **Read access to this repository** on GitHub. Check it with
   `gh repo view Wildflower-Business-Services-Pvt-Ltd/claude-kit`.
3. **Git that reaches GitHub without a prompt.** Claude Code clones over SSH
   and falls back to HTTPS, so either works: an SSH key GitHub knows
   (`ssh -T git@github.com` greets you by name), or `gh auth login` followed by
   `gh auth setup-git`.
4. **The team's repositories, where they usually live:** the Frappe apps in
   your bench's `apps/`, and the relay (`sprint-money-backend`) and the
   frontend (`sprint-money-frontend`) beside the bench, for example in
   `~/Documents/Sprintmoney/`.

### Your first session

1. Open Claude Code in a team repository, for example your bench's
   `apps/mutual_fund`, and trust the folder when it asks. Claude Code adds the
   `sprintmoney` marketplace in the background and loads `sm-kit`. If that
   first session shows no `/sm-kit:` skills, start a new one.
2. Once per machine, run `/sm-kit:setup-machine`. It writes your
   `~/.claude/CLAUDE.md` (where your bench, sites, QA site and repositories
   are) and gives you the commands to create a QA site.
3. Check it worked: typing `/sm-kit:` lists the kit's skills, and
   `claude plugin marketplace list`, run inside the repository, shows
   `sprintmoney` from `GitHub (Wildflower-Business-Services-Pvt-Ltd/claude-kit)`.

The plugin's skills are `/sm-kit:<name>`; its agents are `sm-kit:<name>`.

### If it doesn't load

Check the access and git steps above, then start a new session. If the skills
still don't appear, install the plugin yourself, in a session or in a terminal
as `claude plugin install …`. That adds the marketplace to your user settings
and turns `sm-kit` on in all your sessions:

```
/plugin install sm-kit --marketplace Wildflower-Business-Services-Pvt-Ltd/claude-kit
```

### Updates

They come by themselves: when a release raises the plugin's version, Claude
Code picks it up at the start of a session.
`claude plugin marketplace update sprintmoney` fetches it at once.

## For the organization

Two settings in the admin console, set by an Owner or Primary Owner, each with
its source here:

- **Organization instructions** (claude.ai: Organization settings →
  Organization and access): [org/organization-instructions.md](org/organization-instructions.md).
  They reach every claude.ai conversation, and Claude Code sessions too, in
  the desktop app and the terminal (seen on 2026-10-30; Claude Code's
  documentation doesn't say so).
- **Claude Code managed settings** (Organization settings → Claude Code →
  Managed settings): [org/managed-settings.json](org/managed-settings.json).
  They turn `sm-kit` on in every developer's Claude Code session, whichever
  repository it's in: the terminal, the IDEs, the desktop app's Code tab and
  cloud sessions. A developer can't turn it off. Claude Code fetches them at
  start-up and every hour, for anyone signed in with the organization's
  account.

The managed settings put this repository's code, the guard included, on every
developer's machine, and keep it updated from `main`. Before setting them:

1. Give every developer read access to this repository: until then, their
   sessions can't fetch the plugin.
2. Protect `main` (Settings → Branches): a pull request with an approving
   review from a code owner for every change, no force pushes, and no
   exception for admins.
3. Keep the people who can write here few. [.github/CODEOWNERS](.github/CODEOWNERS)
   names who must review. Nobody can approve their own pull request, so name at
   least two people there before turning step 2 on.

If some developers can't have access to this repository, publish the plugin
through the organization's plugin catalog instead (Organization settings →
Plugins & skills → Sync from GitHub). Claude's GitHub app reads the repository,
and the plugin updates on every push. But the catalog also offers its skills in
claude.ai chat, where they don't fit, so managed settings come first.

## Changing the kit

Clone this repository beside the team's other repositories, for example
`~/Documents/Sprintmoney/claude-kit`, never inside a bench's `apps/`: it isn't
a Frappe app. Then:

1. Edit the plugin or `repo-files/`.
2. Run the tests: `python3 -m unittest discover -s plugins/sm-kit/hooks` (the
   guard) and `python3 -m unittest discover -s plugins/sm-kit/skills/performance`
   (the load generator).
3. Validate: `claude plugin validate .` and
   `claude plugin validate plugins/sm-kit`.
4. Raise `version` in `plugins/sm-kit/.claude-plugin/plugin.json`, then open a
   PR here: teammates move to a new version only when this number changes.
   Once it merges, `claude plugin tag plugins/sm-kit --push` tags the release,
   and auto-update brings it to each teammate's next session.
5. If `repo-files/` changed, run `tools/sync.py <repo> …` over the
   repositories and commit the result in each, on a branch from its base. Run
   `tools/sync.py --check <repo> …` any time to see whether a repository has
   drifted from the kit. It works only on a team repository's own checkout.

To try a change before it's released, point your own machine at your clone:
after `claude plugin marketplace add <your clone>`, every session loads the kit
from it, edits included. To go back to GitHub's copy, run
`claude plugin marketplace remove sprintmoney`, then
`claude plugin marketplace add Wildflower-Business-Services-Pvt-Ltd/claude-kit`.
`claude --plugin-dir plugins/sm-kit` loads your clone for one session only.

## Adding a repository

Copy `repo-files/` into it with `tools/sync.py <repo>`, write its `CLAUDE.md`
(any team repository's is a model: what it is, its base branch, the guidance,
when a change is done, working from a BRD, its rules), its
`.claude/rules/security.md` and its topic rules, and add it to
[the team's repositories](plugins/sm-kit/skills/change/repositories.md).

If its base branch already has a `CLAUDE.md` its own team keeps, keep that word
for word and add the team's sections after it, and let the topic rules point to
it rather than repeat it, as loan_against_securities#14 did.
