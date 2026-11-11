# QA: <change>

Test cases, the `qa-auditor` agent's runs and the security check for this change, as the `qa` skill describes. For a change across repositories, each part's `qa.md` holds that repository's own tests and security check.

- **Under test:** each repository with its branch and commit, plus any uncommitted work on top.
- **Stack:** the QA site, the relay, the frontend and the browser. The personas: the actor and the kind of account, without identifiers.
- **Test data:** every synthetic record the run creates, and whether it stays on the QA site for reuse or is removed.

## Test cases

| ID | Covers | Preconditions and data | Steps | Expected |
| --- | --- | --- | --- | --- |
| QA-1 | | | | |

## Automated tests

| Case | Repository | Spec or test | Fails without the change |
| --- | --- | --- | --- |
| QA-1 | `<repo>` | `<file>`: "<test name>" | yes |

**Suites run:** each suite with its test count.

## Runs

### <yyyy-mm-dd>, run 1 by the `qa-auditor`: <what was under test>

| ID | Result | Observed |
| --- | --- | --- |
| QA-1 | Pass, Fail, Blocked or Not run | What actually happened. For a Fail, the bug and its fix |

- **Not run or blocked:** each case, and why.
- **Cleanup:**
  - the records removed;
  - the servers stopped;
  - the Email Queue and SMS Log counts, before and after.

## Performance check

Only for a change on a hot path (sm-kit's `performance` skill); otherwise write
"Not needed: <why>".

- **Under test:** each repository's branch and commit, and its base; the site,
  the server and its workers, the data volume, and the machine.
- **Targets:** each target, and where it came from (the spec, the owner, or the
  skill's defaults).

| ID | What | Base | Change | Target | Result |
| --- | --- | --- | --- | --- | --- |
| PERF-1 | `<method or screen>`, p95 at <n> concurrent | <ms> (spread) | <ms> (spread) | <ms> | Met or Missed |

| ID | Finding | Evidence | Outcome |
| --- | --- | --- | --- |
| PF-1 | What's slow, and why (file and line) | Queries per request, EXPLAIN, profile | Fixed in `<commit>`, or accepted by the owner on <date> |

- **Left on the site:** the volume rows kept or removed, and the servers stopped.

## Security check

- **Reviewed:** each repository's diff and its base, and when the `security-reviewer` agent ran.
- **Security cases:** the QA cases that test a refusal (another account's id, a missing role, bad input), including the IDOR sweep: each id-taking route tried with another customer's or company's ids, in the path and inside the body.

| ID | Severity | Finding | Outcome |
| --- | --- | --- | --- |
| SEC-1 | High, Medium or Low | What could happen, and where | Fixed in `<commit>`, or accepted by the owner on <date> |
