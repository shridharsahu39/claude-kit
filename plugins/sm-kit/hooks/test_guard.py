"""Tests for guard.py. Run: python3 -m unittest discover -s plugins/sm-kit/hooks

Sensitive-looking values are generated at random on each run, so this file
never holds one that the guard (or any other scanner) would flag, and none can
belong to a real person for longer than a test run.
"""
import io
import json
import os
import random
import string
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard  # noqa: E402

RNG = random.Random()


def generated(make, fake):
    while True:
        value = make()
        if not fake(value):
            return value


def digits(n):
    return "".join(RNG.choice(string.digits) for _ in range(n))


def letters(n):
    return "".join(RNG.choice(string.ascii_uppercase) for _ in range(n))


def make_aadhaar():
    while True:
        base = RNG.choice("23456789") + digits(10)
        for d in string.digits:
            if guard.verhoeff_ok(base + d) and not guard.fake_digits(base + d):
                return base + d


def mixed(n):
    return "".join(RNG.choice(string.ascii_letters + string.digits) for _ in range(n))


PAN = generated(lambda: letters(3) + RNG.choice("ABCFGHJLPT") + letters(1) + digits(4) + letters(1), guard.fake_pan)
MOBILE = generated(lambda: RNG.choice("6789") + digits(9), guard.fake_digits)
AADHAAR = make_aadhaar()
EMAIL = "qa." + "".join(RNG.choice(string.ascii_lowercase) for _ in range(8)) + "@gmail.test"
PRIVATE_KEY = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"
GITHUB_TOKEN = "gh" + "p_" + mixed(36)
SECRET_LINE = 'db_password = "' + generated(lambda: mixed(14), lambda v: not guard.secret_value(v)) + '"'


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class Repo:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name
        sh(self.path, "git", "init", "-q", "-b", "main")
        sh(self.path, "git", "config", "user.email", "qa@example.com")
        sh(self.path, "git", "config", "user.name", "QA")
        self.write(".gitignore", "*.log\n")
        self.write(".claude/.gitignore", "local/*\n!local/README.md\n")
        self.write(".claude/local/README.md", "local\n")
        self.write(".claude/local/export.csv", "rows\n")
        self.write("app.py", "x = 1\n")
        sh(self.path, "git", "add", ".")
        sh(self.path, "git", "commit", "-q", "-m", "init")

    def write(self, rel, text):
        p = Path(self.path, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, bytes):
            p.write_bytes(text)
        else:
            p.write_text(text)

    def stage(self, rel, text):
        self.write(rel, text)
        sh(self.path, "git", "add", "-f", rel)

    def check(self, command):
        return guard.check(command, self.path)

    def close(self):
        self.tmp.cleanup()


class Commands(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def decision(self, command):
        verdict = self.repo.check(command)
        return verdict[0] if verdict else None

    def test_ordinary_commands_pass(self):
        for command in ("ls -la", "git status", "git add app.py", "git clean -fd", "bench --site a.localhost migrate",
                        'echo "never run bench start"', "rm -r build", "rm .claude/local/export.csv",
                        "git log --oneline | head -5", "git stash -u -m wip", "git stash list", "git stash pop",
                        "git clean -f -e build", "command -v bench"):
            self.assertIsNone(self.decision(command), command)

    def test_bench_start_is_allowed(self):
        for command in ("bench start", "cd /tmp && bench start", "nohup bench start &", "timeout 30s bench start",
                        "/home/dev/dev-start.sh 8001 bench start"):
            self.assertIsNone(self.decision(command), command)

    def test_wrappers_hide_nothing(self):
        for command in ("sudo -u frappe git clean -fdx", "timeout 30s git clean -fdx", "timeout -k 5 1m git clean -fdx",
                        "nohup git clean -fdx &", "env -S 'git clean -fdx'", "env --split-string='git clean -fdx'",
                        "env -C /tmp git clean -fdx", "stdbuf -oL git clean -fdx", "nice -n 5 git clean -fdx",
                        "time -p git clean -fdx", "env -C .claude rm -rf local", "sudo -D .claude rm -rf local"):
            self.assertEqual(self.decision(command), "deny", command)

    def test_git_clean_with_x(self):
        for command in ("git clean -fdx", "git clean -xfd", "git clean -f -X", "git -C . clean -fx",
                        'bash -c "git clean -fdx"', "cd . && git clean -dfx", "git clean -fdx -evenv",
                        "git clean -fdx --exclude node_modules"):
            self.assertEqual(self.decision(command), "deny", command)
        self.assertIsNone(self.decision("git clean -nx"))
        self.assertIsNone(self.decision("git clean --dry-run -x"))
        self.assertIsNone(self.decision("git clean -fx -n"))

    def test_force_add_of_local_data(self):
        self.assertEqual(self.decision("git add -f .claude/local/export.csv"), "deny")
        self.assertEqual(self.decision("git stage -f .claude/local/export.csv"), "deny")
        self.assertEqual(self.decision("git add -f ."), "deny")
        self.assertEqual(self.decision("git add --force -A"), "deny")
        self.assertEqual(self.decision("cd .claude/local && git add -f export.csv"), "deny")
        self.repo.write("debug.log", "x\n")
        self.assertIsNone(self.decision("git add -f debug.log"))
        self.assertIsNone(self.decision("git add -f .claude/local/README.md"))
        self.assertEqual(self.decision("git add -f --pathspec-from-file=paths.txt"), "ask")

    def test_local_file_names_stay_out_of_the_reason(self):
        verdict = self.repo.check("git add -f .claude/local/export.csv")
        self.assertNotIn("export.csv", verdict[1])

    def test_add_never_runs_an_editor(self):
        marker = Path(self.repo.path, "editor-ran")
        sh(self.repo.path, "git", "config", "core.editor", f"touch {marker}")
        self.assertEqual(self.decision("git add -f -e .claude/local/export.csv"), "deny")
        self.assertFalse(marker.exists())

    def test_stash_all(self):
        for command in ("git stash --all", "git stash -a", "git stash push -a -m wip", "git stash save --all",
                        "git stash push -uam wip"):
            self.assertEqual(self.decision(command), "deny", command)

    def test_recursive_rm(self):
        for command in ("rm -rf .claude/local", "rm -rf .claude", "rm -rf .claude/local/*", "rm -rf .",
                        f"rm -rf {self.repo.path}", f"rm -rf {os.path.dirname(self.repo.path)}/*/.claude/local"):
            self.assertEqual(self.decision(command), "deny", command)
        self.assertIsNone(self.decision("rm -rf .claude/local/inbox"))
        self.assertIsNone(self.decision("rm -rf .claude/worktrees/x"))

    def test_recursive_rm_looks_further_down(self):
        self.repo.write("bench/apps/app/.claude/local/export.csv", "rows\n")
        self.assertEqual(self.decision("rm -rf bench"), "deny")
        self.repo.write("kit/repo-files/.claude/local/README.md", "local\n")
        self.assertIsNone(self.decision("rm -rf kit"))

    def test_recursive_rm_reads_paths_as_the_shell_does(self):
        for command in ("rm -rf $PWD/.claude/local", "rm -rf ${PWD}", 'rm -rf "$PWD/.claude"',
                        "rm -rf .claude/local/?*", "rm -rf .claude/local/[a-z]*", "rm -rf .claude/local/.??*",
                        "cd $PWD/.claude && rm -rf local"):
            self.assertEqual(self.decision(command), "deny", command)
        name = os.path.basename(self.repo.path)
        with mock.patch.dict(os.environ, {"HOME": os.path.dirname(self.repo.path)}):
            for command in (f"rm -rf $HOME/{name}", f"rm -rf ${{HOME}}/{name}/.claude", f"rm -rf ~/{name}"):
                self.assertEqual(self.decision(command), "deny", command)
        self.assertIsNone(self.decision("rm -rf $PWD/build"))

    def test_shell_keywords_hide_nothing(self):
        for command in ("if [ -d .claude/local ]; then rm -rf .claude/local; fi", "if true; then git clean -fdx; fi",
                        "{ rm -rf .claude/local; }", "! rm -rf .claude", "while false; do :; done; rm -rf .claude",
                        "true && { git stash -a; }"):
            self.assertEqual(self.decision(command), "deny", command)

    def test_paths_the_shell_builds(self):
        for command in ('rm -rf "$(pwd)/.claude/local"', 'rm -rf "$(git rev-parse --show-toplevel)/.claude/local"',
                        "rm -rf `pwd`/.claude", 'D=.claude/local; rm -rf "$D"', "export D=.claude; rm -rf $D",
                        "rm -rf .claude/{local,x}", "cd sub; cd -; rm -rf .claude/local",
                        "(cd sub && ls) && rm -rf .claude/local", "rm -rf ~+/.claude/local",
                        'find . -path "*/.claude/local" -exec rm -rf {} +', "find .claude -delete"):
            self.assertEqual(self.decision(command), "deny", command)
        for command in ('rm -rf "$X"', 'cd "$X" && rm -rf local', "find . -name '*.csv' -delete",
                        "ls | xargs rm -rf", 'D=x rm -rf "$D"'):
            self.assertEqual(self.decision(command), "ask", command)
        for command in ("find . -name '*.pyc' -print", "D=build; rm -rf $D", "cd build; cd -; rm -rf build"):
            self.assertIsNone(self.decision(command), command)
        with tempfile.TemporaryDirectory() as elsewhere:
            self.assertIsNone(guard.check('rm -rf "$X"', elsewhere))

    def test_abbreviated_and_odd_spellings(self):
        for command in ("git add --forc .claude/local/export.csv", "git stash push --al", "git stash --al",
                        "git clean -fd -e '!*'", "git clean -fde!*", "git clean --exclude='!x' -f",
                        "/usr/lib/git-core/git-clean -fdx"):
            self.assertEqual(self.decision(command), "deny", command)
        for command in ("GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.zz GIT_CONFIG_VALUE_0=commit git zz -am x",
                        "git --config-env alias.zz=ZZ zz -am x"):
            self.assertEqual(self.decision(command), "ask", command)
        self.assertIsNone(self.decision('git stash push -m "--all"'))

    def test_one_failure_never_passes_the_line(self):
        for command in ('rm -r "x\ud800"; rm -rf .claude/local', 'git -C "\x00" add -f .; rm -rf .claude/local'):
            self.assertEqual(self.decision(command), "deny", repr(command))


class Commits(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def decision(self, command='git commit -m "Fix: x"'):
        verdict = self.repo.check(command)
        return verdict[0] if verdict else None

    def test_clean_commit_passes(self):
        self.repo.stage("app.py", "x = 2\n")
        self.assertIsNone(self.decision())
        heredoc = ("git commit -m \"$(cat <<'EOF'\nFix: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n"
                   "EOF\n)\" 2>&1")
        self.assertIsNone(self.decision(heredoc))

    def test_local_file_is_refused(self):
        self.repo.stage(".claude/local/export.csv", "rows\n")
        verdict = self.repo.check('git commit -m "Fix: x"')
        self.assertEqual(verdict[0], "deny")
        self.assertNotIn("export.csv", verdict[1])

    def test_hard_secrets_are_refused(self):
        for line in (PRIVATE_KEY, f'TOKEN = "{GITHUB_TOKEN}"'):
            self.repo.stage("app.py", line + "\n")
            self.assertEqual(self.decision(), "deny", line)

    def test_personal_data_asks(self):
        for line in (f'pan = "{PAN}"', f"mobile: {MOBILE}", f"to = '{EMAIL}'", f"id = {AADHAAR}", SECRET_LINE):
            self.repo.stage("app.py", line + "\n")
            self.assertEqual(self.decision(), "ask", line)

    def test_long_and_tricky_lines_are_scanned(self):
        for line in ("x" * 9000 + f" {PAN}", f"++ {MOBILE}", f"+++ b/{EMAIL}"):
            self.repo.stage("app.py", line + "\n")
            self.assertEqual(self.decision(), "ask", line[-30:])

    def test_type_change_is_scanned(self):
        os.symlink("app.py", os.path.join(self.repo.path, "link"))
        sh(self.repo.path, "git", "add", "link")
        sh(self.repo.path, "git", "commit", "-q", "-m", "link")
        os.unlink(os.path.join(self.repo.path, "link"))
        self.repo.stage("link", f"mobile = {MOBILE}\n")
        self.assertEqual(self.decision(), "ask")

    def test_files_the_guard_cant_read_ask(self):
        for rel, content in (("shot.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00"), ("export.xlsx", b"PK\x03\x04\x00\x01"),
                             ("rows.csv", "a,b\n1,2\n"), (".claude/changes/2026-01-01-x/evidence.json", "{}\n")):
            self.repo.stage(rel, content)
            self.assertEqual(self.decision(), "ask", rel)
            sh(self.repo.path, "git", "reset", "-q")
        self.repo.stage(".claude/changes/2026-01-01-x/spec.md", "# Spec\n")
        self.assertIsNone(self.decision())

    def test_fake_and_allowed_values_pass(self):
        for line in ('pan = "ABCPE1234F"', "mobile = 9999999999", "mobile = 9876543210",
                     'fieldname = "new_password"', 'url = "https://example.com/token"',
                     'api_key = frappe.conf.get("api_key")', "id = 234567812345"):
            self.repo.stage("app.py", line + "\n")
            self.assertIsNone(self.decision(), line)
        self.repo.write(".claude/guard-allow.txt", f"# synthetic\n{PAN}\n")
        sh(self.repo.path, "git", "add", ".claude/guard-allow.txt")
        sh(self.repo.path, "git", "commit", "-q", "--no-verify", "-m", "allow")
        self.repo.stage("app.py", f'pan = "{PAN}"\n')
        self.assertIsNone(self.decision())

    def test_allowlist_counts_only_once_committed(self):
        self.repo.write(".claude/guard-allow.txt", f"{PAN}\n")
        self.repo.stage("app.py", f'pan = "{PAN}"\n')
        self.assertEqual(self.decision(), "ask")
        sh(self.repo.path, "git", "add", ".claude/guard-allow.txt")
        verdict = self.repo.check('git commit -m "Fix: x"')
        self.assertEqual(verdict[0], "ask")
        self.assertIn("allowlist", verdict[1])

    def test_secret_files_ask(self):
        self.repo.stage(".env.uat", "DEBUG=1\n")
        self.assertEqual(self.decision(), "ask")
        sh(self.repo.path, "git", "reset", "-q")
        self.repo.stage(".env.example", "DEBUG=1\n")
        self.assertIsNone(self.decision())

    def test_commit_all_and_message(self):
        self.repo.write("app.py", f"mobile = {MOBILE}\n")
        self.assertIsNone(self.decision())
        self.assertEqual(self.decision('git commit -am "Fix: x"'), "ask")
        self.assertEqual(self.decision('git commit -m "Fix: x" app.py'), "ask")
        self.repo.write("app.py", "x = 3\n")
        self.assertEqual(self.decision(f'git commit -am "call {MOBILE}"'), "ask")

    def test_add_then_commit_in_one_command(self):
        self.repo.write("app.py", PRIVATE_KEY + "\n")
        self.repo.write("new.py", f"mobile = {MOBILE}\n")
        for command in ('git add app.py && git commit -m "Fix: x"', 'git add -A && git commit -m "Fix: x"',
                        'git add . ; git commit -m "Fix: x"', 'git stage -u && git commit -m "Fix: x"'):
            self.assertEqual(self.decision(command), "deny", command)
        self.repo.write("app.py", "x = 2\n")
        for command in ('git add new.py && git commit -m "Fix: x"', 'git add -A && git commit -m "Fix: x"',
                        'cd .claude && git add .. && git commit -m "Fix: x"', 'git add -A && git commit -am "Fix: x"'):
            self.assertEqual(self.decision(command), "ask", command)
        for command in ('git add -u && git commit -m "Fix: x"', 'git add app.py && git commit -m "Fix: x"',
                        'git commit -m "Fix: x" && git add new.py', 'git add -n . && git commit -m "Fix: x"'):
            self.assertIsNone(self.decision(command), command)

    def test_carriage_returns_hide_nothing(self):
        for content in (f"a\rb\n{PRIVATE_KEY}\n", f"\r{PRIVATE_KEY}\n", f"x = 1\r\n{PRIVATE_KEY}\r\n"):
            self.repo.stage("app.py", content)
            self.assertEqual(self.decision(), "deny", repr(content[:5]))
        sh(self.repo.path, "git", "checkout", "-q", "HEAD", "--", "app.py")
        self.repo.write("new.py", f"\rmobile = {MOBILE}\n")
        self.assertEqual(self.decision('git add new.py && git commit -m "Fix: x"'), "ask")

    def test_forced_add_then_commit(self):
        self.repo.write("debug.log", PRIVATE_KEY + "\n")
        for command in ('git add -f debug.log && git commit -m "Fix: x"',
                        'git add --force . && git commit -m "Fix: x"'):
            self.assertEqual(self.decision(command), "deny", command)

    def test_binary_by_attribute_or_config_is_still_read(self):
        self.repo.stage("app.py", PRIVATE_KEY + "\n")
        self.repo.write(".gitattributes", "*.py -diff\n")
        self.assertEqual(self.decision(), "deny")
        os.remove(os.path.join(self.repo.path, ".gitattributes"))
        sh(self.repo.path, "git", "config", "core.bigFileThreshold", "1")
        self.assertEqual(self.decision(), "deny")
        self.repo.stage("shot.png", b"\x89PNG\r\n\x1a\n\x00\x00")
        verdict = self.repo.check('git commit -m "Fix: x"')
        self.assertIn("shot.png is a binary", verdict[1])

    def test_add_paths_the_shell_builds(self):
        self.repo.write("app.py", PRIVATE_KEY + "\n")
        self.repo.write("new.py", "y = 2\n")
        for command in ('git add $(git ls-files -m) && git commit -m "Fix: x"',
                        'git add {app,new}.py && git commit -m x', 'git ls-files -m | xargs git add && git commit -m x',
                        'F=app.py; git add "$F" && git commit -m x',
                        "yes | git commit -p -m x", "git --attr-source HEAD commit -am x", "git commit --al -m x"):
            self.assertEqual(self.decision(command), "deny", command)

    def test_a_shell_alias_sees_earlier_adds(self):
        sh(self.repo.path, "git", "config", "alias.sci", "!git commit")
        self.repo.write("new.py", PRIVATE_KEY + "\n")
        self.assertEqual(self.decision('git add -A && git sci -m "Fix: x"'), "deny")

    def test_replace_refs_are_ignored(self):
        self.repo.stage("app.py", PRIVATE_KEY + "\n")
        staged = subprocess.run(["git", "write-tree"], cwd=self.repo.path, capture_output=True, text=True,
                                check=True).stdout.strip()
        sh(self.repo.path, "git", "replace", "HEAD^{tree}", staged)
        self.assertEqual(self.decision(), "deny")

    def test_a_file_named_in_another_encoding_is_read(self):
        with open(os.path.join(os.fsencode(self.repo.path), b"\xff.py"), "w") as f:
            f.write(PRIVATE_KEY + "\n")
        self.assertEqual(self.decision('git add -A && git commit -m "Fix: x"'), "deny")

    def test_time_is_bounded(self):
        sh(self.repo.path, "git", "config", "alias.a", "!git a; git a; git a; git a; git a; git a")
        started = guard.time.monotonic()
        self.assertEqual(self.decision("git a"), "ask")
        self.repo.stage("app.py", "password_" * 120_000 + "\n" + PRIVATE_KEY + "\n")
        self.assertEqual(self.decision(), "deny")
        self.assertLess(guard.time.monotonic() - started, 10)

    def test_a_first_commit_is_checked(self):
        with tempfile.TemporaryDirectory() as fresh:
            sh(fresh, "git", "init", "-q", "-b", "main")
            Path(fresh, "app.py").write_text(f"mobile = {MOBILE}\n")
            verdict = guard.check('git add . && git commit -m "Init"', fresh)
            self.assertEqual(verdict[0] if verdict else None, "ask")

    def test_aliases_are_followed(self):
        self.repo.stage("app.py", PRIVATE_KEY + "\n")
        sh(self.repo.path, "git", "config", "alias.ci", "commit")
        sh(self.repo.path, "git", "config", "alias.cm", "ci -m")
        sh(self.repo.path, "git", "config", "alias.sci", "!git commit")
        for command in ('git ci -m "Fix: x"', 'git cm "Fix: x"', 'git sci -m "Fix: x"',
                        'git -c alias.go=commit go -m "Fix: x"'):
            self.assertEqual(self.decision(command), "deny", command)
        sh(self.repo.path, "git", "config", "alias.loop", "loop")
        self.assertEqual(self.decision("git loop"), "ask")

    def test_another_repository_or_index_asks(self):
        self.repo.stage("app.py", "x = 2\n")
        for command in ('GIT_DIR=/tmp/x/.git git commit -m "Fix: x"', 'git --git-dir=/tmp/x/.git commit -m "Fix: x"',
                        'git --work-tree /tmp/x commit -am "Fix: x"', 'GIT_INDEX_FILE=/tmp/i git commit -m "Fix: x"',
                        'export GIT_DIR=/tmp/x/.git; git commit -m "Fix: x"',
                        'env GIT_WORK_TREE=/tmp/x git commit -am x', "GIT_DIR=/tmp/x/.git git add -f ."):
            self.assertEqual(self.decision(command), "ask", command)
        self.assertEqual(self.decision("GIT_DIR=/tmp/x/.git git stash --all"), "deny")

    def test_diff_settings_never_hide_lines(self):
        self.repo.write("sub/b.py", "y = 1\n")
        sh(self.repo.path, "git", "add", "sub/b.py")
        sh(self.repo.path, "git", "commit", "-q", "-m", "sub")
        for key, value in (("diff.relative", "true"), ("diff.noprefix", "true"), ("diff.mnemonicPrefix", "true"),
                           ("color.ui", "always"), ("diff.context", "8")):
            sh(self.repo.path, "git", "config", key, value)
        self.repo.stage("app.py", f"mobile = {MOBILE}\n")
        self.assertEqual(self.decision('cd sub && git commit -m "Fix: x"'), "ask")

    def test_merged_hunks_keep_their_place(self):
        lines = [f'"dep{i}": "{i}.0.0",' for i in range(12)]
        self.repo.write("lock/package-lock.json", "\n".join(lines) + "\n")
        sh(self.repo.path, "git", "add", "lock")
        sh(self.repo.path, "git", "commit", "-q", "-m", "lock")
        sh(self.repo.path, "git", "config", "diff.interHunkContext", "10")
        lines[1], lines[7] = '"dep1": "1.0.1",', '"dep7": "7.0.1",'
        self.repo.stage("lock/package-lock.json", "\n".join(lines) + "\n")
        self.repo.stage("zz.py", f"mobile = {MOBILE}\n")
        self.assertEqual(self.decision(), "ask")


class RepositoryConfig(unittest.TestCase):
    """A repository's own config must never make the guard's git run a command."""

    def setUp(self):
        self.repo = Repo()
        self.marker = Path(self.repo.path, "ran")

    def tearDown(self):
        self.repo.close()

    def plant(self, gitdir_command):
        hook = Path(self.repo.path, "hook.sh")
        hook.write_text(f"#!/bin/sh\ntouch {self.marker}\nexit 1\n")
        hook.chmod(0o755)
        gitdir_command("core.fsmonitor", str(hook))
        gitdir_command("filter.x.clean", f"sh -c 'touch {self.marker}; cat'")
        gitdir_command("diff.x.textconv", f"sh -c 'touch {self.marker}; cat'")
        return hook

    def test_fsmonitor_filters_and_textconv_never_run(self):
        self.plant(lambda key, value: sh(self.repo.path, "git", "config", key, value))
        self.repo.write(".gitattributes", "*.py filter=x diff=x\n")
        subprocess.run(["git", "status"], cwd=self.repo.path, capture_output=True)
        if not self.marker.exists():
            self.skipTest("this git doesn't run the planted commands, so there's nothing to prove")
        self.marker.unlink()
        self.repo.write("app.py", f"mobile = {MOBILE}\n")
        for command in ('git commit -m "Fix: x"', 'git commit -am "Fix: x"', "git add -f .", "git add -f -A",
                        'git commit -m "Fix: x" app.py'):
            self.repo.check(command)
        self.assertFalse(self.marker.exists())
        self.assertEqual(self.repo.check('git commit -am "Fix: x"')[0], "ask")

    def plain_git_runs_it(self, *args):
        """True when plain git runs the planted command here: only then is there something to prove."""
        subprocess.run(["git", *args], cwd=self.repo.path, capture_output=True)
        ran = self.marker.exists()
        if ran:
            self.marker.unlink()
        return ran

    def touch(self, rel):
        """A new timestamp but the same content: the next porcelain diff would rewrite the index."""
        path = Path(self.repo.path, rel)
        later = path.stat().st_mtime + RNG.randint(10, 10_000)
        os.utime(path, (later, later))

    def test_a_planted_hook_never_runs(self):
        hook = Path(self.repo.path, ".git", "hooks", "post-index-change")
        hook.write_text(f"#!/bin/sh\ntouch {self.marker}\n")
        hook.chmod(0o755)
        self.touch("app.py")
        if not self.plain_git_runs_it("diff", "--numstat", "HEAD"):
            self.skipTest("this git doesn't run the planted hook, so there's nothing to prove")
        for command in ('git commit -am "Fix: x"', 'git commit -m "Fix: x" app.py', 'git commit -i -m "Fix: x" app.py'):
            self.touch("app.py")
            self.repo.check(command)
        self.assertFalse(self.marker.exists())

    def test_a_promisor_remote_is_never_fetched(self):
        upload_pack = Path(self.repo.path, "upload-pack.sh")
        upload_pack.write_text(f"#!/bin/sh\ntouch {self.marker}\nexit 1\n")
        upload_pack.chmod(0o755)
        for key, value in (("remote.origin.url", self.repo.path), ("remote.origin.promisor", "true"),
                           ("remote.origin.uploadpack", str(upload_pack))):
            sh(self.repo.path, "git", "config", key, value)
        blob = subprocess.run(["git", "rev-parse", "HEAD:app.py"], cwd=self.repo.path, capture_output=True,
                              text=True, check=True).stdout.strip()
        Path(self.repo.path, ".git", "objects", blob[:2], blob[2:]).unlink()
        if not self.plain_git_runs_it("cat-file", "-p", blob):
            self.skipTest("this git doesn't fetch from the planted remote, so there's nothing to prove")
        self.repo.stage("app.py", f"mobile = {MOBILE}\n")
        if self.marker.exists():
            self.marker.unlink()
        for command in ('git commit -m "Fix: x"', 'git commit -am "Fix: x"'):
            self.assertEqual(self.repo.check(command)[0], "ask", command)
        self.assertFalse(self.marker.exists())

    def test_a_submodule_s_filters_never_run(self):
        with tempfile.TemporaryDirectory() as upstream:
            sh(upstream, "git", "init", "-q", "-b", "main")
            sh(upstream, "git", "config", "user.email", "qa@example.com")
            sh(upstream, "git", "config", "user.name", "QA")
            Path(upstream, "f.txt").write_text("one\n")
            sh(upstream, "git", "add", "f.txt")
            sh(upstream, "git", "commit", "-q", "-m", "init")
            sh(self.repo.path, "git", "-c", "protocol.file.allow=always", "submodule", "add", "-q", upstream, "sub")
        sh(self.repo.path, "git", "commit", "-q", "-m", "sub")
        sh(self.repo.path, "git", "-C", "sub", "config", "filter.x.clean", f"sh -c 'touch {self.marker}; cat'")
        self.repo.write("sub/.gitattributes", "* filter=x\n")
        self.repo.write("sub/f.txt", "two\n")
        if not self.plain_git_runs_it("diff", "--numstat", "HEAD"):
            self.skipTest("this git doesn't run the submodule's filter, so there's nothing to prove")
        for command in ('git commit -am "Fix: x"', 'git commit -m "Fix: x" app.py', 'git commit -m "Fix: x" sub'):
            self.repo.check(command)
        self.assertFalse(self.marker.exists())

    def test_a_filter_named_with_odd_characters_never_runs(self):
        sh(self.repo.path, "git", "config", "filter.a=b.clean", f"sh -c 'touch {self.marker}; cat'")
        self.repo.write(".gitattributes", "* filter=a=b\n")
        self.repo.write("app.py", PRIVATE_KEY + "\n")
        if not self.plain_git_runs_it("diff", "--numstat", "HEAD"):
            self.skipTest("this git doesn't run the planted filter, so there's nothing to prove")
        for command in ('git commit -am "Fix: x"', 'git commit -m "Fix: x" app.py',
                        'git add app.py && git commit -m "Fix: x"'):
            self.assertEqual(self.repo.check(command)[0], "deny", command)
            self.assertFalse(self.marker.exists(), command)

    def test_a_link_turned_file_is_read(self):
        os.symlink("app.py", os.path.join(self.repo.path, "link"))
        sh(self.repo.path, "git", "add", "link")
        sh(self.repo.path, "git", "commit", "-q", "-m", "link")
        sh(self.repo.path, "git", "config", "filter.x.clean", f"sh -c 'touch {self.marker}; cat'")
        os.remove(os.path.join(self.repo.path, "link"))
        self.repo.write("link", PRIVATE_KEY + "\n")
        self.assertEqual(self.repo.check('git commit -am "Fix: x"')[0], "deny")
        self.assertFalse(self.marker.exists())

    def test_with_filters_set_the_guard_reads_files_itself(self):
        def decision(command):
            verdict = self.repo.check(command)
            self.assertFalse(self.marker.exists(), command)
            return verdict[0] if verdict else None

        def plain_git(*args):
            sh(self.repo.path, "git", *args)
            if self.marker.exists():
                self.marker.unlink()

        sh(self.repo.path, "git", "config", "filter.x.clean", f"sh -c 'touch {self.marker}; cat'")
        self.repo.write(".gitattributes", "*.py filter=x\n*.csv filter=x\n")
        self.repo.write("app.py", PRIVATE_KEY + "\n")
        self.repo.write("new.py", PRIVATE_KEY + "\n")
        for command in ('git commit -am "Fix: x"', 'git commit -m "Fix: x" app.py',
                        'git add new.py && git commit -m "Fix: x"', 'git add -u && git commit -m "Fix: x"'):
            self.assertEqual(decision(command), "deny", command)
        os.remove(os.path.join(self.repo.path, "new.py"))
        self.repo.write("app.py", f"x = 1\nmobile = {MOBILE}\n")
        for command in ('git commit -am "Fix: x"', 'git commit -m "Fix: x" app.py', 'git commit -i -m "Fix: x" app.py'):
            self.assertEqual(decision(command), "ask", command)
        plain_git("add", "app.py")
        self.assertEqual(decision('git commit -m "Fix: x" app.py'), "ask")
        self.repo.write("app.py", "x = 2\n")
        self.assertIsNone(decision('git commit -am "Fix: x"'))
        plain_git("add", "-f", ".claude/local/export.csv")
        plain_git("commit", "-q", "--no-verify", "-m", "tracked by mistake")
        self.repo.write(".claude/local/export.csv", "more rows\n")
        self.assertEqual(decision('git commit -am "Fix: x"'), "deny")
        plain_git("checkout", "--", ".claude/local/export.csv")
        app = os.path.join(self.repo.path, "app.py")
        os.remove(app)
        os.symlink("/dev/zero", app)
        self.assertIsNone(decision('git commit -am "Fix: x"'))
        os.remove(app)
        os.mkfifo(app)
        self.assertIsNone(decision('git commit -am "Fix: x"'))

    def test_a_planted_bare_repository_is_never_used(self):
        evil = Path(self.repo.path, "evil")
        sh(self.repo.path, "git", "init", "-q", "--bare", str(evil))
        self.plant(lambda key, value: sh(str(evil), "git", "config", key, value))
        sh(str(evil), "git", "config", "core.bare", "false")
        sh(str(evil), "git", "config", "core.worktree", self.repo.path)
        subprocess.run(["git", "-C", str(evil), "status"], capture_output=True)
        if not self.marker.exists():
            self.skipTest("this git doesn't use the planted repository, so there's nothing to prove")
        self.marker.unlink()
        for command in ('git -C evil commit -m "Fix: x"', "git -C evil add -f .", "cd evil && git commit -am x"):
            self.repo.check(command)
        self.assertFalse(self.marker.exists())


class Output(unittest.TestCase):
    def run_main(self, payload):
        stdin, out = sys.stdin, io.StringIO()
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            with redirect_stdout(out):
                self.assertEqual(guard.main(), 0)
        finally:
            sys.stdin = stdin
        return out.getvalue()

    def test_deny_json(self):
        out = json.loads(self.run_main({"tool_name": "Bash", "tool_input": {"command": "git clean -fdx"}, "cwd": "/"}))
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertEqual(spec["permissionDecision"], "deny")
        self.assertIn("git clean", spec["permissionDecisionReason"])

    def test_silent_when_allowed(self):
        self.assertEqual(self.run_main({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": "/"}), "")
        self.assertEqual(self.run_main({"tool_name": "Read", "tool_input": {}, "cwd": "/"}), "")

    def test_never_blocks_on_its_own_error(self):
        stdin, err = sys.stdin, io.StringIO()
        sys.stdin = io.StringIO("not json")
        try:
            with redirect_stderr(err), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(guard.main(), 0)
            self.assertEqual(out.getvalue(), "")
        finally:
            sys.stdin = stdin
        self.assertIn("internal error", err.getvalue())


class Helpers(unittest.TestCase):
    def test_verhoeff(self):
        self.assertTrue(guard.verhoeff_ok("2363"))
        self.assertFalse(guard.verhoeff_ok("2364"))

    def test_mask(self):
        self.assertEqual(guard.mask(MOBILE), "10 characters")
        self.assertEqual(guard.mask(PAN), "10 characters")
        self.assertEqual(guard.mask(EMAIL), EMAIL[:2] + "*" * (len(EMAIL) - 4) + EMAIL[-2:])

    def test_generated_values_are_flagged(self):
        self.assertFalse(guard.fake_pan(PAN))
        self.assertTrue(guard.PAN.fullmatch(PAN))
        self.assertTrue(guard.EMAIL.fullmatch(EMAIL))
        self.assertTrue(guard.verhoeff_ok(AADHAAR))


if __name__ == "__main__":
    unittest.main()
