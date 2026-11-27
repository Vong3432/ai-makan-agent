"""Meal slots: default windows, user overrides, inferring the slot from local time."""

import re
from dataclasses import dataclass
from datetime import time
from typing import Any

from makan.db.models import MealSlot

SLOT_ORDER: tuple[MealSlot, ...] = ("breakfast", "lunch", "tea", "dinner", "supper")

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


@dataclass(frozen=True)
class Window:
    start: time
    end: time  # may be earlier than start => wraps past midnight

    def contains(self, t: time) -> bool:
        if self.start <= self.end:
            return self.start <= t < self.end
        return t >= self.start or t < self.end


DEFAULT_WINDOWS: dict[MealSlot, Window] = {
    "breakfast": Window(time(6), time(10)),
    "lunch": Window(time(11), time(14)),
    "tea": Window(time(15), time(17)),
    "dinner": Window(time(18), time(21)),
    "supper": Window(time(21), time(1)),
}


def parse_hhmm(value: str) -> time:
    m = _HHMM.match(value.strip())
    if not m:
        raise ValueError(f"expected HH:MM, got {value!r}")
    return time(int(m[1]), int(m[2]))


def windows_for(overrides: dict[str, Any] | None) -> dict[MealSlot, Window]:
    """Defaults merged with stored overrides ({slot: {"start": "HH:MM", "end": "HH:MM"}}).
    Malformed overrides are ignored rather than breaking recommendations."""
    out = dict(DEFAULT_WINDOWS)
    for slot, w in (overrides or {}).items():
        if slot not in DEFAULT_WINDOWS or not isinstance(w, dict):
            continue
        try:
            out[slot] = Window(parse_hhmm(w["start"]), parse_hhmm(w["end"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def infer_slot(local: time, overrides: dict[str, Any] | None = None) -> MealSlot:
    """The slot whose window contains `local`; in a gap, the next slot to start."""
    windows = windows_for(overrides)
    for slot in SLOT_ORDER:
        if windows[slot].contains(local):
            return slot

    def minutes_until(slot: MealSlot) -> int:
        start = windows[slot].start
        delta = (start.hour * 60 + start.minute) - (local.hour * 60 + local.minute)
        return delta % (24 * 60)

    return min(SLOT_ORDER, key=minutes_until)
