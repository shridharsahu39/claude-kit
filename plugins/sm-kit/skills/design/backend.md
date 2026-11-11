# Backend design

Read when a design adds or changes an API, a service, a job or an
integration. Frappe notes are in *italics*.

## Layers

- **Route or controller:** authenticate, validate the request against a
  schema, authorise, call one service function, shape the response. No
  business rule here. *A whitelisted method is a route.*
- **Service:** the business rules, one module per subject, callable from a
  route, a job and a test alike. Reuse or extend before adding.
- **Data access:** queries in one place per subject, reused, scoped.
- Dependencies point down only (route → service → data). Shared helpers live
  below everything that uses them. No import cycles.

## APIs

- Every protected route checks the caller; deny by default.
- Authorise at four levels: the function (role), the object (this record is
  the caller's, no IDOR), the property (fields the caller may set and see:
  copy fields by name, never the whole body), and the scope (tenant, branch).
- Never trust an identity, role, branch or price sent by the client; take it
  from the session or the server's records.
- Validate input centrally against an explicit schema: types, lengths,
  ranges, allowed values.
- One response shape and stable error codes; no stack traces or internal ids
  the caller has no use for.
- Lists are paginated with a maximum page size; uploads and bodies have size
  limits; expensive actions have per-user rate limits.
- Stateless where possible; anything kept between requests is in the
  database or a cache with a scoped key.

## Jobs and integrations

- Long or heavy work (exports, reports, bulk messages, imports, partner
  sync) goes to a queue. *`frappe.enqueue` with a timeout and a queue.*
- Every job is idempotent: a rerun or a duplicate delivery changes nothing
  twice. Retries are bounded, with exponential backoff; a job that gives up
  is visible (failed-jobs list, alert).
- External calls have a timeout, bounded retries for safe operations only,
  and a circuit breaker or back-off when the partner is down. Never inside a
  database transaction.
- A partner's response is validated before use and never trusted as an
  authority on who the caller is.
- Webhooks and callbacks verify a signature and a timestamp, refuse
  replays, and are idempotent. They're outside callers: never removed or
  renamed without the owner.
- Jobs, exports and bulk actions apply the same authorisation and scope as
  the API, for the user they act for.

## Operations

- Structured logs with a request or correlation id; no secrets or personal
  data in logs.
- Configuration from the environment, validated at start-up; secrets never
  in code or the browser.
- Health and readiness checks; graceful shutdown that finishes or returns
  in-flight work.
- Metrics for latency, throughput, errors, saturation and queue depth, with
  targets set from the real workload, not universal numbers.
