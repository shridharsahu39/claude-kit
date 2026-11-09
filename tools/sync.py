#!/usr/bin/env python3
"""Keep the team repositories' shared Claude files in step with this kit.

Usage:
  tools/sync.py <repo> [<repo> ...]          write the shared files, retire old copies
  tools/sync.py --check <repo> [<repo> ...]  report what differs; change nothing

What it manages in each repository; everything else there is the repository's own:

- .claude/.gitignore, .claude/settings.json, .claude/rules/local-data.md,
  .claude/changes/README.md and .claude/local/README.md, copied from
  repo-files/.claude/.
- .claude/rules/frappe.md, where the repository has one: the body from
  repo-files/frappe/frappe-body.md, under the repository's own `paths:`.
- .claude/rules/security.md, where it's built on the kit's Frappe core (it has
  an "## In this app" section): repo-files/frappe/security-core.md around that
  section.
- The copies the sm-kit plugin replaced (the change and brd-design skills, both
  agents, and the old generic qa skill) are removed when they match a version
  the kit shipped. A changed copy is reported, never removed.

In a repository whose package.json uses Prettier, Markdown and JSON are
formatted with that repository's own Prettier, as its CI checks them.

It works only on a team repository's own checkout: the top of a git work tree
with a remote in the team's GitHub organization. It never writes or deletes
through a symlink. Exits 1 when --check finds a difference, 2 when it skipped
a folder.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
FILES = KIT / "repo-files"
COPIED = [".gitignore", "settings.json", "rules/local-data.md", "changes/README.md", "local/README.md"]
RETIRED = {
    "skills/change/SKILL.md": {"ab1a116be2b6256af55bf6e4224ae7e4", "d71b75f75153ae2649f2af03efb06a8b"},
    "skills/change/templates/spec.md": {"3de5705f03d5c8620b1b4f051a55a483", "75d1507dc1126245647c4779f0fed908"},
    "skills/change/templates/progress.md": {"feac1ce36428e9c713aac75502b5a301", "58f0edad43d52260c38e7964316022ff"},
    "skills/change/templates/HANDOVER.md": {"a3399f5a37b0283bf8d960aa60d2f7cd", "448529a80c1c03e5a84f776cc25c5c8c"},
    "skills/change/templates/qa.md": {"8bcabdbe6e15dd53127f02146537cf6d", "235fbd879299a1b707444ea2570e717c"},
    "skills/change/templates/part-README.md": {"4952e01109abf5e2e0d15aa835986e87", "12f9447cb55454e39b52a07a7a57476b"},
    "skills/change/templates/part-qa.md": {"5f1fd736da14f2257433653e8d348d54", "7afb8ab16914c6d1599c50e99d3d903b"},
    "skills/brd-design/SKILL.md": {"b26de162328a7219541957556c16b460", "cb4f88ba84392cd4802489d7128d2023"},
    "agents/qa-auditor.md": {"e026c0d4a6bce021ae8592f125f1b1b3"},
    "agents/security-reviewer.md": {"329a47264cbf6308146008ab0e44b7cc"},
    "skills/qa/SKILL.md": {"41f9cb3e663eb251b31a95fe63716dfe"},
}
FRONT = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
APP_SECTION = re.compile(r"\n## In this app\n(.*?)\n## Before handover\n", re.DOTALL)
TEAM_REMOTE = re.compile(r"github\.com[:/]Wildflower-Business-Services-Pvt-Ltd/")


def not_a_team_repository(repo):
    """Why repo isn't a team repository's own checkout, or None when it is."""
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout
    try:
        top, remotes = git("rev-parse", "--show-toplevel").strip(), git("remote", "-v")
    except (subprocess.CalledProcessError, OSError):
        return "not a git checkout"
    if Path(top).resolve() != repo.resolve():
        return f"not the top of its checkout ({top} is)"
    if not TEAM_REMOTE.search(remotes):
        return "no remote in the team's GitHub organization"
    return None


def managed_path(repo, rel):
    """The managed file's path, refused when a symlink lies on the way to it."""
    path = repo / ".claude" / rel
    for part in [path, *path.parents]:
        if part == repo:
            return path
        if part.is_symlink():
            raise SystemExit(f"{repo.name}: .claude/{rel} goes through a symlink ({part}); fix that first")
    return path


def uses_prettier(repo):
    pkg = repo / "package.json"
    if not pkg.exists():
        return False
    deps = json.loads(pkg.read_text())
    return any("prettier" in deps.get(k, {}) for k in ("dependencies", "devDependencies"))


def formatted(repo, rel, text):
    if not uses_prettier(repo) or not rel.endswith((".md", ".json")):
        return text
    result = subprocess.run(
        ["npx", "--no-install", "prettier", "--stdin-filepath", rel],
        cwd=repo, input=text, capture_output=True, text=True, check=True,
    )
    return result.stdout


def wanted(repo):
    """The managed files' wanted content, by path relative to the repository's .claude/."""
    dot = repo / ".claude"
    out = {rel: (FILES / ".claude" / rel).read_text() for rel in COPIED}
    frappe = dot / "rules/frappe.md"
    if frappe.exists():
        front = FRONT.match(frappe.read_text())
        if front:
            out["rules/frappe.md"] = front.group(0) + (FILES / "frappe/frappe-body.md").read_text()
    security = dot / "rules/security.md"
    if security.exists():
        section = APP_SECTION.search(security.read_text())
        if section:
            core = (FILES / "frappe/security-core.md").read_text()
            out["rules/security.md"] = core.replace("{app_section}", section.group(1).strip("\n"))
    return {rel: formatted(repo, ".claude/" + rel, text) for rel, text in out.items()}


def sync(repo, check):
    dot = repo / ".claude"
    changes = []
    for rel, text in wanted(repo).items():
        path = managed_path(repo, rel)
        if not path.exists() or path.read_text() != text:
            changes.append(f"{'differs' if path.exists() else 'missing'}: .claude/{rel}")
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
    for rel, known in RETIRED.items():
        path = managed_path(repo, rel)
        if not path.exists():
            continue
        if hashlib.md5(path.read_bytes()).hexdigest() not in known:
            if rel != "skills/qa/SKILL.md":
                changes.append(f"changed copy, merge by hand: .claude/{rel}")
            continue
        changes.append(f"retired: .claude/{rel}")
        if not check:
            path.unlink()
            for parent in path.parents:
                if parent == dot or any(parent.iterdir()):
                    break
                parent.rmdir()
    return changes


def main(argv):
    check = "--check" in argv
    repos = [Path(a).resolve() for a in argv if a != "--check"]
    if not repos:
        print(__doc__)
        return 2
    drift = skipped = False
    for repo in repos:
        problem = not_a_team_repository(repo)
        if problem:
            print(f"{repo.name}: skipped, {problem}")
            skipped = True
            continue
        changes = sync(repo, check)
        drift = drift or bool(changes)
        print(f"{repo.name}: {'in step' if not changes else ''}")
        for line in changes:
            print(f"  {line}")
    if skipped:
        return 2
    return 1 if check and drift else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
