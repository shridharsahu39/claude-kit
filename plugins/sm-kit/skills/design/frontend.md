# Frontend design

Read when a design adds or changes screens, components, client state or API
calls in a web or Desk frontend. This file covers structure, behaviour,
security and speed; for the visual design itself (layout, type, colour,
motion, critique, polish) use the `impeccable` skill (`/impeccable shape`
before building a screen, `/impeccable audit` or `polish` after).

## Structure

- **Pages** compose; **components** render; **hooks or services** fetch and
  hold state; **API clients** are one module per backend subject. A component
  doesn't call `fetch` directly or hold a business rule.
- Reuse the design system and existing components first; extend a component
  with a prop only when its current users keep their look and behaviour.
- One source of truth per piece of state: server data in the data-fetching
  cache (React Query or the app's equivalent), form state in the form, URL
  state (filters, page, tab) in the URL. Don't copy server data into global
  state.
- No import cycles; shared types and helpers live below the components that
  use them.

## Behaviour

- The client never decides who may do what. Hiding a button is convenience;
  the server enforces it. The UI's offered actions come from the same check
  the server uses (an allowed-actions field), not a copy of the rule.
- Every list shows loading, empty, error and paginated states. A section with
  no data isn't shown, unless the spec says so.
- Forms validate for the user's sake and the server validates again; server
  errors map to the field they're about.
- Submits are disabled while in flight and carry an idempotency key where
  money or access changes, so a double click doesn't act twice.
- Money in rupees with Indian grouping, dates DD/MM/YYYY, from one formatting
  helper. Customer-facing text says only what the product knows.

## Security

- No raw HTML from data (`dangerouslySetInnerHTML`, `v-html`) unless
  sanitised; links only to `http(s)`.
- No secrets, tokens or personal data in the bundle, local storage, URLs or
  logs. Mask personal data the screen doesn't need in full.
- Third-party scripts only from the allow-list, with integrity where loaded
  from a CDN.

## Speed

- Each route's page is lazy-loaded; heavy libraries stay out of the main
  chunk.
- Fetch what the screen shows, paginated; no request per row; debounce search.
- Lists over a few hundred rows are virtualised or paginated.
- Measure first load and bundle size on the change when it's on a hot path
  (the `performance` skill).
