# Security check for every change

Every change gets a security check before it's handed over, alongside its QA.
That covers code, DocType JSON, patches, scripts, CI and configuration. A
documentation-only change is checked only for secrets and personal data in its
text.

## While building

Build against this list rather than reviewing at the end.

1. **Who may call it.** Every whitelisted method chooses its callers on purpose.
   - `allow_guest=True` and `ignore_permissions=True` need a reason in a code
     comment and never act on caller-chosen records. Never take a DocType or
     field name from the caller.
   - A method that takes a record's id checks that the record belongs to the
     caller (the customer, RM or partner) before reading or changing it (IDOR).
     So does every other record the request names, such as a row's link. A
     refused record answers "not found", so ids can't be probed.
   - New Desk roles and permissions are the least the job needs.
2. **What it trusts.** Validate on the server: amounts, premiums, rates, dates,
   choices, ownership and state changes. Never take a price, a premium or a
   status from the client. A repeated submit must not double an order, a policy
   or a payment.
3. **Injection.** Parameterise SQL (`frappe.qb`, or `%s` values). Never put
   input into SQL text, shell commands, file paths, `eval`, `safe_eval` or a
   template. Treat uploaded and partner files as hostile: check size, type and
   name, and parse spreadsheets, zips and XML defensively.
4. **What it shows.** An answer carries only the fields its screen needs. Errors
   carry no stack traces or another customer's data. Escape customer text in
   Desk JS, print formats and Jinja.
5. **Secrets.** No credentials, keys, tokens or OTP bypass codes in code, tests,
   fixtures, change records or commits. Settings come from site config or a
   Password field. Developer shortcuts stay behind developer mode.
6. **Sessions and links.** Tokens and personal data never go in a URL, beyond
   the existing SSO hand-offs. Keep the relay's and the SSO's checks intact.
7. **Files.** Customer documents and partner files are private files.
8. **Dependencies.** A new package is needed, maintained and pinned.
9. **Logs.** No credentials, customer identifiers or raw partner payloads in
   app logs, except where an exception below says otherwise.

## In this app

{app_section}

## Before handover

1. Run the `security-reviewer` agent on the change's diff, in every repo the
   change touches. It reviews on its own and doesn't edit.
2. Fix each finding, or record why not. A high finding blocks handover until
   it's fixed or the change's owner accepts it in chat. High means: an
   authorization bypass, one customer reaching another's data, injection, or a
   leaked secret.
3. Add a security case to the QA record for each new entry point or rule: for
   example, another customer's id is refused, a missing role is refused, bad
   input is refused.
4. Record the check in the change's `qa.md`, under "Security check": what was
   reviewed, each finding and its outcome.
5. Before any commit, read the staged diff for secrets and personal data: PAN,
   mobile, email, bank account, policy, folio and customer numbers, tokens.
