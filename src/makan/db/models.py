"""Typed rows for the Postgres tables (see supabase/migrations)."""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

MealSlot = Literal["breakfast", "lunch", "tea", "dinner", "supper"]
DinePreference = Literal["dine_in", "delivery", "either"]


class Profile(BaseModel):
    user_id: UUID
    onboarded: bool = False
    allergies: list[str] = Field(default_factory=list)
    allergies_answered: bool = False
    dietary_rules: list[str] = Field(default_factory=list)
    dietary_answered: bool = False
    budget_per_meal: float | None = None
    currency: str | None = None
    spice_tolerance: int | None = Field(default=None, ge=0, le=4)
    skipped_meals: list[MealSlot] = Field(default_factory=list)
    dine_preference: DinePreference | None = None
    health_goals: list[str] = Field(default_factory=list)
    default_radius_km: float | None = Field(default=None, gt=0)
    slot_windows: dict[str, Any] = Field(default_factory=dict)
    timezone: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class NewRecommendation(BaseModel):
    position: int = Field(ge=1, le=3)
    dish: str
    place_id: str | None = None
    place_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    is_explore: bool = False


class Recommendation(NewRecommendation):
    id: UUID
    batch_id: UUID
    user_id: UUID


class NewBatch(BaseModel):
    meal_slot: MealSlot
    location: str
    lat: float | None = None
    lng: float | None = None


class Batch(NewBatch):
    id: UUID
    user_id: UUID
    created_at: datetime
    recommendations: list[Recommendation] = Field(default_factory=list)


class NewFeedbackEvent(BaseModel):
    raw_message: str
    recommendation_id: UUID | None = None
    dish: str | None = None
    place_id: str | None = None
    meal_slot: MealSlot | None = None
    tags: list[str] = Field(default_factory=list)
    score: int = Field(ge=-2, le=2)
    created_at: datetime | None = None  # None => server default now()


class FeedbackEvent(NewFeedbackEvent):
    id: UUID
    user_id: UUID
    created_at: datetime


class GeocodeEntry(BaseModel):
    query_norm: str
    lat: float
    lng: float
    timezone: str | None = None
    fetched_at: datetime | None = None


class UsageCount(BaseModel):
    day: date
    calls: int
