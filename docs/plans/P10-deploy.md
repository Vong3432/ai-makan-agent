# P10 — Cloud Run deploy & host connection

**Goal:** live HTTPS MCP endpoint usable from ChatGPT and Claude.
**Specs:** [Architecture](../specs/02-architecture.md)

## Tasks

- [ ] **P10-T1** Build the `prod` target of the P0 Dockerfile; confirm it honours `PORT` from env.
- [ ] **P10-T2** GCP project, Artifact Registry, Cloud Run service (min instances 0).
- [ ] **P10-T3** Secrets in Secret Manager (Supabase keys, Google API key, LLM key) mounted as env vars.
- [ ] **P10-T4** Restrict Google API key to Places/Geocoding APIs; set a billing budget alert.
- [ ] **P10-T5** Update Supabase OAuth redirect/allowed URLs with the Cloud Run URL.
- [ ] **P10-T6** Deploy script / GitHub Actions workflow (`gcloud run deploy`).
- [ ] **P10-T7** Connect from Claude (custom connector) and ChatGPT (connector / developer mode); run the full loop: onboard → recommend → feedback → recommend.
- [ ] **P10-T8** Structured logging + basic error reporting (Cloud Logging).
- [ ] **P10-T9** Pre-public checklist: enable rate limit, review DCR registered clients, privacy note.

## Done when

- Full loop works from at least two hosts against the deployed URL.
