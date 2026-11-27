"""Thin HTTP client for Google Places API (New) Text Search.

Every request carries an explicit `X-Goog-FieldMask` (cost control: the mask decides the
billing SKU), and every request is logged on the `makan.billing` logger (P4-T8).
"""

import logging
import time
from typing import Any

import httpx

from makan.location.geo import BBox

log = logging.getLogger(__name__)
billing_log = logging.getLogger("makan.billing")

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
TIMEOUT_S = 10.0


class PlacesAPIError(Exception):
    pass


class GooglePlacesHTTP:
    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        region_code: str | None = None,
    ) -> None:
        if not api_key:
            raise PlacesAPIError("GOOGLE_API_KEY is not set (see docs/SETUP_KEYS.md)")
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=TIMEOUT_S)
        self._region = region_code or None

    async def text_search(
        self,
        *,
        purpose: str,
        text_query: str,
        field_mask: str,
        page_size: int = 20,
        restrict_to: BBox | None = None,
    ) -> list[dict[str, Any]]:
        if not field_mask:
            raise ValueError("field_mask is required (cost control)")
        body: dict[str, Any] = {"textQuery": text_query, "pageSize": page_size}
        if self._region:
            body["regionCode"] = self._region
        if restrict_to is not None:
            body["locationRestriction"] = {
                "rectangle": {
                    "low": {"latitude": restrict_to.low.lat, "longitude": restrict_to.low.lng},
                    "high": {"latitude": restrict_to.high.lat, "longitude": restrict_to.high.lng},
                }
            }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._key,
            "X-Goog-FieldMask": field_mask,
        }

        started = time.perf_counter()
        status: int | str = "error"
        try:
            resp = await self._client.post(TEXT_SEARCH_URL, json=body, headers=headers)
            status = resp.status_code
        except httpx.HTTPError as e:
            raise PlacesAPIError(f"places text search failed: {e}") from e
        finally:
            billing_log.info(
                "billable api=places.searchText purpose=%s status=%s fields=%s ms=%d",
                purpose,
                status,
                field_mask,
                (time.perf_counter() - started) * 1000,
            )
        if resp.status_code != 200:
            # Body holds Google's error message; never contains the key.
            raise PlacesAPIError(f"places text search HTTP {resp.status_code}: {resp.text[:300]}")
        return resp.json().get("places", [])

    async def aclose(self) -> None:
        await self._client.aclose()
