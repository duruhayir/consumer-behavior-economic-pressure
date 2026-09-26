"""Inspect live Eurostat schemas, validate selections, and download bounded extracts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from eurostat import (
    build_url,
    category_codes,
    fetch_json,
    require_codes,
    require_dimensions,
    write_untouched,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
COUNTRIES = ["NL", "DE", "FR"]
START = "2015-01"
END = "2025-12"


def inspect(dataset: str) -> tuple[dict, str, bytes]:
    url = build_url(
        dataset,
        {
            "lang": "en",
            "geo": COUNTRIES,
            "sinceTimePeriod": START,
            "untilTimePeriod": "2015-02",
        },
    )
    raw, payload = fetch_json(url)
    return payload, url, raw


def download(dataset: str, filename: str, params: dict) -> tuple[dict, str]:
    url = build_url(dataset, {"lang": "en", **params})
    raw, payload = fetch_json(url)
    write_untouched(RAW_DIR / filename, raw)
    return payload, url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true", help="replace existing raw extracts")
    args = parser.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    probes: dict[str, dict] = {}
    probe_urls: dict[str, str] = {}
    for dataset in ("sts_trtu_m", "prc_hicp_minr", "ei_bsco_m"):
        payload, url, raw = inspect(dataset)
        probes[dataset] = payload
        probe_urls[dataset] = url
        write_untouched(RAW_DIR / f"schema_probe_{dataset}.json", raw)

    retail_probe = probes["sts_trtu_m"]
    require_dimensions(retail_probe, ["freq", "indic_bt", "nace_r2", "s_adj", "unit", "geo", "time"])
    require_codes(
        retail_probe,
        {
            "freq": ["M"],
            "indic_bt": ["VOL_SLS"],
            "nace_r2": ["G47", "G47_FOOD", "G47_NFOOD_X_G473"],
            "s_adj": ["SCA"],
            "unit": ["I21"],
            "geo": COUNTRIES,
        },
    )

    hicp_probe = probes["prc_hicp_minr"]
    require_dimensions(hicp_probe, ["freq", "unit", "geo", "time"])
    if "coicop18" in hicp_probe["id"]:
        hicp_classification_dimension = "coicop18"
        hicp_all_items_code = "TOTAL"
    elif "coicop" in hicp_probe["id"]:
        hicp_classification_dimension = "coicop"
        hicp_all_items_code = "CP00"
    else:
        raise ValueError("Could not identify the current HICP classification dimension")
    require_codes(
        hicp_probe,
        {
            "freq": ["M"],
            "unit": ["RCH_A"],
            hicp_classification_dimension: [hicp_all_items_code],
            "geo": COUNTRIES,
        },
    )

    confidence_probe = probes["ei_bsco_m"]
    require_dimensions(confidence_probe, ["freq", "indic", "s_adj", "unit", "geo", "time"])
    require_codes(
        confidence_probe,
        {
            "freq": ["M"],
            "indic": ["BS-CSMCI"],
            "s_adj": ["SA"],
            "unit": ["BAL"],
            "geo": COUNTRIES,
        },
    )

    source_specs = {
        "retail": {
            "dataset": "sts_trtu_m",
            "file": "retail_sts_trtu_m_2015_2025.json",
            "params": {
                "freq": "M",
                "indic_bt": "VOL_SLS",
                "nace_r2": ["G47", "G47_FOOD", "G47_NFOOD_X_G473"],
                "s_adj": "SCA",
                "unit": "I21",
                "geo": COUNTRIES,
                "sinceTimePeriod": START,
                "untilTimePeriod": END,
            },
        },
        "inflation": {
            "dataset": "prc_hicp_minr",
            "file": "inflation_prc_hicp_minr_2015_2025.json",
            "params": {
                "freq": "M",
                "unit": "RCH_A",
                hicp_classification_dimension: hicp_all_items_code,
                "geo": COUNTRIES,
                "sinceTimePeriod": START,
                "untilTimePeriod": END,
            },
        },
        "consumer_confidence": {
            "dataset": "ei_bsco_m",
            "file": "consumer_confidence_ei_bsco_m_2015_2025.json",
            "params": {
                "freq": "M",
                "indic": "BS-CSMCI",
                "s_adj": "SA",
                "unit": "BAL",
                "geo": COUNTRIES,
                "sinceTimePeriod": START,
                "untilTimePeriod": END,
            },
        },
    }

    manifest_sources: dict[str, dict] = {}
    for name, spec in source_specs.items():
        target = RAW_DIR / spec["file"]
        if target.exists() and not args.overwrite:
            raise FileExistsError(f"{target} already exists; use --overwrite to refresh")
        payload, url = download(spec["dataset"], spec["file"], spec["params"])
        if payload.get("error"):
            raise RuntimeError(f"Eurostat returned an error for {name}: {payload['error']}")
        manifest_sources[name] = {
            "dataset": spec["dataset"],
            "file": spec["file"],
            "url": url,
            "selection": spec["params"],
            "dimensions_returned": payload.get("id"),
            "sizes_returned": payload.get("size"),
        }

    schema_evidence = {
        "retail": {
            dimension: category_codes(retail_probe, dimension)
            for dimension in ("indic_bt", "nace_r2", "s_adj", "unit")
        },
        "inflation": {
            "classification_dimension": hicp_classification_dimension,
            "all_items_code": hicp_all_items_code,
            "all_items_label": category_codes(hicp_probe, hicp_classification_dimension)[hicp_all_items_code],
            "unit_label": category_codes(hicp_probe, "unit")["RCH_A"],
        },
        "consumer_confidence": {
            dimension: category_codes(confidence_probe, dimension)
            for dimension in ("indic", "s_adj", "unit")
        },
    }
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "api_base": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data",
        "period": {"start": START, "end": END},
        "countries": COUNTRIES,
        "schema_probe_urls": probe_urls,
        "schema_evidence": schema_evidence,
        "sources": manifest_sources,
    }
    (RAW_DIR / "download_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Downloaded 3 official extracts to {RAW_DIR}")


if __name__ == "__main__":
    main()
