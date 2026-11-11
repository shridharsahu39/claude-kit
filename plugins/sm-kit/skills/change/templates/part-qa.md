# QA: <change>, <repository>'s part

The end-to-end cases and the `qa-auditor` agent's runs are in the record's
`qa.md`. This file holds this repository's own checks.

## Automated tests

| Case | Spec or test | Fails without the change |
| --- | --- | --- |
| QA-1 | `<file>`: "<test name>" | yes |

**Suites run:** each suite, its test count and the date.

## Code quality

| ID | Finding | Safe to apply | Outcome |
| --- | --- | --- | --- |
| CQ-1 | What and where | Yes, owner or no | Applied in `<commit>`, approved on <date>, or a follow-up |

## Security check

- **Reviewed:** this repository's diff and its base, and when the
  `security-reviewer` agent ran.

| ID | Severity | Finding | Outcome |
| --- | --- | --- | --- |
| SEC-1 | High, Medium or Low | What could happen, and where | Fixed in `<commit>`, or accepted by the owner on <date> |
