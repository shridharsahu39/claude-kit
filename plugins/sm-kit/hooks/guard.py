#!/usr/bin/env python3
"""sm-kit's guard: a PreToolUse hook on every Bash command.

It stops the commands SprintMoney's guidance forbids, and checks what Claude is
about to commit:

- `git clean` with -x or -X is refused: it deletes .claude/local/, where the
  sensitive inputs live, and they exist nowhere else.
- `git add --force` (or `git stage`) is refused when it would stage an ignored
  file under .claude/local/.
- `git stash --all` is refused: it moves .claude/local/ into the stash, which
  every worktree and session shares.
- A recursive `rm` is refused when it would delete a .claude/local/ folder
  holding anything but its README, found up to a few folders down.
- A commit is refused when it carries files from .claude/local/, or added lines
  with a private key or a known token format.
- A commit asks the developer first when it adds a file that usually holds
  secrets (.env, a key or certificate store, site_config.json); a binary, data
  or image file; a file other than Markdown in a change record; a change to
  .claude/guard-allow.txt; a secret-looking value; or what looks like personal
  data: a PAN, an Aadhaar number, an Indian mobile number or a personal email
  address. Values listed in .claude/guard-allow.txt as of the last commit
  (synthetic test data) don't count. It also asks when it can't read the
  commit through git, or when the command points git at another repository,
  work tree or index (GIT_DIR, --git-dir and the like). Git aliases are
  followed. A commit is checked as the repository stands when the command
  starts, plus what a `git add` earlier in the same command line stages; any
  other change that command makes before it commits isn't seen.

The guard's own git never lets a repository's config run a command: no
fsmonitor, hooks, textconv or external diff; no index rewrite; no fetch, so a
partial clone's missing objects stay missing; no look inside submodules; no
bare repository found by searching; and none of Claude's options passed on.
Where a repository's own config sets filters that reading its working files
would run, the guard reads those files itself instead of through git.

It reads the shell's usual forms: wrappers such as `sudo` and `timeout`,
reserved words, subshells, `cd -`, variables the same line sets, `xargs`, and
git's abbreviated long options. Where the shell builds a path the guard can't
resolve, it refuses an `rm` that names .claude and asks about one near
.claude/local/ data. It's a check against mistakes and known tricks, not a
sandbox: a determined agent can still get past it.

Everything else passes untouched. If the guard fails on a command, or runs past
its time limit, that command asks; only when the hook's own input can't be read
does a command pass, with a note on stderr. Standard library only; Python 3.8
or later.
"""
import glob
import hashlib
import itertools
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time

GIT_TIMEOUT = 20
TIME_LIMIT = 20  # for a whole command line, well inside the hook's 30-second timeout
MAX_ALIASES = 20
MAX_FINDINGS = 12
MAX_LINES = 200_000
MAX_SCAN_CHARS = 5_000_000
WINDOW, OVERLAP = 4000, 200
RM_DEPTH, RM_MAX_DIRS = 4, 3000

LOCAL_FILE = re.compile(r"(?:^|/)\.claude/local/(?!README\.md$)")
SECRET_FILE = re.compile(
    r"(?:^|/)(?:\.env(?:\.[\w.-]+)?|[^/]+\.(?:pem|key|p12|pfx|jks|keystore)"
    r"|id_(?:rsa|dsa|ecdsa|ed25519)|(?:common_)?site_config\.json)$"
)
SECRET_FILE_EXAMPLE = re.compile(r"(?:^|/)\.env\.(?:example|sample|template|dist)$")
DATA_FILE = re.compile(
    r"\.(?:csv|tsv|xlsx?|xlsm|ods|dbf|zip|gz|tgz|bz2|xz|7z|rar|pdf|docx?|sql|dump|bak|har|sqlite3?|db"
    r"|parquet|jpe?g|png|gif|webp|heic|bmp|tiff?)$",
    re.IGNORECASE,
)
RECORD_FILE = re.compile(r"(?:^|/)\.claude/changes/.")
ALLOW_FILE = ".claude/guard-allow.txt"
NO_CONTENT_SCAN = re.compile(
    r"(?:^|/)(?:package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock)$"
    r"|\.(?:min\.js|map)$"
)
# Config keys that make reading working files run a command. A driver's name can hold any
# character, "=" and "." included, so only the key's end is matched; git-lfs runs a
# repository's lfs.extension commands through the developer's own lfs filter.
CONFIG_RUNS_COMMANDS = re.compile(
    r"^(?:filter\..*\.(?:clean|smudge|process)|diff\.external|diff\..*\.(?:textconv|command)|lfs\..+)$",
    re.IGNORECASE | re.DOTALL,
)

HARD = [
    ("a private key", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY(?: BLOCK)?-----")),
    ("a GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})")),
    ("an AWS access key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("a Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("a Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("a live payment key", re.compile(r"\b(?:[sr]k_live_[0-9A-Za-z]{20,}|rzp_live_[A-Za-z0-9]{14,})")),
    ("an AI provider key", re.compile(r"\b(?:sk-ant-[A-Za-z0-9_\-]{20,}|sk-proj-[A-Za-z0-9_\-]{20,})")),
]

SECRET_NAME = (
    r"(?:pass(?:word|wd)?|pwd|secret|api[_-]?key|apikey|access[_-]?key|auth[_-]?token|token"
    r"|private[_-]?key|client[_-]?secret|encryption[_-]?key|jwt[_-]?secret)"
)
# Every repeat is bounded, so a long run of word characters can't make a scan take minutes.
QUOTED_SECRET = re.compile(
    r"(?i)\b\w{0,40}" + SECRET_NAME + r"\w{0,40}[\"']?\s{0,20}[:=]\s{0,20}[\"']([^\"'\s]{8,512})[\"']"
)
BARE_SECRET = re.compile(
    r"(?i)^\s{0,40}(?:export\s+)?[\w.-]{0,60}" + SECRET_NAME
    + r"[\w.-]{0,60}\s{0,20}[:=]\s{0,20}([^\s\"'#,;(){}<>$\[\]]{12,512})\s*(?:#.*)?$"
)
PLACEHOLDER = re.compile(
    r"(?i)^(?:x+|\*+|\.+|<.*>|\$\{.*\}|\{\{.*\}\}|%\(.*\)s)$|example|placeholder|changeme|dummy|your[_-]|redacted"
)
JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,4096}\.eyJ[A-Za-z0-9_-]{10,4096}\.[A-Za-z0-9_-]{10,4096}")
FRAPPE_TOKEN = re.compile(r"(?i)\btoken\s+([0-9a-f]{15}:[0-9a-f]{15})\b")
PAN = re.compile(r"\b[A-Z]{3}[ABCFGHJLPT][A-Z][0-9]{4}[A-Z]\b")
AADHAAR = re.compile(r"(?<!\w)([2-9][0-9]{3})[ -]?([0-9]{4})[ -]?([0-9]{4})(?!\w)")
MOBILE = re.compile(r"(?<![\w+])(?:\+91[\s-]?|91[\s-]|0)?([6-9][0-9]{9})(?!\w)")
EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]{1,64}@(?:gmail|googlemail|yahoo|ymail|rocketmail|hotmail|outlook|live|msn"
    r"|icloud|me|aol|rediffmail|protonmail|proton)\.[A-Za-z.]{2,6}\b",
    re.IGNORECASE,
)

_VD = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6], [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4], [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VP = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2], [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


class GitError(Exception):
    pass


class OutOfTime(Exception):
    """The check ran past TIME_LIMIT: the command asks rather than wait for the hook's timeout."""


CLOCK = {"deadline": None, "aliases": 0}


def start_clock():
    CLOCK.update(deadline=time.monotonic() + TIME_LIMIT, aliases=0)


def time_left():
    if CLOCK["deadline"] is None:
        return GIT_TIMEOUT
    left = CLOCK["deadline"] - time.monotonic()
    if left <= 0:
        raise OutOfTime()
    return min(GIT_TIMEOUT, left)


def verhoeff_ok(digits):
    check = 0
    for i, ch in enumerate(reversed(digits)):
        check = _VD[check][_VP[i % 8][int(ch)]]
    return check == 0


def fake_digits(digits):
    """Obviously fake: one or two distinct digits, or a run like 0123… or 9876…."""
    return (
        len(set(digits)) <= 2
        or digits in "0123456789012345678901"
        or digits in "9876543210987654321098"
    )


def fake_pan(pan):
    return fake_digits(pan[5:9]) or len(set(pan[:5])) <= 2


def secret_value(value):
    """True when a value looks like a real secret, not a name, URL or placeholder."""
    if PLACEHOLDER.search(value) or "://" in value or value.startswith(("/", "./", "../")):
        return False
    if re.fullmatch(r"[A-Za-z_]+", value):
        return False
    return bool(re.search(r"\d", value) and re.search(r"[A-Za-z]", value)) or len(value) >= 24


def mask(value):
    """A value's shape, never enough of it to tell whose it is."""
    value = value.strip()
    if len(value) < 12:
        return f"{len(value)} characters"
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def normalise(value):
    return re.sub(r"[\s-]", "", value).upper()


def plural(n, noun):
    return f"{n} {noun}" + ("" if n == 1 else "s")


# The guard's own git: a repository's config can't make it run anything, or
# change how a diff reads. Settings given with -c win over every config file
# and reach the git processes git starts.

SAFE_CONFIG = [
    "-c", "core.quotePath=false",
    "-c", "core.fsmonitor=false",
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.bigFileThreshold=512m",
    "-c", "safe.bareRepository=explicit",
    "-c", "diff.autoRefreshIndex=false",
    "-c", "diff.relative=false",
    "-c", "diff.interHunkContext=0",
]
SAFE_ENV = {
    "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GIT_EDITOR": "true", "GIT_PAGER": "cat",
    "GIT_NO_REPLACE_OBJECTS": "1",
    # No transport at all, whatever the repository's protocol settings: a promisor remote's
    # lazy fetch would run its upload-pack or ssh command. Git's May 2024 security releases
    # (2.39.4 to 2.45.1) and later also honour GIT_NO_LAZY_FETCH.
    "GIT_ALLOW_PROTOCOL": "none", "GIT_NO_LAZY_FETCH": "1",
    # Only absolute folders: an empty or relative PATH entry would let git run a helper
    # (git-remote-<name>) from the repository itself.
    "PATH": os.pathsep.join(p for p in os.environ.get("PATH", "").split(os.pathsep) if os.path.isabs(p))
    or "/usr/bin:/bin",
}


def git_bytes(cwd, *args):
    result = subprocess.run(
        ["git", *SAFE_CONFIG, "-C", cwd, *args],
        capture_output=True, timeout=time_left(), stdin=subprocess.DEVNULL, env={**os.environ, **SAFE_ENV},
    )
    if result.returncode != 0:
        raise GitError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def git(cwd, *args):
    """git's output as text: no newline translation, and bytes that aren't UTF-8 (a file's
    name, a stray byte in a line) kept as they are, so paths still open and lines still split
    only where git split them."""
    return git_bytes(cwd, *args).decode("utf-8", "surrogateescape")


def repo_config_runs_commands(cwd):
    """True when the repository's own config, not the developer's, sets a filter or diff driver."""
    try:
        listed = git(cwd, "config", "--list", "-z", "--show-scope", "--includes")
    except (GitError, OSError, subprocess.TimeoutExpired):
        return True
    fields = listed.split("\0")  # scope, then key and value split by a newline, for each setting
    for scope, setting in zip(fields[0::2], fields[1::2]):
        if scope not in ("system", "global") and CONFIG_RUNS_COMMANDS.match(setting.partition("\n")[0]):
            return True
    return False


# Splitting a command line into simple commands.

WRAPPERS = {"sudo", "env", "nohup", "time", "command", "exec", "nice", "stdbuf", "timeout", "builtin"}
WRAPPER_VALUE_OPTIONS = {
    "sudo": {"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt", "-C", "--close-from",
             "-D", "--chdir", "-r", "--role", "-t", "--type", "-T", "--command-timeout", "-U", "--other-user"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "timeout": {"-k", "--kill-after", "-s", "--signal"},
    "nice": {"-n", "--adjustment"},
    "stdbuf": {"-i", "--input", "-o", "--output", "-e", "--error"},
    "time": {"-f", "--format", "-o", "--output"},
    "exec": {"-a"},
}
CHDIR_OPTIONS = {"env": {"-C", "--chdir"}, "sudo": {"-D", "--chdir"}}
DURATION = re.compile(r"\d+(?:\.\d+)?[smhd]?")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SHELLS = {"bash", "sh", "zsh", "dash"}
OPERATORS = {"&&", "||", ";", "|", "&", "(", ")", ";;", "|&", ";&"}
REDIRECT = re.compile(r"^\d*(?:>>?|<<?|&>)(.*)$")
SHELL_PATH_VARIABLE = re.compile(r"\$(?:\{(HOME|PWD)\}|(HOME|PWD)(?![A-Za-z0-9_]))")
VARIABLE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
# What's left of a word the shell would still build: a variable this line didn't set, a
# command's output, a brace list, or ~+ and ~-.
UNRESOLVED = re.compile(r"[$`{]|^~[+-]")
RESERVED = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for", "in", "case", "esac",
            "select", "function", "coproc", "{", "}", "!"}
DECLARE = {"export", "declare", "local", "readonly", "typeset"}
# Environment that points git at another repository, work tree or index, or adds config.
GIT_REDIRECT = re.compile(
    r"\bGIT_(?:DIR|WORK_TREE|INDEX_FILE|COMMON_DIR|OBJECT_DIRECTORY|CONFIG(?:_COUNT|_PARAMETERS|_GLOBAL|_SYSTEM)?)="
)


def expand(path, cwd):
    """path as the shell would resolve it from cwd: ~, $HOME and $PWD expanded."""
    path = SHELL_PATH_VARIABLE.sub(
        lambda m: cwd if (m.group(1) or m.group(2)) == "PWD" else os.path.expanduser("~"), path)
    return os.path.normpath(os.path.join(cwd, os.path.expanduser(path)))


def _unquoted_newlines_to_semicolons(command):
    out, quote, escape = [], None, False
    for ch in command:
        if escape:
            out.append(ch)
            escape = False
        elif ch == "\\" and quote != "'":
            out.append(ch)
            escape = True
        elif quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in "'\"":
            out.append(ch)
            quote = ch
        elif ch == "\n":
            out.append(" ; ")
        else:
            out.append(ch)
    return "".join(out)


def _tokens(command):
    command = command.replace("\\\n", " ")
    command = re.sub(r"\d*>&\d+|&>", " ", command)
    lexer = shlex.shlex(_unquoted_newlines_to_semicolons(command), posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def _drop_redirections(argv):
    out, skip = [], False
    for token in argv:
        if skip:
            skip = False
            continue
        m = REDIRECT.match(token)
        if m:
            skip = not m.group(1)
            continue
        out.append(token)
    return out


def unwrap(argv, cwd):
    """Strip wrappers such as `sudo -u x`, `timeout 30s` or `env -C dir` from argv.

    Returns (argv, cwd, nested): nested is the command line an `env -S` holds.
    """
    while argv and os.path.basename(argv[0]) in WRAPPERS:
        wrapper, argv = os.path.basename(argv[0]), argv[1:]
        takes = WRAPPER_VALUE_OPTIONS.get(wrapper, set())
        split = None
        while argv:
            arg = argv[0]
            if arg == "--":
                argv = argv[1:]
                break
            if wrapper == "env" and ASSIGNMENT.match(arg):
                argv = argv[1:]
                continue
            if not arg.startswith("-") or arg == "-":
                break
            name, value = arg, None
            if arg.startswith("--") and "=" in arg:
                name, value = arg.split("=", 1)
            elif not arg.startswith("--") and len(arg) > 2 and arg[:2] in takes:
                name, value = arg[:2], arg[2:]
            argv = argv[1:]
            if name in takes and value is None:
                value, argv = (argv[0], argv[1:]) if argv else ("", argv)
            if value and name in CHDIR_OPTIONS.get(wrapper, ()):
                cwd = expand(value, cwd)
            if wrapper == "env" and name in ("-S", "--split-string"):
                split = value or ""
        if wrapper == "timeout" and argv and DURATION.fullmatch(argv[0]):
            argv = argv[1:]
        if split is not None:
            return [], cwd, " ".join([split] + [shlex.quote(a) for a in argv])
    return argv, cwd, None


def substitute(word, variables):
    """word with the variables in variables replaced; any other stays as written."""
    return VARIABLE.sub(lambda m: variables.get(m.group(1) or m.group(2), m.group(0)), word)


def simple_commands(command, cwd, depth=0, uncertain=False):
    """Yield (argv, cwd, uncertain) for each simple command.

    Follows `cd` (and `cd -`), subshells, reserved words such as `then` and `{`,
    variables the same line sets, wrappers and `bash -c`. uncertain turns True
    once a `cd` goes somewhere the guard can't resolve; cwd is then its best guess.
    """
    try:
        tokens = _tokens(command)
    except ValueError:
        tokens = command.split()
    variables = {"HOME": os.path.expanduser("~")}
    argv, previous, saved = [], cwd, []
    for token in tokens + [";"]:
        if token not in OPERATORS:
            argv.append(token)
            continue
        argv = [substitute(word, {**variables, "PWD": cwd, "OLDPWD": previous}) for word in _drop_redirections(argv)]
        while argv and argv[0] in RESERVED:
            argv = argv[1:]
        assigned = []
        while argv and ASSIGNMENT.match(argv[0]):
            assigned.append(argv.pop(0))
        if not argv or os.path.basename(argv[0]) in DECLARE:
            for word in assigned + argv[1:]:
                if ASSIGNMENT.match(word):
                    name, _, value = word.partition("=")
                    variables[name] = value
            argv = []
        argv, here, nested = unwrap(argv, cwd)
        if nested is not None:
            if depth < 3:
                yield from simple_commands(nested, here, depth + 1, uncertain)
        elif argv:
            name = os.path.basename(argv[0])
            if name in ("cd", "pushd"):
                target = argv[1] if len(argv) > 1 else "~"
                if target == "-":
                    previous, cwd = cwd, previous
                elif UNRESOLVED.search(target):
                    uncertain = True
                else:
                    previous, cwd = cwd, expand(target, here)
            elif name in SHELLS and "-c" in argv[1:] and depth < 3:
                i = argv.index("-c")
                if i + 1 < len(argv):
                    yield from simple_commands(argv[i + 1], here, depth + 1, uncertain)
            elif name == "eval" and depth < 3:
                yield from simple_commands(" ".join(argv[1:]), here, depth + 1, uncertain)
            else:
                yield argv, here, uncertain
        if token == "(":
            saved.append((cwd, previous, uncertain))
        elif token == ")" and saved:
            cwd, previous, uncertain = saved.pop()  # a subshell's `cd` ends with it
        argv = []


# The checks.

def deny(reason):
    return "deny", "sm-kit's guard: " + reason


def ask_redirected(what):
    return "ask", (
        f"sm-kit's guard: this {what} points git at another repository, work tree or index (GIT_DIR, "
        "--git-dir and the like), so the guard can't check it. Check what it stages or commits before approving."
    )


def long_option(arg, names):
    """The option in names that arg spells: git takes any unambiguous start of one (`--forc`)."""
    if not arg.startswith("--") or len(arg) < 3:
        return None
    spelled = arg[2:].split("=", 1)[0]
    if spelled in names:
        return spelled
    return next((name for name in names if name.startswith(spelled)), None)


def options(args, with_value="", long_with_value=(), long_names=()):
    """(short flags, long options) in args, up to `--`.

    Short flags come as one string. Long options come as the names in long_names
    or long_with_value they spell. A letter in with_value takes a value: the rest
    of its cluster, or the next argument; so does an option in long_with_value
    written without `=`. Values are skipped, never read as options.
    """
    flags, longs, i = [], [], 0
    names = tuple(long_names) + tuple(long_with_value)
    while i < len(args):
        arg = args[i]
        if arg == "--":
            break
        if arg.startswith("--"):
            name = long_option(arg, names)
            if name:
                longs.append(name)
            if name in long_with_value and "=" not in arg:
                i += 1
        elif re.fullmatch(r"-[A-Za-z].*", arg):
            for j, ch in enumerate(arg[1:], 1):
                if ch in with_value:
                    if j == len(arg) - 1:
                        i += 1
                    break
                flags.append(ch)
        i += 1
    return "".join(flags), longs


def short_options(args, with_value="", long_with_value=()):
    return options(args, with_value, long_with_value)[0]


def option_values(args, letter, name):
    """Every value given to -<letter> or --<name> in args, up to `--`."""
    values, i = [], 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            break
        if long_option(arg, (name,)):
            if "=" in arg:
                values.append(arg.split("=", 1)[1])
            elif i + 1 < len(args):
                values.append(args[i + 1])
                i += 1
        elif re.fullmatch(r"-[A-Za-z].*", arg) and letter in arg[1:]:
            rest = arg[arg.index(letter, 1) + 1:]
            if rest:
                values.append(rest)
            elif i + 1 < len(args):
                values.append(args[i + 1])
                i += 1
        i += 1
    return values


def check_clean(args):
    flags, longs = options(args, with_value="e", long_with_value=("exclude",), long_names=("dry-run",))
    if "n" in flags or "dry-run" in longs:
        return None
    if "x" in flags or "X" in flags:
        return deny(
            "`git clean -x` deletes ignored files, and .claude/local/ is ignored: it holds sensitive "
            "inputs that exist nowhere else. Run `git clean` without -x or -X, or ask the developer."
        )
    if any(value.startswith("!") for value in option_values(args, "e", "exclude")):
        return deny(
            "`git clean -e '!…'` stops ignoring what it names, so it deletes ignored files, .claude/local/ "
            "among them. Run `git clean` without it, or ask the developer."
        )
    return None


ADD_VALUE_OPTIONS = ("chmod", "pathspec-from-file")
ADD_OPTIONS = ("force", "dry-run", "all", "no-ignore-removal", "update", "interactive", "patch")


def add_pathspecs(args):
    paths, i, after = [], 0, False
    while i < len(args):
        arg = args[i]
        if after or not arg.startswith("-") or arg == "-":
            paths.append(arg)
        elif arg == "--":
            after = True
        elif long_option(arg, ADD_VALUE_OPTIONS) and "=" not in arg:
            i += 1
        i += 1
    return paths


def add_targets(args, unknown=False):
    """What a `git add` stages, as (pathspecs, untracked files too, ignored files too), or None.

    unknown: its paths come from elsewhere (xargs), so it may stage anything.
    """
    flags, longs = options(args, long_with_value=ADD_VALUE_OPTIONS, long_names=ADD_OPTIONS)
    if "n" in flags or "dry-run" in longs:
        return None
    force, update = "f" in flags or "force" in longs, "u" in flags or "update" in longs
    paths = add_pathspecs(args)
    if unknown or "pathspec-from-file" in longs or any(UNRESOLVED.search(p) for p in paths):
        return [":/"], not update, force
    if paths:
        return paths, not update, force
    if "A" in flags or "i" in flags or {"all", "no-ignore-removal", "interactive"} & set(longs):
        return [":/"], True, force
    if update or "p" in flags or "patch" in longs:
        return [":/"], False, force
    return None


def check_add(cwd, args, redirected=False):
    flags, longs = options(args, long_with_value=ADD_VALUE_OPTIONS, long_names=ADD_OPTIONS)
    if not ("f" in flags or "force" in longs) or "n" in flags or "dry-run" in longs:
        return None
    if redirected:
        return ask_redirected("`git add --force`")
    paths = add_pathspecs(args)
    if "pathspec-from-file" in longs or any(UNRESOLVED.search(p) for p in paths):
        return "ask", (
            "sm-kit's guard: this `git add --force` takes its paths from a file or from the shell, so the guard "
            "can't tell whether it stages anything from .claude/local/. Check the paths first."
        )
    if not paths:
        if not ("A" in flags or {"all", "no-ignore-removal"} & set(longs)):
            return None
        paths = [":/"]
    try:
        listed = git(cwd, "ls-files", "-z", "--full-name", "--others", "--ignored", "--exclude-standard",
                     "--", *paths).split("\0")
    except (GitError, OSError, subprocess.TimeoutExpired):
        listed = paths
    local = [p for p in listed if p and (LOCAL_FILE.search(p) or p.rstrip("/").endswith(".claude/local"))]
    if local:
        return deny(
            f"this `git add --force` would stage {plural(len(local), 'file')} from .claude/local/, which "
            "never goes into a commit. Stage files outside it, or ask the developer."
        )
    return None


def check_stash(args):
    if args and not args[0].startswith("-"):
        sub, rest = args[0], args[1:]
    else:
        sub, rest = "push", args
    if sub not in ("push", "save"):
        return None
    flags, longs = options(rest, with_value="m", long_with_value=("message", "pathspec-from-file"),
                           long_names=("all",))
    if "a" in flags or "all" in longs:
        return deny(
            "`git stash --all` moves ignored files, .claude/local/ among them, into the stash, which every "
            "worktree and session shares: a drop or a failed pop loses them. Stash without -a (-u takes "
            "untracked files), or ask the developer."
        )
    return None


HEAVY_DIRS = {"node_modules", "env", "venv", "dist", "build", "logs", "__pycache__", "coverage"}
GLOB = re.compile(r"[*?\[]")


def is_local_folder(path):
    return os.path.basename(path) == "local" and os.path.basename(os.path.dirname(path)) == ".claude"


def local_has_data(folder):
    """True when a .claude/local/ folder holds anything but its README."""
    try:
        with os.scandir(folder) as entries:
            return any(e.name != "README.md" for e in entries)
    except OSError:
        return False


def holds_local(path):
    """True when deleting path would delete a .claude/local/ folder with something in it.

    Looks RM_DEPTH folders down, breadth first, past hidden and generated folders.
    A search too large to finish lets the command through.
    """
    if "/.claude/worktrees/" in path + "/":
        return False
    name = os.path.basename(path)
    if is_local_folder(path):
        return local_has_data(path)
    if name == ".claude":
        return local_has_data(os.path.join(path, "local"))
    queue, visited = [(path, 0)], 0
    while queue and visited < RM_MAX_DIRS:
        here, depth = queue.pop(0)
        visited += 1
        if visited % 200 == 0:
            time_left()
        if local_has_data(os.path.join(here, ".claude", "local")):
            return True
        if depth >= RM_DEPTH:
            continue
        try:
            with os.scandir(here) as entries:
                queue += [(e.path, depth + 1) for e in entries
                          if e.is_dir(follow_symlinks=False) and not e.name.startswith(".")
                          and e.name not in HEAVY_DIRS]
        except OSError:
            continue
    return False


def repo_root(path):
    """The nearest folder at or above path that holds a .git, found without running git."""
    while True:
        if os.path.exists(os.path.join(path, ".git")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def check_rm(argv, cwd, uncertain=False, unknown=False):
    """unknown: the targets come from elsewhere (xargs); uncertain: cwd is only the guard's best guess."""
    args = argv[1:]
    flags, longs = options(args, long_names=("recursive",))
    if not ("r" in flags or "R" in flags or "recursive" in longs):
        return None
    targets, after = ["the paths xargs supplies"] if unknown else [], False
    for a in args:
        if after or not a.startswith("-"):
            targets.append(a)
        elif a == "--":
            after = True
    for target in targets:
        if unknown or UNRESOLVED.search(target) or (uncertain and not os.path.isabs(os.path.expanduser(target))):
            if ".claude" in target:
                return deny(
                    f"this `rm` deletes {target}, a path the shell builds, and it names .claude: it may delete "
                    ".claude/local/, whose sensitive inputs exist nowhere else. Spell the path out, or ask the "
                    "developer."
                )
            if holds_local(repo_root(cwd) or cwd):
                return "ask", (
                    f"sm-kit's guard: this `rm` deletes {target}, a path the shell builds, where a .claude/local/ "
                    "folder holds sensitive inputs that exist nowhere else. Check what it resolves to before "
                    "approving."
                )
            continue
        stripped = re.sub(r"(?:/\*)+/?$", "", target.rstrip("/")) or target
        path = expand(stripped, cwd)
        head, tail = os.path.split(path)
        if GLOB.search(tail) and is_local_folder(head):
            path = head  # any wildcard straight inside .claude/local/ can empty it
        paths = sorted(glob.glob(path))[:200] if GLOB.search(path) else []
        if any(holds_local(p) for p in paths or [path]):
            return deny(
                f"this `rm` would delete {target}, which is or holds a .claude/local/ folder: sensitive "
                "inputs that exist nowhere else. Delete specific files inside it, or ask the developer."
            )
    return None


FIND_RUNS = ("-exec", "-execdir", "-ok", "-okdir")


def check_find(argv, cwd, uncertain=False):
    """A `find` that deletes what it matches (-delete, or -exec rm): the guard can't tell what its
    expression matches, so it refuses one that names .claude, and asks about one that searches
    a folder holding .claude/local/ data."""
    args = argv[1:]
    runs_rm = any(arg in FIND_RUNS and os.path.basename(nxt) == "rm" for arg, nxt in zip(args, args[1:]))
    if "-delete" not in args and not runs_rm:
        return None
    if any(".claude" in arg for arg in args):
        return deny(
            "this `find` deletes what it matches, and it names .claude: it may delete .claude/local/, whose "
            "sensitive inputs exist nowhere else. Delete specific files instead, or ask the developer."
        )
    starts = list(itertools.takewhile(lambda a: not a.startswith(("-", "(", "!", ")")), args)) or ["."]
    if uncertain or any(UNRESOLVED.search(start) for start in starts):
        starts = [repo_root(cwd) or cwd]
    if any(holds_local(expand(start, cwd)) for start in starts):
        return "ask", (
            "sm-kit's guard: this `find` deletes what it matches in a folder that holds .claude/local/ data, "
            "sensitive inputs that exist nowhere else. Check what it matches (run it without the delete) "
            "before approving."
        )
    return None


COMMIT_VALUE_OPTIONS = ("message", "file", "reuse-message", "reedit-message", "template", "author", "date",
                        "fixup", "squash", "cleanup", "trailer", "pathspec-from-file")


def parse_commit(args):
    """What a `git commit` takes from where. --patch and --interactive count as -a: they commit
    working-tree changes, whichever parts the prompts pick."""
    spec = {"all": False, "include": False, "from_file": False, "paths": [], "messages": []}
    i, after = 0, False
    while i < len(args):
        a = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else ""
        if after:
            spec["paths"].append(a)
        elif a == "--":
            after = True
        elif a.startswith("--"):
            name = long_option(a, ("all", "include", "patch", "interactive") + COMMIT_VALUE_OPTIONS)
            if name in ("all", "patch", "interactive"):
                spec["all"] = True
            elif name == "include":
                spec["include"] = True
            elif name in COMMIT_VALUE_OPTIONS:
                value = a.split("=", 1)[1] if "=" in a else nxt
                if "=" not in a:
                    i += 1
                if name == "message":
                    spec["messages"].append(value)
                elif name == "pathspec-from-file":
                    spec["from_file"] = True
        elif re.fullmatch(r"-[A-Za-z].*", a):
            for j, ch in enumerate(a[1:], 1):
                if ch in "ap":
                    spec["all"] = True
                elif ch == "i":
                    spec["include"] = True
                elif ch in "mFCct":
                    value = a[j + 1:]
                    if not value:
                        value = nxt
                        i += 1
                    if ch == "m":
                        spec["messages"].append(value)
                    break
        else:
            spec["paths"].append(a)
        i += 1
    return spec


DIFF_OPTIONS = ["--no-color", "--no-renames", "--no-ext-diff", "--no-textconv", "--ignore-submodules=all",
                "--diff-filter=d"]


def changed_files(cwd, revs, paths):
    """(path, is binary) for each file the commit adds or changes; deletions don't count."""
    out = git(cwd, "diff", "--numstat", "-z", *DIFF_OPTIONS, *revs, "--", *paths)
    files = []
    for entry in filter(None, out.split("\0")):
        added, _, rest = entry.partition("\t")
        files.append((rest.partition("\t")[2], added == "-"))
    return files


HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def added_lines(cwd, revs, paths, text=False):
    """Yield (path, line number, text) for each added line, counting each hunk's lines.

    text: read every file as text, for files git takes for binary only because
    attributes or config say so.
    """
    out = git(cwd, "diff", "-U0", "--src-prefix=a/", "--dst-prefix=b/", *(["--text"] if text else []),
              *DIFF_OPTIONS, *revs, "--", *paths)
    path, lineno, old_left, new_left = None, 0, 0, 0
    for line in out.split("\n"):
        if (old_left > 0 or new_left > 0) and line.startswith("diff --git "):
            old_left = new_left = 0  # the hunk ended sooner than its header said: read on as headers
        if old_left > 0 or new_left > 0:
            if line.startswith("-"):
                old_left -= 1
            elif line.startswith(" "):
                lineno += 1
                old_left -= 1
                new_left -= 1
            elif not line.startswith("\\"):
                # an added line, or one git shouldn't have written here: scan it either way
                if path is not None:
                    yield path, lineno, line[1:] if line.startswith("+") else line
                lineno += 1
                new_left -= 1
            continue
        if line.startswith("diff --git "):
            path = None
        elif line.startswith("+++ "):
            name = line[4:]
            path = None if name == "/dev/null" else (name[2:] if name.startswith("b/") else name)
        elif line.startswith("@@"):
            m = HUNK.match(line)
            if m:
                old_left = int(m.group(1)) if m.group(1) is not None else 1
                lineno = int(m.group(2))
                new_left = int(m.group(3)) if m.group(3) is not None else 1


def holds_nul(top, revs, path):
    """True when the version of path a commit takes holds a NUL byte, or can't be read.

    Git's own idea of binary follows attributes and config a repository sets, so a
    file it calls binary is read here before the guard believes it.
    """
    try:
        if revs == ["--cached"]:
            if int(git(top, "cat-file", "-s", ":" + path)) > MAX_SCAN_CHARS:
                return True
            data = git_bytes(top, "cat-file", "blob", ":" + path)[:8000]
        else:
            full = os.path.join(top, path)
            if not stat.S_ISREG(os.lstat(full).st_mode):
                return True
            with open(full, "rb") as f:
                data = f.read(8000)
    except (GitError, OSError, ValueError, subprocess.TimeoutExpired):
        return True
    return b"\0" in data


def blob_id(path, size, hexlen):
    """The id git gives a file's bytes as a blob, worked out here so that no filter runs."""
    digest = hashlib.sha1() if hexlen == 40 else hashlib.sha256()
    digest.update(b"blob %d\0" % size)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def working_file(top, path, old=None):
    """(path, binary, lines) for a working file, read from disk so that no filter runs.

    old is its HEAD version as (blob id, size); lines holds (path, line number,
    text) for each line that version lacks. None when the file matches old, is
    gone, or isn't a regular file: a link commits only its target's name, and a
    device or pipe is never read.
    """
    full = os.path.join(top, path)
    try:
        info = os.lstat(full)
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    size = info.st_size
    if old and old[1] == size <= MAX_SCAN_CHARS and blob_id(full, size, len(old[0])) == old[0]:
        return None
    if LOCAL_FILE.search(path) or size > MAX_SCAN_CHARS:
        return path, size > MAX_SCAN_CHARS, ()
    with open(full, "rb") as f:
        data = f.read(MAX_SCAN_CHARS + 1)
    if b"\0" in data[:8000] or len(data) > MAX_SCAN_CHARS:
        return path, True, ()
    known = set(git(top, "cat-file", "blob", old[0]).splitlines()) if old else set()
    return path, False, [(path, n, text) for n, text in enumerate(data.decode("utf-8", "replace").splitlines(), 1)
                         if text not in known]


def disk_changes(cwd, top, paths):
    """working_file() for each tracked file in paths whose working copy differs from HEAD.

    For a repository whose own filters git would run to read its working files:
    git only lists what HEAD and the index hold.
    """
    head = {}
    for entry in filter(None, git(top, "ls-tree", "-r", "-l", "-z", "--full-tree", "HEAD").split("\0")):
        meta, _, path = entry.partition("\t")
        _, _, sha, size = meta.split()
        head[path] = (sha, int(size) if size.isdigit() else -1)
    seen = set()
    for entry in filter(None, git(cwd, "ls-files", "-z", "--stage", "--full-name", "--", *paths).split("\0")):
        meta, _, path = entry.partition("\t")
        if path in seen or meta.startswith("160000"):  # not submodules; working_file() goes by what's on disk
            continue
        seen.add(path)
        found = working_file(top, path, head.get(path))
        if found:
            yield found


def new_files(cwd, top, paths, tracked=False, ignored=False):
    """working_file() for each file in paths that git doesn't track yet: with ignored, those
    .gitignore names too (what `git add -f` stages); with tracked, each it does track."""
    listing = ["--others"] + ([] if ignored else ["--exclude-standard"]) + (["--cached"] if tracked else [])
    for path in filter(None, git(cwd, "ls-files", "-z", "--full-name", *listing, "--", *paths).split("\0")):
        found = working_file(top, path)
        if found:
            yield found


def load_allow(cwd):
    """The synthetic values .claude/guard-allow.txt lists as of the last commit."""
    try:
        text = git(cwd, "cat-file", "-p", "HEAD:" + ALLOW_FILE)
    except (GitError, OSError, subprocess.TimeoutExpired):
        return set()
    return {normalise(line.split("#", 1)[0]) for line in text.splitlines() if line.split("#", 1)[0].strip()}


def windows(text):
    """The text in overlapping pieces, so a long line is scanned whole."""
    if len(text) <= WINDOW:
        yield text
        return
    for start in range(0, len(text), WINDOW - OVERLAP):
        yield text[start:start + WINDOW]
        if start + WINDOW >= len(text):
            break


def scan(where, path, text, allow, findings):
    for kind, rx in HARD:
        if rx.search(text):
            findings.append(("deny", f"{where}: {kind}"))
    if NO_CONTENT_SCAN.search(path):
        return
    seen = set()

    def add(kind, value):
        key = normalise(value)
        if key in allow or (kind, key) in seen:
            return
        seen.add((kind, key))
        findings.append(("ask", f"{where}: {kind} ({mask(value)})"))

    m = BARE_SECRET.match(text) if len(text) <= WINDOW else None
    if m and secret_value(m.group(1)):
        add("a secret-looking value", m.group(1))
    for part in windows(text):
        for m in QUOTED_SECRET.finditer(part):
            if secret_value(m.group(1)):
                add("a secret-looking value", m.group(1))
        for m in JWT.finditer(part):
            add("a token (JWT)", m.group(0))
        for m in FRAPPE_TOKEN.finditer(part):
            add("a Frappe API key and secret", m.group(1))
        for m in PAN.finditer(part):
            if not fake_pan(m.group(0)):
                add("a PAN", m.group(0))
        for m in AADHAAR.finditer(part):
            digits = "".join(m.groups())
            if verhoeff_ok(digits) and not fake_digits(digits):
                add("an Aadhaar-like number", digits)
        for m in MOBILE.finditer(part):
            if not fake_digits(m.group(1)):
                add("a mobile number", m.group(1))
        for m in EMAIL.finditer(part):
            add("a personal email address", m.group(0))


def check_commit(cwd, args, added=(), uncertain=False):
    try:
        top = git(cwd, "rev-parse", "--show-toplevel").strip()
    except (GitError, OSError, subprocess.TimeoutExpired):
        if uncertain:
            return "ask", (
                "sm-kit's guard: this commit runs after a `cd` the guard can't follow, so it can't tell which "
                "repository the commit is in or check what it adds. Check it before approving."
            )
        return None
    try:
        git(cwd, "rev-parse", "--verify", "-q", "HEAD")
        has_head = True
    except GitError:
        has_head = False
    spec = parse_commit(args)
    # What the commit takes from the working files, as (cwd, paths, untracked files too, ignored
    # files too): what a `git add` earlier in the same command line stages, and the commit's own
    # -a, -i, --patch or paths.
    worktree, staged = list(added), True
    if has_head and (spec["all"] or spec["paths"] or spec["from_file"]):
        worktree.append((cwd, [] if spec["all"] or spec["from_file"] else spec["paths"], False, False))
        staged = spec["include"]
    try:
        findings = commit_findings(cwd, top, spec, staged, worktree, has_head)
    except (GitError, OSError, subprocess.TimeoutExpired):
        return "ask", (
            "sm-kit's guard couldn't read this commit through git, so it didn't check it. Check what it adds "
            "for secrets and personal data before approving."
        )
    if not findings:
        return None

    findings = list(dict.fromkeys(findings))
    findings.sort(key=lambda f: f[0] != "deny")
    listed = [text for _, text in findings[:MAX_FINDINGS]]
    if len(findings) > MAX_FINDINGS:
        listed.append(f"and {len(findings) - MAX_FINDINGS} more")
    body = "\n".join("- " + line for line in listed)
    if findings[0][0] == "deny":
        return deny(
            "this commit carries what must never be committed:\n" + body
            + "\nUnstage those files or remove those lines, then commit again."
        )
    return "ask", (
        "sm-kit's guard found what may be secrets, personal data or data files in this commit:\n" + body
        + "\nOnly the developer decides whether they're synthetic test data and fit to commit. If they "
        "are, the developer approves this commit, and can list the values in .claude/guard-allow.txt in "
        "a commit of its own. Otherwise take them out. Don't edit .claude/guard-allow.txt to get past this."
    )


def commit_findings(cwd, top, spec, staged, worktree, has_head):
    """("deny" | "ask", text) for each problem in what the commit adds."""
    findings, scanned, files, sources = [], 0, {}, []
    allow = load_allow(cwd)
    worktree = [entry for entry in worktree
                if entry[0] == cwd or git(entry[0], "rev-parse", "--show-toplevel").strip() == top]
    passes, reads = ([(cwd, ["--cached"], [])] if staged else []), []
    if worktree and has_head and repo_config_runs_commands(cwd):
        # git would run the repository's own filters to read the working files: read them here
        reads += [disk_changes(c, top, p) for c, p, _, _ in worktree]
    elif has_head:
        passes += [(c, ["HEAD"], p) for c, p, _, _ in worktree]
    reads += [new_files(c, top, p, tracked=not has_head, ignored=ignored)
              for c, p, untracked, ignored in worktree if untracked or ignored or not has_head]
    for c, revs, paths in passes:
        listed = changed_files(c, revs, paths)
        # A file git calls binary only because of attributes or config is read as text.
        texts = [p for p, binary in listed if binary and not DATA_FILE.search(p) and not holds_nul(top, revs, p)]
        for path, binary in listed:
            files[path] = files.get(path, False) or (binary and path not in texts)
        sources.append(added_lines(c, revs, paths))
        if texts:
            sources.append(added_lines(top, revs, [":(top,literal)" + p for p in texts], text=True))
    for path, binary, lines in itertools.chain.from_iterable(reads):
        files[path] = files.get(path, False) or binary
        sources.append(lines)
    local = [p for p in files if LOCAL_FILE.search(p)]
    if local:
        findings.append(("deny", f"{plural(len(local), 'file')} under .claude/local/, which never goes into a commit"))
    for path, binary in files.items():
        if LOCAL_FILE.search(path):
            continue
        if SECRET_FILE.search(path) and not SECRET_FILE_EXAMPLE.search(path):
            findings.append(("ask", f"{path} is a kind of file that usually holds secrets"))
        elif binary or DATA_FILE.search(path):
            findings.append(("ask", f"{path} is a binary, data or image file, which the guard can't check"))
        elif RECORD_FILE.search(path) and not path.lower().endswith(".md"):
            findings.append(("ask", f"{path} is in a change record but isn't Markdown: data and evidence "
                                    "belong in .claude/local/"))
        if path == ALLOW_FILE:
            findings.append(("ask", f"{path} changes the guard's allowlist: only the developer decides a value "
                                    "is synthetic"))
    for count, (path, lineno, text) in enumerate(itertools.chain.from_iterable(sources)):
        if count >= MAX_LINES or scanned > MAX_SCAN_CHARS:
            findings.append(("ask", "the commit is too large for the guard to check all of it"))
            break
        if count % 2000 == 0:
            time_left()
        scanned += len(text)
        scan(f"{path}:{lineno}", path, text, allow, findings)
    for message in spec["messages"]:
        for lineno, text in enumerate(message.splitlines(), 1):
            scan(f"the commit message, line {lineno}", "", text, allow, findings)
    return findings


# Git's own commands: an alias with one of these names is ignored, so they're never looked up.
GIT_BUILTINS = {
    "add", "am", "apply", "archive", "bisect", "blame", "branch", "bundle", "cat-file", "check-attr",
    "check-ignore", "checkout", "cherry-pick", "clean", "clone", "commit", "config", "describe", "diff",
    "diff-files", "diff-index", "diff-tree", "difftool", "fetch", "for-each-ref", "format-patch", "fsck", "gc",
    "grep", "hash-object", "help", "init", "log", "ls-files", "ls-remote", "ls-tree", "maintenance", "merge",
    "merge-base", "mergetool", "mv", "name-rev", "notes", "pull", "push", "range-diff", "read-tree", "rebase",
    "reflog", "remote", "reset", "restore", "rev-list", "rev-parse", "revert", "rm", "shortlog", "show",
    "show-ref", "sparse-checkout", "stage", "stash", "status", "submodule", "switch", "symbolic-ref", "tag",
    "update-index", "update-ref", "var", "version", "whatchanged", "worktree", "write-tree",
}
MAX_ALIAS_DEPTH = 5
UNKNOWN_ALIAS = object()  # an alias set from the environment, which the guard can't read
GIT_GLOBAL_VALUE_OPTIONS = ("--namespace", "--attr-source")
XARGS_VALUE_OPTIONS = {"-n", "--max-args", "-L", "--max-lines", "-I", "--replace", "-d", "--delimiter", "-E",
                       "--eof", "-s", "--max-chars", "-P", "--max-procs", "-a", "--arg-file", "--process-slot-var"}


class Line:
    """What the checks of one command line share: whether it points git elsewhere, and what
    each `git add` in it stages, for a commit later in the line."""

    def __init__(self, command, parent=None):
        self.redirected = bool(parent and parent.redirected) or bool(GIT_REDIRECT.search(command))
        self.added = parent.added if parent else []


def git_alias(cwd, name):
    try:
        return git(cwd, "config", "--get", "alias." + name).strip()
    except (GitError, OSError, subprocess.TimeoutExpired):
        return None


def ask_alias(sub, why):
    return "ask", (f"sm-kit's guard: `git {sub}` {why}, so the guard can't check what it runs. "
                   "Check it before approving.")


def check_git(argv, cwd, line, depth=0, aliases=None, uncertain=False, unknown=False):
    """unknown: some of the arguments come from elsewhere (xargs)."""
    aliases, redirected = dict(aliases or {}), line.redirected
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        arg = argv[i]
        if arg == "-C" and i + 1 < len(argv):
            cwd = expand(argv[i + 1], cwd)
            uncertain = uncertain or bool(UNRESOLVED.search(argv[i + 1]))
            i += 2
        elif arg in ("-c", "--config-env") and i + 1 < len(argv) or arg.startswith("--config-env="):
            setting = arg.split("=", 1)[1] if arg.startswith("--config-env=") else argv[i + 1]
            key, _, value = setting.partition("=")
            if key.lower().startswith("alias."):
                aliases[key[len("alias."):].lower()] = value if arg == "-c" else UNKNOWN_ALIAS
            i += 1 if arg.startswith("--config-env=") else 2
        elif arg in ("--git-dir", "--work-tree") and i + 1 < len(argv):
            redirected = True
            i += 2
        elif arg.startswith(("--git-dir=", "--work-tree=")):
            redirected = True
            i += 1
        elif arg in GIT_GLOBAL_VALUE_OPTIONS and i + 1 < len(argv):
            i += 2
        else:
            i += 1
    if i >= len(argv):
        return None
    sub, args = argv[i], argv[i + 1:]
    if sub == "clean":
        return check_clean(args)
    if sub in ("add", "stage"):
        targets = add_targets(args, unknown)
        if targets:
            line.added.append((cwd, *targets))
        return check_add(cwd, args, redirected)
    if sub == "stash":
        return check_stash(args)
    if sub == "commit":
        return ask_redirected("commit") if redirected else check_commit(cwd, args, line.added, uncertain)
    if sub in GIT_BUILTINS:
        return None
    if depth >= MAX_ALIAS_DEPTH or CLOCK["aliases"] >= MAX_ALIASES:
        return ask_alias(sub, "goes through more aliases than the guard follows")
    CLOCK["aliases"] += 1
    expansion = aliases[sub.lower()] if sub.lower() in aliases else git_alias(cwd, sub)
    if expansion is UNKNOWN_ALIAS or (not expansion and redirected):
        return ask_alias(sub, "may be an alias set from the environment")
    if not expansion:
        return None
    if expansion.startswith("!"):
        # A shell alias runs from the repository's top folder, after whatever this line staged.
        body = expansion[1:] + "".join(" " + shlex.quote(a) for a in args)
        return check(body, repo_root(cwd) or cwd, depth + 1, line)
    try:
        words = shlex.split(expansion)
    except ValueError:
        return None
    return check_git(["git", *words, *args], cwd, line, depth + 1, aliases, uncertain, unknown)


def xargs_command(argv):
    """The command an `xargs` runs, without xargs and its options."""
    i = 1
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] == "--":
            i += 1
            break
        i += 2 if argv[i] in XARGS_VALUE_OPTIONS else 1
    return argv[i:]


def check_simple(argv, cwd, line, depth=0, uncertain=False):
    name, unknown = os.path.basename(argv[0]), False
    if name == "xargs":
        argv, unknown = xargs_command(argv), True
        if not argv:
            return None
        name = os.path.basename(argv[0])
    if name.startswith("git-") and name[4:] in GIT_BUILTINS:
        argv, name = ["git", name[4:], *argv[1:]], "git"
    if name == "git":
        return check_git(argv, cwd, line, depth, uncertain=uncertain, unknown=unknown)
    if name == "rm":
        return check_rm(argv, cwd, uncertain, unknown)
    if name == "find":
        return check_find(argv, cwd, uncertain)
    return None


def check(command, cwd, depth=0, parent=None):
    """Return ("deny" | "ask", reason) for a command the guard stops, else None.

    A simple command the guard fails to check, or runs out of time on, asks:
    its failure never lets the rest of the line through.
    """
    if parent is None:
        start_clock()
    line, results = Line(command, parent), []
    try:
        commands = list(simple_commands(command, cwd))
    except Exception:  # the guard's own parsing failed: check the words as they stand
        commands = [(command.split(), cwd, True)]
    for argv, here, uncertain in commands:
        try:
            result = check_simple(argv, here, line, depth, uncertain)
        except OutOfTime:
            result = "ask", "sm-kit's guard ran out of time checking this command. Check it before approving."
        except Exception as exc:  # noqa: BLE001 - one command's failure mustn't pass the others
            result = "ask", (f"sm-kit's guard failed while checking `{os.path.basename(argv[0])}` "
                             f"({type(exc).__name__}). Check it before approving.")
        if result:
            results.append(result)
    if not results:
        return None
    denied = [reason for decision, reason in results if decision == "deny"]
    if denied:
        return "deny", "\n\n".join(denied)
    return "ask", "\n\n".join(reason for _, reason in results)


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("tool_name") != "Bash":
            return 0
        command = (data.get("tool_input") or {}).get("command") or ""
        verdict = check(command, data.get("cwd") or os.getcwd())
    except Exception as exc:  # never block work because of the guard's own bug
        print(f"sm-kit guard: skipped after an internal error: {exc!r}", file=sys.stderr)
        return 0
    if verdict:
        decision, reason = verdict
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
