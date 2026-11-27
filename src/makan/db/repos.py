"""Thin repositories over Supabase tables.

Per-user repos always filter by user_id, even when RLS would already do so
(dev mode uses the service role, which bypasses RLS).
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from supabase import AsyncClient

from makan.db.models import (
    Batch,
    FeedbackEvent,
    GeocodeEntry,
    NewBatch,
    NewFeedbackEvent,
    NewRecommendation,
    Profile,
    Recommendation,
)


class _UserRepo:
    def __init__(self, client: AsyncClient, user_id: str) -> None:
        self.db = client
        self.user_id = user_id


class ProfileRepo(_UserRepo):
    async def get(self) -> Profile | None:
        res = (
            await self.db.table("profiles")
            .select("*")
            .eq("user_id", self.user_id)
            .maybe_single()
            .execute()
        )
        return Profile.model_validate(res.data) if res and res.data else None

    async def upsert(self, profile: Profile) -> Profile:
        row = profile.model_dump(mode="json", exclude={"created_at", "updated_at"})
        row["user_id"] = self.user_id
        res = await self.db.table("profiles").upsert(row).execute()
        return Profile.model_validate(res.data[0])


class BatchRepo(_UserRepo):
    async def create(self, batch: NewBatch, recs: list[NewRecommendation]) -> Batch:
        b = (
            await self.db.table("recommendation_batches")
            .insert({**batch.model_dump(mode="json"), "user_id": self.user_id})
            .execute()
        ).data[0]
        rows = [
            {**r.model_dump(mode="json"), "batch_id": b["id"], "user_id": self.user_id}
            for r in recs
        ]
        saved = (await self.db.table("recommendations").insert(rows).execute()).data if rows else []
        return Batch.model_validate({**b, "recommendations": saved})

    async def recent(self, limit: int = 3) -> list[Batch]:
        res = (
            await self.db.table("recommendation_batches")
            .select("*, recommendations(*)")
            .eq("user_id", self.user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        batches = [Batch.model_validate(b) for b in res.data]
        for b in batches:
            b.recommendations.sort(key=lambda r: r.position)
        return batches

    async def recommendations_since(self, since: datetime) -> list[tuple[datetime, Recommendation]]:
        """Recommendations shown since `since` (for repetition rules), newest first."""
        res = (
            await self.db.table("recommendation_batches")
            .select("created_at, recommendations(*)")
            .eq("user_id", self.user_id)
            .gte("created_at", since.isoformat())
            .order("created_at", desc=True)
            .execute()
        )
        out: list[tuple[datetime, Recommendation]] = []
        for b in res.data:
            at = datetime.fromisoformat(b["created_at"])
            out.extend((at, Recommendation.model_validate(r)) for r in b["recommendations"])
        return out


class FeedbackRepo(_UserRepo):
    async def add(self, events: list[NewFeedbackEvent]) -> list[FeedbackEvent]:
        if not events:
            return []
        rows = [
            {**e.model_dump(mode="json", exclude_none=True), "user_id": self.user_id}
            for e in events
        ]
        res = await self.db.table("feedback_events").insert(rows).execute()
        return [FeedbackEvent.model_validate(r) for r in res.data]

    async def list(self, since: datetime | None = None) -> list[FeedbackEvent]:
        q = self.db.table("feedback_events").select("*").eq("user_id", self.user_id)
        if since is not None:
            q = q.gte("created_at", since.isoformat())
        res = await q.order("created_at", desc=True).execute()
        return [FeedbackEvent.model_validate(r) for r in res.data]

    async def profile_item_counts(self) -> tuple[int, int]:
        """Distinct loved / disliked dishes stated via update_profile (onboarding counts)."""
        res = (
            await self.db.table("feedback_events")
            .select("dish, score")
            .eq("user_id", self.user_id)
            .eq("source", "profile")
            .execute()
        )
        loves = {r["dish"].strip().lower() for r in res.data if r["dish"] and r["score"] > 0}
        dislikes = {r["dish"].strip().lower() for r in res.data if r["dish"] and r["score"] < 0}
        return len(loves), len(dislikes)


class UsageRepo(_UserRepo):
    async def increment(self, day: date) -> int:
        res = await self.db.rpc(
            "increment_usage", {"p_user_id": self.user_id, "p_day": day.isoformat()}
        ).execute()
        return int(res.data)


class CacheRepo:
    """Shared caches. Use with the service-role client only."""

    def __init__(self, client: AsyncClient) -> None:
        self.db = client

    async def get_places(self, key: str, max_age: timedelta) -> Any | None:
        res = (
            await self.db.table("places_cache")
            .select("payload")
            .eq("cache_key", key)
            .gte("fetched_at", (datetime.now(UTC) - max_age).isoformat())
            .maybe_single()
            .execute()
        )
        return res.data["payload"] if res and res.data else None

    async def put_places(self, key: str, payload: Any) -> None:
        await (
            self.db.table("places_cache")
            .upsert(
                {
                    "cache_key": key,
                    "payload": payload,
                    "fetched_at": datetime.now(UTC).isoformat(),
                }
            )
            .execute()
        )

    async def get_geocode(self, query_norm: str) -> GeocodeEntry | None:
        res = (
            await self.db.table("geocode_cache")
            .select("*")
            .eq("query_norm", query_norm)
            .maybe_single()
            .execute()
        )
        return GeocodeEntry.model_validate(res.data) if res and res.data else None

    async def put_geocode(self, entry: GeocodeEntry) -> None:
        row = entry.model_dump(mode="json", exclude={"fetched_at"})
        row["fetched_at"] = datetime.now(UTC).isoformat()
        await self.db.table("geocode_cache").upsert(row).execute()
