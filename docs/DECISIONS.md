# Decision Log

Decisions reached during design grilling on 2026-11-27.

| # | Decision | Alternatives considered | Rationale |
|---|---|---|---|
| 1 | Fat agent: server runs its own LLM + ranking | Thin MCP server (host LLM reasons); hybrid | Consistent behaviour regardless of which host/model the user connects from |
| 2 | Multi-user ("everyone") from day one | Personal-only | Product intent is for anyone to connect |
| 3 | Recommend dish + real place via Google Places, minimal cost | Dish only; curated personal list; OSM; Foursquare | Best coverage; cost controlled via field masks + shared cache |
| 4 | Location is required, passed by host LLM as short free text | Saved named locations; lat/lng | Hosts rarely have coordinates; free text is natural in chat |
| 5 | Allergies are hard exclusions + vendor-confirm disclaimer; other prefs soft | Allergies as soft preferences | Public tool — soft allergy handling is a safety/liability risk |
| 6 | Feedback via explicit tool, free text | Transcript analysis; daily check-in | MCP servers can't see the chat; explicit tool is reliable |
| 7 | Host on Google Cloud Run | Cloudflare Workers; Fly; VPS | User preference; scales to zero |
| 8 | Operator pays for a cheap LLM | BYO key; freemium | Simplest UX; model is swappable |
| 9 | Tools: `recommend_meal`, `give_feedback`, `update_profile`, `get_profile`, `delete_my_data` | Many fine-grained structured tools | Free-text tools work across all hosts |
| 10 | Database: Supabase Postgres | Firestore; Cloud SQL | User preference; free tier, SQL, RLS |
| 11 | Auth: Supabase Auth as OAuth 2.1 server with DCR, Google sign-in | WorkOS / Auth0 / Clerk; custom on Firebase | Already using Supabase; supports MCP auth with DCR |
| 12 | Preferences = scored tags (−2..+2) with 60-day half-life | Fixed liked/disliked lists | Captures nuance and lets tastes drift |
| 13 | Variety: no same dish within 3 days, no same place within 2; 1 of 3 is "explore" | No variety rules | Avoid repetitive suggestions; keep learning |
| 14 | Meal slots: fixed default windows, user-overridable; timezone from location | Per-user mandatory setup | Low-friction defaults |
| 15 | Blocking onboarding before first recommendation | Lazy learning | Allergies must be known before first suggestion |
| 16 | Habits = dietary rules (hard) + budget, spice, skipped meals, dine-in/delivery, health goals (soft) | — | Concrete, structured profile |
| 17 | No-match fallback: dish-only + offer wider radius; never relax constraints | Silently widen radius / relax filters | Safety and transparency |
| 18 | Privacy: RLS, no cross-user sharing except place caches, `delete_my_data` | — | Allergy/diet data is sensitive |
| 19 | Python + FastMCP | TypeScript + MCP SDK | User preference; FastMCP has built-in Supabase auth provider |
| 20 | No rate limit during testing | 30 calls/user/day | Testing convenience — **must enable before public launch** |
| 21 | No `recommendation_id` in tool interface; server resolves feedback against recent batches | Explicit IDs passed by host | Simpler interface; trade-off: vague late feedback may mis-resolve |
| 22 | Dev environment in Docker: app via `docker compose` (hot reload), Supabase local via `supabase start`, tests in container | Host Python venv; full self-hosted Supabase in compose | Reproducible, no host Python; Supabase CLI already manages its own Docker stack |
| 23 | LLM: Claude Haiku 5.5 (`claude-haiku-5-5`) behind provider interface | Other cheap models | Cheap, fast, strong structured output |
| 24 | Geocoding via Google Places Text Search | Google Geocoding API; Nominatim | One API key, one bill |
| 25 | Timezone via offline `timezonefinder` | Google Time Zone API | Free |
| 26 | Per-user DB access with user's JWT (RLS enforced); caches via service role | Service role everywhere | Defence in depth for health data |
