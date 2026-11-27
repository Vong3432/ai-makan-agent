# Open Items

## Known caveats / open items

- Supabase OAuth 2.1 server is relatively new; DCR is **off by default** and must be enabled (Authentication → OAuth Server).
- Reported issue: Supabase DCR rejecting custom redirect schemes (e.g. `cursor://`) — affects native clients like Cursor, not ChatGPT/Claude web connectors. See https://github.com/supabase/auth/issues/2285.
- Specific LLM model not yet chosen.
- Rate limit value to set before launch (suggested starting point: 30 LLM-backed calls/user/day).
