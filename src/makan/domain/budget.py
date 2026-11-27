"""Map a per-meal budget to Google's 0..4 price level. Pure.

Thresholds are rough per-person meal costs for each Google level (upper bounds for levels
1..3; anything above is 4). Unknown currencies return None, so no budget penalty applies.
"""

_THRESHOLDS: dict[str, tuple[float, float, float]] = {
    "MYR": (15, 40, 100),
    "SGD": (8, 25, 60),
    "IDR": (50_000, 150_000, 400_000),
    "THB": (150, 400, 1_000),
    "USD": (15, 35, 70),
    "EUR": (15, 35, 70),
    "GBP": (12, 30, 60),
    "AUD": (20, 45, 90),
}


def budget_to_price_level(budget: float | None, currency: str | None) -> int | None:
    """The highest Google price level the budget comfortably covers (1..4), or None."""
    if budget is None or budget <= 0 or not currency:
        return None
    t = _THRESHOLDS.get(currency.upper())
    if t is None:
        return None
    for level, upper in enumerate(t, start=1):
        if budget <= upper:
            return level
    return 4
