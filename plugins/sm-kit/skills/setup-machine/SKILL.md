---
name: setup-machine
description: Write this developer's ~/.claude/CLAUDE.md (where the bench, its sites, the QA site and the repositories are) from the kit's template, install the tools a session needs (without sudo where it isn't available), and give the commands that create a local QA site. Use once per machine, on a new or second computer, or when ~/.claude/CLAUDE.md is missing or out of date.
---

# Set up this machine

Every Claude Code session on a machine loads `~/.claude/CLAUDE.md`, whichever
repository it starts in. SprintMoney's guidance keeps what differs per machine
there: where the bench and each repository are, which sites exist, which site
QA uses, and how the dev stack runs. Each repository's `CLAUDE.md` says how to
work in it.

## Steps

1. Read `~/.claude/CLAUDE.md` if it exists. Keep anything the developer wrote
   that the template doesn't cover.
2. Find the facts, then confirm them with the developer:
   - the Frappe bench: a folder holding `apps/`, `sites/` and `env/`; its
     sites (`ls <bench>/sites/*/site_config.json`) and which one is their dev
     site;
   - where the relay (`sprint-money-backend`), the frontend
     (`sprint-money-frontend`) and any other team repositories are cloned
     ([the team's repositories](../change/repositories.md), at
     `${CLAUDE_SKILL_DIR}/../change/repositories.md`);
   - how they start their dev stack (a VS Code workspace task, `bench start`
     in their own terminal, or something else), with each part's command and
     folder, so agents can start it the same way;
   - their QA site and its personas file, if they have them.
   - the team repositories that aren't Frappe apps (ClassManager, for
     example): where each is cloned, and its own `qa` skill's stack (its
     language versions, database and dev servers);
   - which tools are missing (see [Tools](#tools)), and whether `sudo` works
     without a prompt (`sudo -n true`);
   - how git reaches GitHub: an SSH key (`ssh -T git@github.com`), a host alias
     per account in `~/.ssh/config`, or `gh` over HTTPS.
3. Write `~/.claude/CLAUDE.md` from [the template](machine-CLAUDE.md)
   (`${CLAUDE_SKILL_DIR}/machine-CLAUDE.md`): fill each `<…>`, and delete the
   lines that don't apply.
4. Install what's missing, as [Tools](#tools) says. Never sign the developer
   in to anything: they run `gh auth login` themselves.
5. Without a QA site, give the developer the commands below to run themselves:
   `bench new-site` asks for the MariaDB root password, which stays with them.

## A QA site

A copy of the dev site, kept for the `qa-auditor` and `performance-auditor`
agents' runs, so a run never touches the site the developer works on. From the
bench root, with the dev site's name in place of `<dev-site>`:

```bash
bench --site <dev-site> backup
```

```bash
bench new-site qa.localhost
```

```bash
bench --site qa.localhost --force restore "$(ls -t sites/<dev-site>/private/backups/*-database.sql.gz | head -1)"
```

Copy the dev site's encryption key across without printing it, so it never
reaches the terminal or `bench.log`, which records every bench command line:

```bash
python3 - <dev-site> qa.localhost <<'PY'
import json, sys
dev, qa = (f"sites/{name}/site_config.json" for name in sys.argv[1:3])
with open(qa) as f:
    config = json.load(f)
with open(dev) as f:
    config["encryption_key"] = json.load(f)["encryption_key"]
with open(qa, "w") as f:
    json.dump(config, f, indent=1)
PY
```

Delete the partners' secrets the restore copied, and switch off Frappe's SMS
gateway. The delete keeps what isn't a partner's: users' own secrets (their API
keys, such as the relay's), the customers' PANs the sales app keeps in Password
fields (`Customer Profile`, `Lead`), and the keys the SSO app's sign-in needs
(`SSO Channel`, `SSO Settings`). An app whose `qa` skill names other DocTypes
like these keeps them too:

```bash
bench --site qa.localhost execute frappe.db.sql --args "[\"delete from __Auth where encrypted = 1 and doctype not in ('User', 'Customer Profile', 'Lead', 'SSO Channel', 'SSO Settings')\"]" && bench --site qa.localhost execute frappe.db.set_single_value --args "['SMS Settings', 'sms_gateway_url', '']"
```

```bash
bench --site qa.localhost set-config developer_mode 1 && bench --site qa.localhost set-config allow_tests 1 && bench --site qa.localhost set-config mute_emails 1 && bench --site qa.localhost scheduler disable
```

The restore copies the dev site's data, and the copied key lets the kept
secrets decrypt, so the relay can still sign in. The last command turns on
developer mode (the OTP bypass the QA logins use) and the test flag, mutes
outgoing email and stops the QA site's scheduler.

The delete doesn't reach every partner setting, so the QA site alone doesn't
stop partner calls:

- **Plain fields.** An app that keeps a partner's address or credentials in a
  plain field, not a Password field, clears them on the QA site too: its `qa`
  skill lists them, with the command. An app without a `qa` skill hasn't been
  checked.
- **The bench's shared config.** A partner setting in
  `sites/common_site_config.json` applies to every site, the QA site included.
  List the names the team's apps read from it, never the values:

  ```bash
  python3 - <<'PY'
  import json, pathlib, re
  keys, read = set(json.load(open("sites/common_site_config.json"))), set()
  for path in pathlib.Path("apps").glob("*/**/*.py"):
      if path.parts[1] != "frappe":
          read |= set(re.findall(r"frappe\.conf(?:\.get\(\s*[\"']|\.)(\w+)", path.read_text(errors="replace")))
  print("\n".join(sorted(keys & read)) or "none")
  PY
  ```

  If one is a partner's, the developer moves it into the dev site's own
  `site_config.json`, so the QA site doesn't inherit it.
- **The relay** keeps its own partner settings in its `.env`, whatever the site
  holds: a journey through it can still reach a partner the relay calls itself,
  such as the CVL KRA check.
- **Code that sends anyway.** Some code calls its partner even with the secret
  gone, sending an empty one: a failed login against a shared account. The QA
  site's scheduler stays off, and a run calls no partner's method or job.

So the `qa` skill's rules still apply on the QA site: partner reads only against
a test environment you've confirmed, writes only with the owner's go-ahead in
chat. When a run needs a partner's test system, the owner sets that system's
test credentials on the QA site for the run.

Then name the site in `~/.claude/CLAUDE.md`, mark it as the QA site, and start
its personas file, all outside every repository. Only this step makes the
`.qa-site` mark, which the performance skill's load generator looks for:

```bash
mkdir -p ~/.claude/qa-sites && touch ~/.claude/qa-sites/qa.localhost.qa-site && { [ -e ~/.claude/qa-sites/qa.localhost.md ] || printf '# QA personas on qa.localhost\n\nNone yet.\n' > ~/.claude/qa-sites/qa.localhost.md; }
```

The `qa-auditor` seeds `QA` personas on its first run and lists them there:
each one's user id (a synthetic email), who it is and what data it has, never a
password. They sign in without one, as the `qa` skill says.

## Tools

Check each with `--version` first: `git`, `python3` and the repositories'
own Python versions, `node` and `npm`, `gh`, a headless browser for QA, and
the database each stack's `qa` skill names.

**With sudo**, use the system's packages. **Without it** (`sudo -n true`
fails), install into `~/.local` and change no system file. Download each
release into a new, empty folder in the session's scratchpad, check its
published checksum, and only then unpack it:

```bash
mkdir -p ~/.local/bin ~/.local/opt
# uv: Python versions and virtual environments
curl -fsSL -o uv.tgz https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz
tar xzf uv.tgz && cp uv-x86_64-unknown-linux-gnu/uv uv-x86_64-unknown-linux-gnu/uvx ~/.local/bin/
uv python install 3.12            # the version production runs; a repository's CLAUDE.md names it
# Node: the newest release of an LTS line, checked against SHASUMS256.txt
NV=v22.x.y   # from https://nodejs.org/dist/index.json
curl -fsSLO https://nodejs.org/dist/$NV/node-$NV-linux-x64.tar.xz
curl -fsSL https://nodejs.org/dist/$NV/SHASUMS256.txt | grep " node-$NV-linux-x64.tar.xz$" | sha256sum -c -
tar xJf node-$NV-linux-x64.tar.xz -C ~/.local/opt && ln -sfn ~/.local/opt/node-$NV-linux-x64 ~/.local/opt/node
ln -sf ~/.local/opt/node/bin/node ~/.local/opt/node/bin/npm ~/.local/opt/node/bin/npx ~/.local/bin/
# gh: from its GitHub release, checked against the release's checksums file
GV=2.x.y
curl -fsSLO https://github.com/cli/cli/releases/download/v$GV/gh_${GV}_linux_amd64.tar.gz
curl -fsSL https://github.com/cli/cli/releases/download/v$GV/gh_${GV}_checksums.txt | grep " gh_${GV}_linux_amd64.tar.gz$" | sha256sum -c -
tar xzf gh_${GV}_linux_amd64.tar.gz && cp gh_${GV}_linux_amd64/bin/gh ~/.local/bin/
```

- `~/.local/bin` joins the PATH at the next login (Ubuntu's `~/.profile` adds
  it once the folder exists). Until then, put
  `PATH=$HOME/.local/bin:$PATH` in front of each command.
- **Each repository's environment**: `uv venv -p <version> .venv` and
  `VIRTUAL_ENV=$PWD/.venv uv pip install -r <requirements>`, in every folder
  that has its own requirements. Check that git ignores the `.venv`.
- **A browser for QA**: Playwright's Chromium, in a virtual environment in the
  session's scratchpad (`uv pip install playwright`, then
  `python -m playwright install chromium`). The browser lands in
  `~/.cache/ms-playwright`, outside every repository.
- **What needs sudo anyway**: a database server (MariaDB or MySQL) and system
  libraries. Give the developer the exact command to run as `! sudo …`, with
  the disposable database and user the repository's `qa` skill names.
- **GitHub**: the developer runs `gh auth login` themselves. With no SSH key,
  git can push over HTTPS through `gh`: `gh auth setup-git -h github.com`
  adds a credential helper for github.com to `~/.gitconfig`. That's a global
  git change, so ask first. Without it, give the helper for one command only:
  `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push https://github.com/<owner>/<repo>.git <branch>`.
  A private plugin marketplace (this kit) needs one of the two to fetch.
- **This kit**: `claude plugin marketplace add shridharsahu39/claude-kit`,
  then `claude plugin install sm-kit@sprintmoney`. Its skills appear in the
  next session.

Record in `~/.claude/CLAUDE.md` what was installed where. The next session
then needn't rediscover it.
