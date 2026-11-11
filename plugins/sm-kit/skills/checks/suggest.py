#!/usr/bin/env python3
"""Recommend which checks a change needs, from its diff, without a model.

Usage: suggest.py [--base <ref>] <repo> [<repo> ...]

For each repository, reads what changed against the base (the merge base with
--base, default origin/HEAD, else main), plus uncommitted and untracked files,
and prints the check menu with each item marked recommended (x) or not ( ) and
the reason. Only reads; changes nothing. The session shows the menu to the
owner, who picks; it is a recommendation, not a decision.
"""
import re
import subprocess
import sys
from pathlib import Path

TEXT = re.compile(r"(\.(md|mdx|txt|rst|po|pot)$)|(^|/)(translations?|locales?|i18n)/|(^|/)(README|CHANGELOG|LICENSE)[^/]*$", re.I)
CODE = re.compile(r"\.(py|pyi|js|jsx|ts|tsx|vue|svelte|html|jinja2?|sql|sh|go|rb|php|java|kt|cs)$", re.I)
UI = re.compile(r"\.(jsx|tsx|vue|svelte|html|jinja2?|css|scss)$|(^|/)(src|public|www|templates|pages|components)/|/doctype/[^/]+/[^/]+\.js$", re.I)
SCHEMA = re.compile(r"/doctype/[^/]+/[^/]+\.json$|(^|/)patches(\.txt|/)|(^|/)(migrations|alembic|versions)/|\.sql$|schema\.prisma$|(^|/)models?\.py$|(^|/)fixtures/", re.I)
DEPS = re.compile(r"(^|/)(requirements[^/]*\.txt|pyproject\.toml|setup\.(py|cfg)|Pipfile(\.lock)?|poetry\.lock|uv\.lock|package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml)$")
OUTSIDE_FILES = re.compile(r"(^|/)hooks\.py$|webhook|callback|oauth|(^|/)auth|permission|role", re.I)
# Added or removed lines that create, guard or expose an entry point.
ENTRY = re.compile(r"@frappe\.whitelist|allow_guest|ignore_permissions|frappe\.db\.sql|\.route\(|@(app|router|bp|api)\.|router\.(get|post|put|patch|delete)\(|app\.(get|post|put|patch|delete|use)\(|has_permission|permission_query|verify_signature|request\.(args|form|json|get_json)|frappe\.form_dict|dangerouslySetInnerHTML|v-html|subprocess|eval\(|pickle|yaml\.load")
# Queries, jobs and data loads: the things a performance run can measure.
HOT = re.compile(r"frappe\.get_all|frappe\.get_list|frappe\.db\.(sql|get_all|get_list|get_values)|\bget_all\(|\bget_list\(|\.objects\.|\bselect\b[^\n]*\bfrom\b|scheduler_events|enqueue\(|useQuery|useInfiniteQuery", re.I)

CHECKS = [
    ("quality", "Code quality (code-quality-reviewer)"),
    ("security", "Security review (security-reviewer)"),
    ("tests", "Full test suites, every database engine"),
    ("migration", "Database migration check (fresh install + migrate a production-like copy)"),
    ("browser", "Browser QA (qa-auditor)"),
    ("performance", "Performance (performance-auditor)"),
    ("cloudflare", "Cloudflare full security audit (whole repository, many agents)"),
]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True).stdout


def base_ref(repo, base):
    for ref in ([base] if base else []) + ["origin/HEAD", "main", "master"]:
        if git(repo, "rev-parse", "--verify", "--quiet", ref).strip():
            return git(repo, "merge-base", ref, "HEAD").strip() or ref
    return None


def changes(repo, base):
    """Changed paths and the changed lines (added and removed) against base."""
    ref = base_ref(repo, base)
    rng = [ref] if ref else []
    untracked = set(git(repo, "ls-files", "--others", "--exclude-standard").split())
    names = set(git(repo, "diff", "--name-only", *rng).split()) | untracked
    # Only code is read for entry points and queries: guidance that mentions them isn't one.
    code = [n for n in names if CODE.search(n) or n.endswith("hooks.py")]
    lines = []
    if code:
        lines = [l[1:] for l in git(repo, "diff", "-U0", *rng, "--", *code).splitlines()
                 if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    for path in sorted(untracked & set(code)):
        f = Path(repo) / path
        if f.is_file() and f.stat().st_size < 200_000:
            try:
                lines += f.read_text(errors="ignore").splitlines()
            except OSError:
                pass
    return sorted(names), lines


def recommend(names, lines):
    """{check: reason} for the recommended checks."""
    rec = {}
    code = [n for n in names if CODE.search(n) and not TEXT.search(n)]
    if not names:
        return rec
    if not code and all(TEXT.search(n) for n in names):
        return rec  # text only: run the tests that assert the strings, nothing more
    body = "\n".join(lines)
    if code:
        rec["quality"] = f"{len(code)} code file(s) changed"
        rec["tests"] = "code changed; the target tests ran while building, the full suites haven't"
    entry = sorted({m.group(0) for m in ENTRY.finditer(body)})
    outside = [n for n in names if OUTSIDE_FILES.search(n)]
    deps = [n for n in names if DEPS.search(n)]
    if entry or outside or deps:
        why = []
        if entry:
            why.append("entry points or risky calls: " + ", ".join(entry[:4]))
        if outside:
            why.append("files outside callers reach: " + ", ".join(outside[:3]))
        if deps:
            why.append("dependencies changed: " + ", ".join(deps[:3]))
        rec["security"] = "; ".join(why)
    schema = [n for n in names if SCHEMA.search(n)]
    if schema:
        rec["migration"] = "schema or patches changed: " + ", ".join(schema[:3])
        rec["tests"] = rec.get("tests", "schema changed")
    ui = [n for n in names if UI.search(n) and not TEXT.search(n)]
    if ui:
        rec["browser"] = "screens or client code changed: " + ", ".join(ui[:3])
    if code and (HOT.search(body) or schema):
        rec["performance"] = "a query, job or schema on a possible hot path changed; skip if it isn't one"
    return rec


def main(argv):
    base = None
    if argv[:1] == ["--base"]:
        base, argv = argv[1], argv[2:]
    repos = argv or ["."]
    total = {}
    for repo in repos:
        names, lines = changes(repo, base)
        print(f"{repo}: {len(names)} file(s) changed")
        for check, reason in recommend(names, lines).items():
            total.setdefault(check, []).append(f"{Path(repo).resolve().name}: {reason}")
    print()
    for check, label in CHECKS:
        mark = "x" if check in total else " "
        why = " | ".join(total.get(check, []))
        if check == "cloudflare":
            why = "not per change: for a full audit before a big release, or when asked"
        print(f"[{mark}] {check:<11} {label}" + (f" — {why}" if why else ""))
    if not total:
        print("\nNothing recommended: a text-only change (or no change). Run the tests that assert the strings.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
