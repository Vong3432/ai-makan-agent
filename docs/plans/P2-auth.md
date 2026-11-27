# P2 — OAuth 2.1 via Supabase Auth

**Goal:** MCP hosts (ChatGPT, Claude) can connect, sign in with Google, and every tool call carries an authenticated `user_id`.
**Specs:** [Architecture](../specs/02-architecture.md), [Open Items](../specs/09-open-items.md)

## Tasks

- [ ] **P2-T1** Verify current Supabase OAuth 2.1 server docs + FastMCP Supabase provider docs (APIs are new; confirm before coding).
- [ ] **P2-T2** Supabase dashboard: enable Google sign-in provider (Google Cloud OAuth client).
- [ ] **P2-T3** Supabase dashboard: enable OAuth Server + **Dynamic Client Registration**.
- [ ] **P2-T4** Build the authorization/consent page Supabase's OAuth server redirects to (shows which client is requesting access; approve/deny).
- [ ] **P2-T5** Wire FastMCP's Supabase auth provider in `auth.py` when `AUTH_MODE=supabase`; expose protected-resource metadata.
- [ ] **P2-T6** Helper `current_user()` returning `user_id` + access token for tools (works in both auth modes).
- [ ] **P2-T7** Validate redirect URIs / log registered clients (safety item from spec).
- [ ] **P2-T8** Manual test: connect via MCP Inspector with OAuth; full sign-in flow completes and `ping` returns the user id.

## Done when

- OAuth flow works end-to-end from MCP Inspector against a deployed or tunnelled server.
- Unauthenticated calls are rejected.

## Risks

- Supabase DCR rejecting custom redirect schemes (`cursor://`) — affects native clients only.
