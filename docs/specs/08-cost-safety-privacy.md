# Cost, Safety & Privacy

## Cost controls

- Google Places: request only basic fields (name, location, types, rating, open-now); shared cache keyed by geohash + cuisine, ~7-day TTL; nearby search only on cache miss.
- Geocoding: cached by normalised query text.
- LLM: cheap/fast model; provider behind an interface for easy swapping.
- Cloud Run scales to zero; Supabase free tier at small scale.
- Per-user daily rate limit: **off for testing, required before public launch**.

## Safety & privacy

- Allergies are hard exclusions, never weighted down by feedback.
- Every response touching a declared allergen category carries a "confirm with the vendor" note.
- Dietary rules enforced as hard constraints.
- Allergy/diet data treated as sensitive health data: RLS on all user tables, no cross-user sharing (only places/geocode caches are shared), `delete_my_data` tool.
- Dynamic Client Registration lets any MCP client register: require user consent on authorization, validate redirect URIs, monitor registered clients.
