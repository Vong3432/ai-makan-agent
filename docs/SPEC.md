# AI Makan Agent — Specification

A meal-recommendation agent exposed as a remote MCP server. Users connect from ChatGPT, Claude, or any MCP host and get personalised breakfast / lunch / tea / dinner / supper suggestions — filtered by allergies and dietary rules, ranked by learned preferences, tied to real places near a chosen location.

Status: design agreed (2026-11-27). Not yet implemented.

| # | Spec | Covers |
|---|---|---|
| 1 | [Goals](specs/01-goals.md) | Goals, non-goals |
| 2 | [Architecture](specs/02-architecture.md) | Stack, hosting, auth, agent style |
| 3 | [MCP Tools](specs/03-tools.md) | The 5 tools and their contracts |
| 4 | [Recommendation Pipeline](specs/04-recommendation-pipeline.md) | Filters, scoring, variety, fallback |
| 5 | [Preference Model](specs/05-preference-model.md) | Feedback → scored tags, decay |
| 6 | [Onboarding & Profile](specs/06-onboarding-and-profile.md) | First-run questions, habits, meal slots |
| 7 | [Data Model](specs/07-data-model.md) | Postgres schema draft |
| 8 | [Cost, Safety & Privacy](specs/08-cost-safety-privacy.md) | Cost controls, allergy safety, RLS |
| 9 | [Open Items](specs/09-open-items.md) | Caveats, undecided items |

See also: [Decision Log](DECISIONS.md).
