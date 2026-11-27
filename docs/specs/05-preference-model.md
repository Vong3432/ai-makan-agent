# Preference Model

## Preference model

- Each feedback event is converted by the LLM into **tags** (dish, cuisine, attributes like `spicy`/`oily`/`soupy`, place) with a score in **−2…+2**.
- Per-user tag score = Σ (event score × decay), where decay uses a **60-day half-life**:
  `weight = 0.5 ^ (age_days / 60)`.
- Preference score for a candidate = sum of the user's tag scores for that candidate's tags.
- Allergies and dietary rules live in the profile as hard constraints and are **not** part of this model.

