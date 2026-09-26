"""Run and save explicit master-dataset quality checks."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "consumer_behavior_eu_2015_2025.csv"
TABLES_DIR = PROJECT_ROOT / "outputs" / "tables"
COUNTRIES = ["NL", "DE", "FR"]
CORE_VARIABLES = [
    "inflation_yoy",
    "consumer_confidence",
    "retail_total_index",
    "retail_food_index",
    "retail_nonfood_index",
]
DERIVED_VARIABLES = [
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
VALUE_VARIABLES = CORE_VARIABLES + DERIVED_VARIABLES


def month_range(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    values = []
    while (year, month) <= (end_year, end_month):
        values.append(f"{year:04d}-{month:02d}-01")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return values


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    checks: list[dict] = []
    row_count_ok = len(rows) == 396
    checks.append({
        "check": "expected_master_grid_rows",
        "scope": "all",
        "observed": len(rows),
        "expected": 396,
        "status": "PASS" if row_count_ok else "FAIL",
        "details": "3 countries x 132 months",
    })

    key_counts = Counter((row["country_code"], row["date"]) for row in rows)
    duplicate_count = sum(count - 1 for count in key_counts.values() if count > 1)
    checks.append({
        "check": "duplicate_country_date_rows",
        "scope": "all",
        "observed": duplicate_count,
        "expected": 0,
        "status": "PASS" if duplicate_count == 0 else "FAIL",
        "details": "candidate key: country_code + date",
    })

    expected_dates = month_range("2015-01", "2025-12")
    expected_date_set = set(expected_dates)
    by_country: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_country[row["country_code"]].append(row)

    coverage_rows: list[dict] = []
    gap_rows: list[dict] = []
    for country_code in COUNTRIES:
        country_rows = sorted(by_country[country_code], key=lambda row: row["date"])
        actual_dates = {row["date"] for row in country_rows}
        missing_calendar = sorted(expected_date_set - actual_dates)
        unexpected_calendar = sorted(actual_dates - expected_date_set)
        coverage_rows.append({
            "country_code": country_code,
            "row_count": len(country_rows),
            "distinct_months": len(actual_dates),
            "start_date": country_rows[0]["date"] if country_rows else "",
            "end_date": country_rows[-1]["date"] if country_rows else "",
            "missing_calendar_months": len(missing_calendar),
            "unexpected_calendar_months": len(unexpected_calendar),
        })
        coverage_ok = (
            len(actual_dates) == 132
            and not missing_calendar
            and not unexpected_calendar
            and (country_rows[0]["date"] if country_rows else "") == "2015-01-01"
            and (country_rows[-1]["date"] if country_rows else "") == "2025-12-01"
        )
        checks.append({
            "check": "date_coverage",
            "scope": country_code,
            "observed": f"{len(actual_dates)} months",
            "expected": "132 months, 2015-01-01 to 2025-12-01",
            "status": "PASS" if coverage_ok else "FAIL",
            "details": f"missing={len(missing_calendar)}; unexpected={len(unexpected_calendar)}",
        })
        for missing_date in missing_calendar:
            gap_rows.append({
                "country_code": country_code,
                "date": missing_date,
                "variable": "__calendar__",
                "gap_type": "missing country-month row",
            })
        for row in country_rows:
            for variable in CORE_VARIABLES:
                if row[variable] == "":
                    gap_rows.append({
                        "country_code": country_code,
                        "date": row["date"],
                        "variable": variable,
                        "gap_type": "missing source observation",
                    })

    checks.append({
        "check": "unexpected_gaps",
        "scope": "calendar_and_core_source_series",
        "observed": len(gap_rows),
        "expected": 0,
        "status": "PASS" if not gap_rows else "WARN",
        "details": "Derived-variable structural nulls are reported separately, not treated as unexpected gaps",
    })

    missing_rows: list[dict] = []
    series_coverage_rows: list[dict] = []
    for country_code in COUNTRIES:
        country_rows = sorted(by_country[country_code], key=lambda row: row["date"])
        for variable in VALUE_VARIABLES:
            missing = sum(row[variable] == "" for row in country_rows)
            nonmissing_dates = [row["date"] for row in country_rows if row[variable] != ""]
            missing_rows.append({
                "country_code": country_code,
                "variable": variable,
                "missing_count": missing,
                "total_rows": len(country_rows),
                "missing_percent": f"{(100 * missing / len(country_rows)):.3f}" if country_rows else "",
            })
            series_coverage_rows.append({
                "country_code": country_code,
                "variable": variable,
                "nonmissing_count": len(nonmissing_dates),
                "missing_count": missing,
                "first_nonmissing_date": nonmissing_dates[0] if nonmissing_dates else "",
                "last_nonmissing_date": nonmissing_dates[-1] if nonmissing_dates else "",
            })

    for variable, expected_missing in {
        "retail_total_yoy": 36,
        "retail_food_yoy": 36,
        "retail_nonfood_yoy": 36,
        "consumer_confidence_lag1": 3,
        "consumer_confidence_lag2": 6,
        "consumer_confidence_lag3": 9,
        "inflation_lag1": 3,
        "inflation_lag2": 6,
        "inflation_lag3": 9,
    }.items():
        observed = sum(row[variable] == "" for row in rows)
        checks.append({
            "check": "structural_missingness",
            "scope": variable,
            "observed": observed,
            "expected": expected_missing,
            "status": "PASS" if observed == expected_missing else "WARN",
            "details": "Expected from within-country 12-month change or 1-3 month lag construction",
        })

    sorted_ok = rows == sorted(rows, key=lambda row: (row["country_code"], row["date"]))
    checks.append({
        "check": "sort_order",
        "scope": "all",
        "observed": "country_code,date" if sorted_ok else "not sorted",
        "expected": "country_code,date",
        "status": "PASS" if sorted_ok else "FAIL",
        "details": "lexicographic country code followed by chronological ISO date",
    })

    write_csv(TABLES_DIR / "data_quality_checks.csv", list(checks[0]), checks)
    write_csv(TABLES_DIR / "date_coverage_by_country.csv", list(coverage_rows[0]), coverage_rows)
    write_csv(TABLES_DIR / "missing_values_by_country.csv", list(missing_rows[0]), missing_rows)
    write_csv(TABLES_DIR / "source_series_coverage.csv", list(series_coverage_rows[0]), series_coverage_rows)
    write_csv(
        TABLES_DIR / "unexpected_gaps.csv",
        ["country_code", "date", "variable", "gap_type"],
        gap_rows,
    )

    failed = [check for check in checks if check["status"] == "FAIL"]
    warnings = [check for check in checks if check["status"] == "WARN"]
    report = [
        "# Data quality validation",
        "",
        "Dataset grain: one row per country and calendar month for NL, DE, and FR, January 2015 through December 2025.",
        "",
        f"- Master rows: **{len(rows)} / 396**",
        f"- Duplicate country-date rows: **{duplicate_count}**",
        f"- Unexpected calendar or core-source gaps: **{len(gap_rows)}**",
        f"- Failed checks: **{len(failed)}**",
        f"- Warning checks: **{len(warnings)}**",
        "",
        "Structural missingness is expected only where year-on-year calculations need 12 prior months and lags need 1-3 prior months. No values are imputed.",
        "",
        "See the companion CSV tables in this directory for complete check-level evidence.",
        "",
    ]
    (TABLES_DIR / "DATA_QUALITY_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Validation complete: {len(failed)} failed checks, {len(warnings)} warnings")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
