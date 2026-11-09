---
name: qa
description: How every change is tested end to end — cases first, automated tests that fail without the change, a full audit by the qa-auditor agent for anything a person or a job does, fix and rerun, and the report — with the safety rules for any test run. Use when planning a change's tests, while running them, and before handing over. A repository's own qa skill, where it has one, adds how its stack runs.
---

# QA for every change

Every change is tested the way a QA tester would test it: written test cases,
an end-to-end run and recorded outcomes. Documentation-only changes are exempt.

How to run and sign in to a repository's stack is that repository's business.
`mutual_fund`, the relay and the frontend each have their own `qa` skill
(`.claude/skills/qa/SKILL.md`); read it for every repository a change
touches. A Frappe app without one follows [Frappe apps](#frappe-apps) below.
A repository that isn't a Frappe app (ClassManager, for example; see
[the team's repositories](../change/repositories.md)) always has its own `qa`
skill. That skill replaces everything here about benches, sites, Desk and the
QA site. The method in [How a change is tested](#how-a-change-is-tested) and
the safety rules still apply. Where the stack has a database other than the one
its tests use (SQLite in tests, MySQL or MariaDB in production), run the suite
and the migrations on a disposable local copy of the production engine too.

## How a change is tested

1. **Cases first.** While planning, write the test cases in the record's
   `qa.md`. Each has an ID (`QA-1`, `QA-2`, …), what it covers, the
   preconditions and data, the steps and the expected result. Cover the journey,
   every new rule or branch (refusals, errors, empty states), each persona,
   entry point and client build it touches, and nearby behaviour as regression
   cases.
2. **Automated tests.** Add or extend the tests for the cases in each
   repository, and show that each fails without the change.
3. **A full QA audit by the `qa-auditor` agent** whenever the change touches
   something a person or a job does: a React screen, a Desk screen, an API a
   screen calls, a scheduled job. Brief it with the record, each repository and
   branch, and any write the owner approved in this session's chat. It adds the
   cases you missed, runs every case end to end in the browser on the QA site,
   records the run in `qa.md` and reports back. Unit tests alone never pass a
   case.
4. **A performance check by the `performance-auditor` agent** when the change
   is on a hot path: an API a screen calls, a list or report query, a scheduled
   job or import, a schema change on a large table, or a screen's first load.
   It measures the base branch and the change on a production-like server on
   the QA site and records the result in `qa.md`; the `performance` skill says
   how.
5. **Fix and rerun.** For each Fail or slowdown, fix it, then have the auditor
   rerun the failed cases and their neighbours.
6. **Report the run** in the final summary: cases passed, failed, blocked and
   not run, the performance results, and what the runs left on the QA site.

**Depth, tiered:** every scenario of each affected journey; a quick pass over
the neighbouring journeys; every journey the repository's `qa` skill lists (or,
where it lists none, every journey of the product) when the change touches
shared code: the store, routing, the session, shared components or services.

**The QA site** is a local site kept for QA, not the developer's working site.
`~/.claude/CLAUDE.md` names it, with the file that lists its personas
(`~/.claude/qa-sites/<site>.md`, outside every repository). With none, QA runs
on the working site and removes everything it created. The `setup-machine`
skill says how to make one, with the partners' secrets removed, and which
partner settings that can't reach, so the rules below hold on the QA site too.

## Safety while testing

- **Site:** test on a local site. Confirm the site before any state-changing
  command, and ask before any migration.
- **Nothing changes outside the machine:** no OTP, email, SMS, payment, order,
  policy or other partner write. Stop on the screen before the action that would
  send, and record that step as Not run.
- **Partner reads** only when a case needs one, and only against a partner's
  test environment you've confirmed first, from the endpoint the site is
  configured with: never production. Record each. A performance run makes no
  partner calls at all. The relay calls some partners itself, with its own
  settings, whatever the site holds (the CVL KRA check, for one): a step through
  it is a partner call too.
- **Partner writes:** only the owner, in the session's chat, can approve a
  write to a partner's test system such as BSE UAT. The main session asks once
  per run, and its brief to the `qa-auditor` quotes the owner's words and lists
  each write they cover.
- **Web server only:** don't start the scheduler or workers. Check the Email
  Queue and SMS Log before and after the run.
- **Synthetic data:** use obviously fake values (`QA` names; PANs, mobiles and
  emails in fake patterns such as `ABCPE1234F`, `9999999999` and
  `qa+1@example.com`), and list every record the run creates. Remove them
  afterwards, leaving the site as it was.
- **URLs:** never put a token, a session id or personal data in a URL you
  build. Sign in through the product's own login, the SSO hand-off the product
  already uses, or a session handed over as a cookie (see
  [Frappe apps](#frappe-apps)), and never record a hand-off URL.
- **Clean up:** stop the servers you started and remove temporary files.

## Frappe apps

- Run the app's tests from the bench root:
  `bench --site <site> run-tests --app <app>`. The app's `CLAUDE.md` says which
  tests exist and what CI runs.
- Desk and RM users sign in without a password. In developer mode, a
  `bench execute` script makes their session as `bench browse --user` does:
  `frappe.utils.set_request(path="/")`, a `CookieManager`, then
  `LoginManager().login_as(user)`. The script writes the session id to a
  mode-600 file and returns nothing, since `bench execute` prints what it
  returns. Hand the id to the browser as a cookie, never in a URL: a one-shot
  local server on the site's host name, on a port of its own, answers one
  request with `Set-Cookie: sid=…; Path=/; HttpOnly` and a redirect to the
  site, then exits. A cookie belongs to the host name, whatever the port. End
  the session when the run ends: Desk's Log out, or
  `frappe.sessions.delete_session(sid)` from a script. `/api/method/logout`
  takes POST only, so opening it in the browser leaves the session alive.
- Customers sign in through the product's real login, with the developer-mode
  OTP code where the login sends one.
- When a change reaches the frontend, the frontend's journey specs are its
  end-to-end suite: each frontend change adds or extends the spec of each page
  in its journey. The frontend's `qa` skill says how to run them.

## Records

- The QA record is the change's `qa.md`, from the `change` skill's template. Its
  Security check section records the review that `.claude/rules/security.md`
  requires.
- Keep identifiers, credentials and raw data out of QA records, as for change
  records.
