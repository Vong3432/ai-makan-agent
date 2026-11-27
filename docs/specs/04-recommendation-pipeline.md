# Recommendation Pipeline

## Recommendation pipeline

1. **Resolve context** — geocode `location` (cache), derive timezone, infer `meal_slot`, determine radius (profile default, overridden by `request` text: "walking distance" ≈ 1 km, "can drive" ≈ 10 km).
2. **Candidate dishes** — LLM proposes candidate dishes suited to slot, cuisine context, and request.
3. **Hard filters** (never relaxed):
   - **Allergies** — LLM checks each candidate dish against typical ingredients; any likely match is excluded. Feedback can never override an allergy.
   - **Dietary rules** — e.g. halal, vegetarian, no beef.
4. **Candidate places** — Places nearby search within radius (cache-first), matched to dish/cuisine.
5. **Soft scoring** — `score = preference_score + novelty_bonus − repetition_penalty`, plus habit fit (budget, spice tolerance, health goals, dine-in vs delivery).
6. **Variety rules**
   - Same dish not repeated within **3 days**; same place not within **2 days** — unless explicitly requested.
   - Of the 3 options, **1 is always an "explore" pick** the user hasn't tried.
7. **Fallback** — if no place passes filters within radius: return dish-only suggestions and offer to widen the radius. Never relax allergies or dietary rules.
8. **Persist** batch; **respond**.

