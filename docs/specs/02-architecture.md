# Architecture

## Architecture

```
 MCP host (ChatGPT / Claude / ...)
        │  Streamable HTTP + OAuth 2.1 bearer token
        ▼
 ┌──────────────────────────────────────────┐
 │  FastMCP server (Python) on Cloud Run    │
 │  ├─ Tools layer (5 tools)                │
 │  ├─ Agent core (LLM, behind interface)   │
 │  ├─ Ranking engine (deterministic)       │
 │  ├─ Places client + shared cache         │
 │  └─ Geocoding client + cache             │
 └──────────────────────────────────────────┘
        │                     │
        ▼                     ▼
 Supabase                Google Places API (New)
  ├─ Auth (OAuth 2.1 server, DCR, Google sign-in)
  └─ Postgres (RLS)
```

| Concern | Choice |
|---|---|
| Language / framework | Python + FastMCP |
| Transport | Remote MCP over Streamable HTTP |
| Hosting | Google Cloud Run (container, scales to zero) |
| Auth | Supabase Auth as OAuth 2.1 server, Dynamic Client Registration enabled, Google sign-in; integrated via FastMCP's Supabase auth provider |
| Database | Supabase Postgres with Row Level Security |
| LLM | Cheap/fast model, paid by operator, behind a swappable provider interface |
| Places | Google Places API (New), minimal field mask, shared cache |
| Rate limiting | Per-user daily counter implemented but **disabled** during testing; must be enabled before public launch |

### Agent style

"Fat agent": the server runs its own LLM and ranking logic. The host LLM only relays user intent into a small set of free-text tools and presents the results. Hard constraints (allergies, dietary rules) are enforced server-side, never left to the host.

