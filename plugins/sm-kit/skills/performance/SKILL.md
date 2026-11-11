---
name: performance
description: How to check a change or journey for performance and scale — hot paths, targets, a production-like local QA server, per-stack tools, a local-only load generator, safety rules. Use when planning or running a performance check or scale audit.
---

# Performance and scale

Two kinds of run, both by the `performance-auditor` agent:

- **A change's performance check**, for a change on a hot path, in the
  checks the owner asks for (`/sm-kit:checks`). It measures
  the base branch and the change on the same server and data, and flags what
  got slower.
- **A scale audit** of an app or a journey: before a bank rollout, a campaign
  or a launch, or when something is slow. It finds the bottleneck and how far
  the current design goes.

**A hot path** is anything that runs often or over a lot of data: an API a
screen calls, a list or report query, a scheduled or background job, an
import, a schema change on a large table, or a screen's first load. Brief the
auditor with the record, each repository and branch, the targets and the
expected load.

A repository that isn't a Frappe app takes its server, data and sign-in from
its own `qa` skill. There, the Frappe tools below give way to the stack's own
tools: the ASGI or WSGI server's access log for timings, the ORM's SQL echo
for query counts, and `EXPLAIN` on the production engine. The load generator
and the safety rules still apply.

## Targets

The change's spec gives the targets; for a scale audit the owner gives the
expected load: users, peak concurrency, data volumes, and the peak moments
(month-end, an NFO's last day, a payment cut-off, a campaign). Without them,
use these defaults and say so in the record:

| What | Default target |
| --- | --- |
| An API a screen calls | p95 under 500 ms at the expected concurrency, no errors |
| Queries per request | The same as rows grow: no query per row |
| A list or report | Paginated, and under 1 s at 10 times today's rows |
| A scheduled or background job | Done well inside its interval at 10 times today's volume |
| A screen's first load | LCP 2.5 s or less, INP 200 ms or less, CLS 0.1 or less (Core Web Vitals' "good"), on a throttled mid-range phone profile |
| The frontend bundle | No growth without a reason |

## Where to measure

- **The QA site** that `~/.claude/CLAUDE.md` names, never the developer's
  working site, a shared site, production, UAT, or a partner's system. Load on
  a system you don't own is an attack, whoever runs it.
- **A production-like server**, on a port of your own:
  from the bench's `sites/` folder, run Frappe under gunicorn as bench's
  production set-up does (its supervisor template):
  `../env/bin/gunicorn -b 127.0.0.1:<port> -w <workers> -t 120 --preload frappe.app:application`.
  Production uses 2 × cores + 1 workers; on a laptop use 4 to 8, and record how
  many. The Host header picks the site: call `http://<qa-site>:<port>/…`. Jobs
  a run enqueues go to the bench's shared queues, where the developer's worker
  runs them: count them, and handle them as the repository's `qa` skill says.
  `bench serve` is one process: fine for a profile, wrong for a load test.
  The developer's running dev stack is theirs: never load it.
- **Partners stay out.** A request that would call BSE, a registrar, KRA, a
  bank, an insurer or a payment gateway is stopped or stubbed for the run (the
  repository's `qa` skill says how its stack does it), and never put under load.
- **Data volume:** today's volume, and a larger one (10 times, or what the
  owner expects). Synthetic rows carry a `QA` prefix and are listed, then
  removed, unless the owner keeps them as the QA site's volume set. A shared
  local site holding real volumes (such as a rehearsal site) can be measured
  read-only, only with the owner's go-ahead in the session's chat.
- **This machine isn't production.** Results compare a change with its base and
  find bottlenecks; they aren't production capacity. When scaling them up, say
  how (by workers, by cores) and how sure you are.

## Tools

### Frappe

These are Frappe 16's own tools; nothing to install.

- **Queries per request or job, with the Recorder:** run
  `bench --site <qa-site> start-recording`, run the journey or the job, then
  `stop-recording`, and read the result in Desk at `/app/recorder`. It records
  each request and background job with its SQL, each query's time, its EXPLAIN
  and the call stack, and suggests indexes. It switches itself off after 10
  minutes. Started from code, `frappe.recorder.start(profile=True)` also
  profiles each request.
- **A method's profile:** `bench --site <qa-site> execute <dotted.method> --profile`
  prints a cProfile summary. It commits afterwards, so profile a method that
  writes only on the QA site, and clean up. `bench serve --profile` profiles
  every request on that one-process server.
- **One query:** `frappe.db.sql(query, values, explain=True)` logs its EXPLAIN,
  and `frappe.get_all(..., run=False)` gives the query a list would run.
  `bench --site <qa-site> describe-database-table --doctype <DocType>` shows a
  table's size and indexes.
- **Every request's time over a run:** set `monitor: 1` in the QA site's config
  and Frappe logs each request and job with its duration to the bench's
  `logs/monitor.json.log`. The scheduler's `frappe.monitor.flush` writes the log
  out, so with the QA site's scheduler off, run `frappe.monitor.flush` yourself
  after the run. Remove the setting afterwards.
- **Jobs:** time a job's method directly, or from the Recorder's job records;
  Scheduled Job Log keeps no durations. `bench --site <qa-site> show-pending-jobs`
  shows the queues. Never run `bench purge-jobs`: the queues are shared with the
  developer's stack.

Usual causes, in order of how often they bite: a query per row
(`frappe.get_doc` or `frappe.db.get_value` in a loop; use one `get_all` with
the fields, or `frappe.qb`); `get_all` without a limit; whole documents loaded
to read a field; filters or sorts on unindexed columns (add `search_index`, or
an index in a patch); a commit per row in bulk work; a partner call inside a
request (enqueue it); a hot read never cached (`frappe.cache`, with an
invalidation); a response far larger than its screen needs.

### The relay

- Latency per GET route with `load.py`, sending the headers the frontend sends,
  as the relay's `qa` skill says: a fresh `x-timestamp` on every request
  (`--fresh-ms-header x-timestamp`) and the CSRF token, in the header file.
- An encrypted POST can't be replayed: the relay derives each request's key
  from the CSRF token and that request's `x-timestamp`
  (`apps/mutual-fund/src/middlewares/reqResIntercepter.middleware.ts`), so a
  body encrypted once fails on the next request, and a fixed timestamp trips
  the replay check. Measure the Frappe method behind the route instead, or
  write a small Node client that encrypts each request with the relay's own
  `crypto-js`, as the app does.
- Never turn off, bypass or patch the relay's CSRF check, payload encryption,
  replay check or token revocation, not even on a side relay: if neither way
  above works, record the route as Not measured.
- CPU: run the relay under `node --cpu-prof`, put it under load, and read the
  `.cpuprofile` in Chrome's DevTools.
- Watch its Redis database's size and the session count during a run.

### The frontend

- A screen's first load, in the browser: read
  `performance.getEntriesByType("navigation")`, and LCP and CLS with a
  `PerformanceObserver`, under CPU and network throttling. Use the client build
  the bank ships.
- The network: count the requests a screen makes and their sizes, and look for
  repeats and waterfalls.
- The bundle: build the bank's configuration on the base branch and on the
  change, and compare the chunk sizes the build prints.

### Load: `load.py`

`${CLAUDE_SKILL_DIR}/load.py` is a dependency-free load generator. It runs a
ladder of concurrency levels on keep-alive connections and prints throughput,
p50, p95, p99, max and errors for each:

```bash
python3 "${CLAUDE_SKILL_DIR}/load.py" http://qa.localhost:8012/api/method/<method> --header-file <mode-600 file with the Cookie> --concurrency 1,5,10,25,50 --requests 300
```

It loads only this machine, over plain HTTP: `localhost`, `*.localhost` (always
sent to `127.0.0.1`) or a loopback address, with no override. A target anywhere
else needs the owner's go-ahead in chat, and another tool. The URL picks the
site: a `Host` header, or an `X-Frappe-Site-Name` naming another site, is
refused. A `*.localhost` site takes load only when `setup-machine` has marked
it this machine's QA site (`~/.claude/qa-sites/<site>.qa-site`), and only once
the server answers a first request as one of the personas listed in
`~/.claude/qa-sites/<site>.md`. A server started for a single site (the dev
stack's `bench serve`, or `--site`) serves it whatever the Host header says,
and only the QA site knows a QA persona's session, so that answer shows which
site the port serves. So the run needs a QA persona's session in
`--header-file`. A `localhost` or loopback target, such as a side relay, gets
no such check: point it only at a server the run started, never at the dev
stack's ports. Secrets (a session cookie, a token, the CSRF token) go only in
`--header-file`, or in a body file (`--data @FILE`); a secret-looking query
parameter or body field given inline is refused, nested JSON included. Keep
those files in the session's scratch folder at mode 600, never in
`.claude/local/`, delete them when the run ends, and end the session (the `qa`
skill says how). Raise the concurrency until p95
passes the target or errors appear: that knee is this set-up's limit. Install
another tool (k6, locust) only with the owner's go-ahead.

## Safety

- Nothing leaves the machine: no partner call, OTP, SMS, email or payment.
- Don't change MariaDB or Redis server settings, `common_site_config.json`, or a
  site other than the QA site, without asking; restore what you change on the
  QA site.
- Stop every server you started, empty only a Redis database you created for
  the run (never the bench's, or the developer's relay database, which holds
  sessions and revoked tokens), and remove temporary files. Never print a
  session id, token or password.

## Record

The change's `qa.md` has a "Performance check" section, from the `change`
skill's template:

- what was under test, the site, the server and its workers, the data volume,
  and the machine;
- the targets, and where they came from;
- each measurement before and after, with its spread;
- each finding: what, how big, why (file and line), and the fix;
- what the run left on the site.

No identifiers or literal values in the record: counts, timings and each
query's shape, never a row, a parameter's value or a customer's data. Raw
Recorder, EXPLAIN and profile output stays in
`.claude/local/changes/<record>/perf/`. A later run of the same journey reuses
the last baseline.
