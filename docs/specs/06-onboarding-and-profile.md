# Onboarding & Profile

## Onboarding

On first `recommend_meal` call (or any call before onboarding is complete), the server returns a short question set instead of recommendations. Required before any recommendation:

1. Allergies
2. Dietary rules (halal, vegetarian, no beef, …)
3. 3 foods loved, 3 foods disliked
4. Typical budget per meal
5. Default travel radius

Answers are submitted via `update_profile`.


## Profile & habits

| Field | Type of constraint |
|---|---|
| Allergies | Hard |
| Dietary rules | Hard |
| Budget per meal | Soft |
| Spice tolerance | Soft |
| Usually-skipped meals | Soft |
| Dine-in vs delivery preference | Soft |
| Health goals (e.g. low-carb) | Soft |
| Default travel radius | Default, overridable per request |
| Meal slot windows | Defaults below, user-overridable |
| Timezone | Derived from latest geocoded location |

Default meal slot windows (local time):

| Slot | Window |
|---|---|
| breakfast | 06:00–10:00 |
| lunch | 11:00–14:00 |
| tea | 15:00–17:00 |
| dinner | 18:00–21:00 |
| supper | 21:00–01:00 |

