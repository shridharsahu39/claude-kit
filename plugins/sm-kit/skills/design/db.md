# Database design

Read when a design adds or changes tables, DocTypes, queries, jobs over data,
or migrations. Frappe notes are in *italics*.

## Integrity in the database, not only in code

- **Constraints:** a unique key for every business identifier (customer code,
  order reference, transaction reference); `NOT NULL` for what's mandatory;
  `CHECK` for ranges and states (no negative quantity, no status outside its
  list); foreign keys wherever the engine and framework allow. *Frappe: `unique`
  and `reqd` on the field, `Link` fields, and a unique index in a patch for a
  combination of fields.*
- **Types:** decimal for money and quantities with a fixed scale, never float
  (*Frappe stores `Currency` and `Float` as decimal but Python reads them as
  float: use `Currency` for money, round with `flt(value, precision)`, and
  never compare money with `==` on raw values*);
  dates as dates, not strings; identifiers as the framework's key type.
- **Normalise.** One fact in one place. Denormalise only for a measured read
  cost, and write down what keeps the copy true (same transaction, trigger, or
  a rebuild job with a check).
- **Derived values** (totals, balances, counts): compute them when read, or
  store them with the mechanism that keeps them true named in the design.
- **Ledgers are append-only.** Money and stock movements are new rows,
  corrected by reversing rows, never edited or deleted. The balance is the sum
  or a checked snapshot of it. *Frappe: submitted documents, cancel and amend.*
- **Soft delete:** decide how a deleted row affects unique keys (does a new
  row with the same code clash?), links, reports and exports, and say so.
- **No orphans:** deleting or cancelling a parent says what happens to each
  child: refused, cascaded, or kept with a reason.

## Queries

- Fetch in bulk: one query for the set, then a map, never a query per row.
- Select the columns needed, never `*` or a full document for one field.
- Every list is paginated (cursor or keyset for large, changing sets; offset
  only for small ones); every query has a bound.
- Aggregate in the database (`SUM`, `COUNT`, `GROUP BY`), not in a loop.
- Indexes follow the queries: a composite index in the order of
  equality filters, then the range or sort column. Check the plan (`EXPLAIN`)
  on production-like volume for any new query on a large table.
- Bound parameters only. Column, table and sort names come from an allow-list.
- Scope (tenant, branch, customer) is in the `WHERE` of every query, join,
  subquery and aggregate, including reports, exports and jobs.

## Concurrency

- What must succeed or fail together runs in one transaction, kept short.
- Read-modify-write on a balance, stock, fee or counter uses an atomic update
  (`SET qty = qty - 1 WHERE qty >= 1`, check the rows changed) or a row lock
  (`SELECT … FOR UPDATE`; *`frappe.get_doc(…, for_update=True)` or
  `frappe.db.get_value(…, for_update=True)`*). Two people issuing the last
  item can't both succeed.
- Concurrent edits of one record use a version check (optimistic locking;
  *Frappe's `modified` check on save*).
- No external call (partner API, email, payment gateway) while a transaction
  or lock is open: commit, then call, then record the result.
- A request that may arrive twice (retry, double click, webhook redelivery)
  carries an idempotency key, or a unique key makes the second insert fail
  harmlessly.
- Deadlocks: take locks in a fixed order; retry the whole transaction a
  bounded number of times.
- Isolation: say it when a workflow needs more than the default.

## Migrations

- Backward compatible with the code still running during a deploy: add, then
  backfill, then switch reads, then drop in a later release.
- A large backfill runs in batches, in a job, not in the migration's one
  transaction. No table-rewriting change on a big table at peak hours.
- Reversible where practical; tested on a copy of the production engine.

## Scale and operations

- Know the table's shape: high-write tables get few indexes; high-read ones
  get the indexes their queries need.
- Heavy work (exports, reports, bulk messages, imports) runs in a background
  job, never in the request.
- Cache only stable reads, with a TTL and an invalidation rule; the key
  carries user, role and tenant or branch.
- Read replicas only where stale reads are acceptable; say which.
- Archive or partition only when volume and query patterns show the need.
- The app uses its own least-privilege database account; migrations may need
  more, runtime doesn't get it.
