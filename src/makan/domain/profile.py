"""Profile rules: applying extracted changes, onboarding completeness. Pure, no I/O."""

from dataclasses import dataclass, field

from makan.db.models import Profile
from makan.domain.preferences import norm
from makan.domain.slots import parse_hhmm
from makan.llm.jobs import ProfileChanges

REQUIRED_LOVES = 3
REQUIRED_DISLIKES = 3

ONBOARDING_QUESTIONS: dict[str, str] = {
    "allergies": "Do you have any food allergies? (say “none” if not)",
    "dietary_rules": "Any dietary rules, e.g. halal, vegetarian, no beef? (say “none” if not)",
    "loves": "Name 3 foods or dishes you love.",
    "dislikes": "Name 3 foods or dishes you dislike.",
    "budget": "What's your typical budget per meal (with currency)?",
    "radius": "How far are you usually willing to go for food (e.g. walking distance, 5 km)?",
}


@dataclass
class ApplyResult:
    profile: Profile
    safety_changes: list[str] = field(default_factory=list)  # echoed for confirmation
    other_changes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _merge(
    current: list[str], add: list[str], remove: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """Returns (new_list, added, removed) using normalised values."""
    items = [norm(x) for x in current]
    added = [a for a in dict.fromkeys(norm(x) for x in add) if a and a not in items]
    removed = [r for r in dict.fromkeys(norm(x) for x in remove) if r in items]
    new = [x for x in items if x not in removed] + added
    return new, added, removed


def apply_changes(profile: Profile, ch: ProfileChanges) -> ApplyResult:
    p = profile.model_copy(deep=True)
    res = ApplyResult(profile=p)

    # --- allergies (hard constraint) ---
    p.allergies, added, removed = _merge(p.allergies, ch.add_allergies, ch.remove_allergies)
    res.safety_changes += [f"added allergy: {a}" for a in added]
    res.safety_changes += [f"removed allergy: {r}" for r in removed]
    if added or removed or ch.no_allergies:
        p.allergies_answered = True
    if ch.no_allergies and p.allergies:
        res.notes.append(
            "You said you have no allergies, but I still have: "
            f"{', '.join(p.allergies)}. Tell me explicitly to remove them if that's right."
        )
    elif ch.no_allergies and not added:
        res.safety_changes.append("no allergies")

    # --- dietary rules (hard constraint) ---
    p.dietary_rules, added, removed = _merge(
        p.dietary_rules, ch.add_dietary_rules, ch.remove_dietary_rules
    )
    res.safety_changes += [f"added dietary rule: {a}" for a in added]
    res.safety_changes += [f"removed dietary rule: {r}" for r in removed]
    if added or removed or ch.no_dietary_rules:
        p.dietary_answered = True
    if ch.no_dietary_rules and p.dietary_rules:
        res.notes.append(
            "You said you have no dietary rules, but I still have: "
            f"{', '.join(p.dietary_rules)}. Tell me explicitly to remove them if that's right."
        )
    elif ch.no_dietary_rules and not added:
        res.safety_changes.append("no dietary rules")

    # --- soft habits ---
    if ch.budget_per_meal is not None and ch.budget_per_meal > 0:
        p.budget_per_meal = ch.budget_per_meal
        if ch.currency:
            p.currency = ch.currency.upper()
        res.other_changes.append(f"budget: {p.currency or ''} {p.budget_per_meal:g}".strip())
    if ch.spice_tolerance is not None:
        p.spice_tolerance = max(0, min(4, ch.spice_tolerance))
        res.other_changes.append(f"spice tolerance: {p.spice_tolerance}/4")
    if ch.default_radius_km is not None and ch.default_radius_km > 0:
        p.default_radius_km = ch.default_radius_km
        res.other_changes.append(f"travel radius: {p.default_radius_km:g} km")
    if ch.dine_preference:
        p.dine_preference = ch.dine_preference
        res.other_changes.append(f"dining: {p.dine_preference.replace('_', '-')}")

    skipped = set(p.skipped_meals) | set(ch.add_skipped_meals)
    skipped -= set(ch.remove_skipped_meals)
    if skipped != set(p.skipped_meals):
        p.skipped_meals = sorted(skipped)
        res.other_changes.append(f"usually skips: {', '.join(p.skipped_meals) or 'nothing'}")

    p.health_goals, added, removed = _merge(
        p.health_goals, ch.add_health_goals, ch.remove_health_goals
    )
    res.other_changes += [f"health goal +{a}" for a in added] + [
        f"health goal -{r}" for r in removed
    ]

    for w in ch.slot_windows:
        try:
            parse_hhmm(w.start), parse_hhmm(w.end)
        except ValueError:
            res.notes.append(f"Couldn't read the time for {w.slot}; use HH:MM.")
            continue
        p.slot_windows = {**p.slot_windows, w.slot: {"start": w.start, "end": w.end}}
        res.other_changes.append(f"{w.slot} time: {w.start}–{w.end}")

    if ch.not_understood:
        res.notes.append("I didn't catch: " + "; ".join(ch.not_understood))
    return res


@dataclass(frozen=True)
class OnboardingStatus:
    missing: list[str]

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def questions(self) -> list[str]:
        return [ONBOARDING_QUESTIONS[m] for m in self.missing]


def onboarding_status(profile: Profile, loves: int, dislikes: int) -> OnboardingStatus:
    missing: list[str] = []
    if not profile.allergies_answered:
        missing.append("allergies")
    if not profile.dietary_answered:
        missing.append("dietary_rules")
    if loves < REQUIRED_LOVES:
        missing.append("loves")
    if dislikes < REQUIRED_DISLIKES:
        missing.append("dislikes")
    if profile.budget_per_meal is None:
        missing.append("budget")
    if profile.default_radius_km is None:
        missing.append("radius")
    return OnboardingStatus(missing)
