# MCP Tools

## MCP tools

All tools require an authenticated user. All inputs are free text where possible so any host can call them without precise structuring.

### `recommend_meal(location: str, meal_slot: str | None = None, request: str | None = None)`

- `location` — **required**, short free text (e.g. "Bangsar", "near KLCC"). Geocoded server-side, cached.
- `meal_slot` — one of `breakfast | lunch | tea | dinner | supper`. If omitted, inferred from the user's local time (timezone derived from geocoded location).
- `request` — optional free-text nuance ("something soupy", "walking distance", "can drive"). May override the default travel radius.

Returns **3 options**, each:

| Field | Notes |
|---|---|
| dish | e.g. "Fried rice" |
| place | name, distance, rating, open-now — or `null` if no suitable place |
| reason | one line, e.g. "you rated spicy noodles +2 last week" |
| allergen_note | present when a declared allergen category is plausibly relevant; always says to confirm with vendor |

If the user has not completed onboarding, returns the onboarding questions instead (see §7).

Every returned batch is persisted as the user's **latest recommendation batch** (used to resolve feedback).

### `give_feedback(message: str)`

Free text, e.g. "the fried rice was quite good", "first one too oily", "had laksa today, loved it".

- Server LLM resolves the reference against the user's recent recommendation batches (most recent first).
- If no match, recorded as a free-standing meal event.
- Extracts structured tags + score (see §6) and stores a feedback event.

Known limitation: vague references ("the first one") given after a newer batch may resolve to the wrong item. Naming the dish avoids this.

### `update_profile(message: str)`

Free text, e.g. "I'm allergic to peanuts", "no beef", "budget RM15 for lunch", "I usually skip breakfast". Server LLM extracts profile changes and applies them. Allergy and dietary-rule changes are echoed back for confirmation in the response.

### `get_profile()`

Returns the stored profile and a summary of top learned likes/dislikes so the user can inspect and correct.

### `delete_my_data()`

Deletes all of the user's profile, feedback, and recommendation history. Shared places cache is unaffected (contains no personal data).

