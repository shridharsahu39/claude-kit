
# Frappe practices

**Scope:** Frappe rules that every app in the bench shares. This app's own
runtime, security boundaries, data model and contracts are in the other rules.

## Repository and site boundaries

- Each app under `apps/` has its own Git history. Check the bench and every
affected app repository; preserve pre-existing changes.
- Run bench commands from the bench root. Confirm the site before a
migration or any other state-changing command. The local site's name is in the bench's
`CLAUDE.md`; verify it exists before use.
- For schema changes, batch edits and normally run one migration after the
implementation is ready. Do not migrate for documentation-only work.
- An agent may start the bench when it isn't running: in the background, since
`bench start` never exits, the way `~/.claude/CLAUDE.md` says.

## Application boundaries

- Keep business behavior in services and expose purpose-specific endpoints.
Enforce authorization at the API boundary; do not add generic client-selected
DocType access or caller-controlled permission bypasses.
- Parameterize SQL values. Prefer the owning app's established query patterns
for new work and check the configured lint/runtime rules before changing code.
- Use savepoints for atomic multi-document operations. Check DocType JSON for
child-table status before creating fixtures; append child rows through the ORM.
- Preserve lifecycle hooks when behavior depends on them. Use explicit
permission handling in trusted background jobs.
- Desk access reaches linked DocTypes. A role that fills a form needs select or
read on every DocType its Link fields point to: Frappe checks links with the
select permission and drops values it can't check. A report's roles need report
permission on its reference DocType, or Frappe won't open it.
- Keep logs and records free of credentials, customer identifiers, bank data,
and raw external payloads. Exceptions the owner accepted
are in [security](security.md).

## Validation

Run focused tests or lint checks from the app repository using its configuration.
For database behavior, use an appropriate site-backed check. Report checks that
actually ran and material gaps; do not treat old results in an archive as current.
