"""Small standard-library helpers for Eurostat JSON-stat responses."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


API_BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
USER_AGENT = "consumer-behavior-economic-pressure/1.0 (academic reproducibility project)"


def build_url(dataset: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode(params, doseq=True)
    return f"{API_BASE}/{dataset}?{query}"


def fetch_bytes(url: str, attempts: int = 4, timeout: int = 90) -> bytes:
    """Download bytes with short retry/backoff for transient Eurostat errors."""
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Failed to download {url}") from last_error


def fetch_json(url: str) -> tuple[bytes, dict[str, Any]]:
    raw = fetch_bytes(url)
    return raw, json.loads(raw.decode("utf-8-sig"))


def write_untouched(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def category_codes(payload: dict[str, Any], dimension: str) -> dict[str, str]:
    category = payload["dimension"][dimension]["category"]
    labels = category.get("label", {})
    positions = category.get("index", {})
    if isinstance(positions, list):
        codes: Iterable[str] = positions
    else:
        codes = positions.keys()
    return {code: labels.get(code, code) for code in codes}


def require_dimensions(payload: dict[str, Any], required: Iterable[str]) -> None:
    actual = set(payload.get("id", []))
    missing = set(required) - actual
    if missing:
        raise ValueError(f"Missing expected dimensions {sorted(missing)}; found {sorted(actual)}")


def require_codes(payload: dict[str, Any], expected: dict[str, Iterable[str]]) -> None:
    for dimension, codes in expected.items():
        available = category_codes(payload, dimension)
        missing = set(codes) - set(available)
        if missing:
            raise ValueError(
                f"Missing codes {sorted(missing)} in {dimension}; "
                f"dataset currently exposes {len(available)} codes"
            )


def _ordered_codes(payload: dict[str, Any], dimension: str) -> list[str]:
    index = payload["dimension"][dimension]["category"]["index"]
    if isinstance(index, list):
        return list(index)
    return [code for code, _ in sorted(index.items(), key=lambda item: item[1])]


def flatten_jsonstat(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a JSON-stat cube to observation records, retaining null cells/status."""
    dimensions = payload["id"]
    sizes = payload["size"]
    codes = [_ordered_codes(payload, dimension) for dimension in dimensions]
    values = payload.get("value", {})
    statuses = payload.get("status", {})
    total = 1
    for size in sizes:
        total *= size

    records: list[dict[str, Any]] = []
    for flat_index in range(total):
        remainder = flat_index
        coordinates = [0] * len(sizes)
        for i in range(len(sizes) - 1, -1, -1):
            coordinates[i] = remainder % sizes[i]
            remainder //= sizes[i]
        if isinstance(values, list):
            value = values[flat_index] if flat_index < len(values) else None
        else:
            value = values.get(str(flat_index))
        if isinstance(statuses, list):
            status = statuses[flat_index] if flat_index < len(statuses) else None
        else:
            status = statuses.get(str(flat_index))
        record = {
            dimension: codes[i][coordinates[i]]
            for i, dimension in enumerate(dimensions)
        }
        record["value"] = value
        record["status"] = status
        records.append(record)
    return records


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))
