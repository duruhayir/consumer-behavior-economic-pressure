"""Build the complete 396-row country-month master dataset without imputation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from eurostat import flatten_jsonstat, load_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "consumer_behavior_eu_2015_2025.csv"
COUNTRIES = {"NL": "Netherlands", "DE": "Germany", "FR": "France"}
RETAIL_COLUMNS = {
    "G47": "retail_total_index",
    "G47_FOOD": "retail_food_index",
    "G47_NFOOD_X_G473": "retail_nonfood_index",
}
BASE_VALUE_COLUMNS = [
    "inflation_yoy",
    "consumer_confidence",
    "retail_total_index",
    "retail_food_index",
    "retail_nonfood_index",
]
DERIVED_COLUMNS = [
    "retail_total_yoy",
    "retail_food_yoy",
    "retail_nonfood_yoy",
    "consumer_confidence_lag1",
    "consumer_confidence_lag2",
    "consumer_confidence_lag3",
    "inflation_lag1",
    "inflation_lag2",
    "inflation_lag3",
]


def month_range(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    months: list[str] = []
    while (year, month) <= (end_year, end_month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def unique_value_map(records: list[dict], key_fields: list[str]) -> dict[tuple, float | None]:
    result: dict[tuple, float | None] = {}
    for record in records:
        key = tuple(record[field] for field in key_fields)
        if key in result:
            raise ValueError(f"Duplicate source observation at {key_fields}={key}")
        result[key] = record["value"]
    return result


def fmt(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, float):
        return format(value, ".12g")
    return value


def main() -> None:
    manifest = json.loads((RAW_DIR / "download_manifest.json").read_text(encoding="utf-8"))
    source_files = {
        name: RAW_DIR / details["file"]
        for name, details in manifest["sources"].items()
    }
    retail_records = flatten_jsonstat(load_json(source_files["retail"]))
    inflation_records = flatten_jsonstat(load_json(source_files["inflation"]))
    confidence_records = flatten_jsonstat(load_json(source_files["consumer_confidence"]))

    retail = unique_value_map(retail_records, ["geo", "time", "nace_r2"])
    inflation = unique_value_map(inflation_records, ["geo", "time"])
    confidence = unique_value_map(confidence_records, ["geo", "time"])

    months = month_range("2015-01", "2025-12")
    rows: list[dict] = []
    for country_code, country in COUNTRIES.items():
        country_rows: list[dict] = []
        for month in months:
            row = {
                "country_code": country_code,
                "country": country,
                "date": f"{month}-01",
                "inflation_yoy": inflation.get((country_code, month)),
                "consumer_confidence": confidence.get((country_code, month)),
            }
            for nace_code, column in RETAIL_COLUMNS.items():
                row[column] = retail.get((country_code, month, nace_code))
            country_rows.append(row)

        for i, row in enumerate(country_rows):
            for index_column, yoy_column in (
                ("retail_total_index", "retail_total_yoy"),
                ("retail_food_index", "retail_food_yoy"),
                ("retail_nonfood_index", "retail_nonfood_yoy"),
            ):
                current = row[index_column]
                previous = country_rows[i - 12][index_column] if i >= 12 else None
                row[yoy_column] = (
                    100.0 * (current / previous - 1.0)
                    if current is not None and previous not in (None, 0)
                    else None
                )
            for lag in (1, 2, 3):
                row[f"consumer_confidence_lag{lag}"] = (
                    country_rows[i - lag]["consumer_confidence"] if i >= lag else None
                )
                row[f"inflation_lag{lag}"] = (
                    country_rows[i - lag]["inflation_yoy"] if i >= lag else None
                )
        rows.extend(country_rows)

    rows.sort(key=lambda row: (row["country_code"], row["date"]))
    fieldnames = ["country_code", "country", "date", *BASE_VALUE_COLUMNS, *DERIVED_COLUMNS]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: fmt(row.get(key)) for key in fieldnames} for row in rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
