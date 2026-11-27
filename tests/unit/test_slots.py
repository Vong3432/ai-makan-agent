from datetime import time

import pytest

from makan.domain.slots import Window, infer_slot, parse_hhmm, windows_for


@pytest.mark.parametrize(
    ("t", "slot"),
    [
        (time(7), "breakfast"),
        (time(12, 30), "lunch"),
        (time(15), "tea"),
        (time(20, 59), "dinner"),
        (time(21), "supper"),  # boundary: dinner ends where supper starts
        (time(0, 30), "supper"),  # wraps past midnight
        (time(10, 30), "lunch"),  # gap -> next slot
        (time(3), "breakfast"),  # overnight gap -> breakfast
        (time(17, 30), "dinner"),
    ],
)
def test_infer_slot_defaults(t, slot):
    assert infer_slot(t) == slot


def test_infer_slot_with_override():
    assert (
        infer_slot(time(10, 30), {"breakfast": {"start": "09:00", "end": "11:00"}}) == "breakfast"
    )


def test_malformed_overrides_ignored():
    w = windows_for({"breakfast": {"start": "9am"}, "brunch": {}, "lunch": "x"})
    assert w["breakfast"] == Window(time(6), time(10))


def test_parse_hhmm():
    assert parse_hhmm(" 07:05 ") == time(7, 5)
    for bad in ("7:05", "24:00", "12:60", "noon"):
        with pytest.raises(ValueError):
            parse_hhmm(bad)
