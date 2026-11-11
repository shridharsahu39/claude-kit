# Design: <change name>

**Task class:** <from the change skill's routing table>  
**Review:** <design-reviewer verdict and date> · **Owner's yes:** <D-n>

## Reuse map

| Need | Existing (file:line) | Reuse / extend / new | Why; callers kept |
| --- | --- | --- | --- |
| <AC-1: list a customer's orders> | `<path>:<line>` | Extend | <parameter added; callers A, B unchanged> |

## Modules

| Module (path) | Layer | Its one job | Depends on |
| --- | --- | --- | --- |

## Data

<Tables or DocTypes, fields with types, constraints (unique, not null, check,
foreign key), indexes for the new filters, migration and backfill, and whether
old code still runs against the new schema.>

## Concurrency and jobs

<What succeeds or fails together; locks or atomic updates; idempotency key;
what runs in a background job, its retries and what makes a rerun harmless.>

## Contract

<Each layer's part: method or route, who may call it, request, response,
errors. Pagination for lists.>

## Outside callers touched

<Cron, webhook, callback, public method or partner route, and who calls it.
"None".>

## Security of the design

<Per entry point: the caller's check, how records are scoped, the fields the
caller may set and see, input validation.>
