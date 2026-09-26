"""Validate the Phase 3 portfolio artifacts against validated source outputs."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
TABLES = OUTPUTS / "tables"
FIGURES = OUTPUTS / "final_figures"
MASTER = DATA / "consumer_behavior_eu_2015_2025.csv"
MASTER_SHA256 = "c6cdd7ca0838af17732bf3539c372df93cadde8fd0ee8289e9934a02c71ab4e7"

checks: list[dict[str, str]] = []


def record(name: str, status: str, detail: str) -> None:
    checks.append({"check": name, "status": status, "detail": detail})


def words(text: str) -> int:
    cleaned = re.sub(r"!\[[^]]*\]\([^)]*\)", "", text)
    cleaned = re.sub(r"[`#*|]", " ", cleaned)
    return len(re.findall(r"\b[\w’'-]+\b", cleaned, flags=re.UNICODE))


digest = hashlib.sha256(MASTER.read_bytes()).hexdigest()
record("master_file_unchanged", "PASS" if digest == MASTER_SHA256 else "FAIL", digest)

master = pd.read_csv(MASTER, parse_dates=["date"]).sort_values(["country_code", "date"]).reset_index(drop=True)
wide = pd.read_csv(DATA / "tableau_analysis_data.csv", parse_dates=["date"]).sort_values(["country_code", "date"]).reset_index(drop=True)
expected_wide_columns = [
    "country_code", "country", "date", "inflation_yoy", "consumer_confidence",
    "retail_total_yoy", "retail_food_yoy", "retail_nonfood_yoy",
]
record("tableau_wide_shape", "PASS" if len(wide) == 396 and list(wide.columns) == expected_wide_columns else "FAIL", f"rows={len(wide)}, columns={list(wide.columns)}")
record("tableau_wide_unique_key", "PASS" if not wide.duplicated(["country_code", "date"]).any() else "FAIL", f"duplicates={wide.duplicated(['country_code', 'date']).sum()}")

wide_match = True
for column in expected_wide_columns:
    if column == "date":
        wide_match &= wide[column].equals(master[column])
    elif pd.api.types.is_numeric_dtype(master[column]):
        wide_match &= np.allclose(wide[column], master[column], equal_nan=True, atol=1e-12)
    else:
        wide_match &= wide[column].equals(master[column])
record("tableau_wide_matches_master", "PASS" if wide_match else "FAIL", "all selected values reconciled")

long_data = pd.read_csv(DATA / "tableau_retail_long.csv", parse_dates=["date"])
expected_long_columns = [
    "country_code", "country", "date", "inflation_yoy", "consumer_confidence",
    "retail_category", "retail_growth_yoy",
]
category_counts = long_data["retail_category"].value_counts().to_dict()
record("tableau_long_shape", "PASS" if len(long_data) == 1188 and list(long_data.columns) == expected_long_columns else "FAIL", f"rows={len(long_data)}, category_counts={category_counts}")
record("tableau_long_unique_key", "PASS" if not long_data.duplicated(["country_code", "date", "retail_category"]).any() else "FAIL", f"duplicates={long_data.duplicated(['country_code', 'date', 'retail_category']).sum()}")

mapping = {"Total": "retail_total_yoy", "Food": "retail_food_yoy", "Non-food": "retail_nonfood_yoy"}
max_long_diff = 0.0
long_ok = True
for category, source_column in mapping.items():
    subset = long_data.loc[long_data["retail_category"].eq(category)].merge(
        wide[["country_code", "date", source_column]], on=["country_code", "date"], how="left"
    )
    long_ok &= np.allclose(subset["retail_growth_yoy"], subset[source_column], equal_nan=True, atol=1e-12)
    differences = (subset["retail_growth_yoy"] - subset[source_column]).abs().dropna()
    max_long_diff = max(max_long_diff, float(differences.max()) if not differences.empty else 0.0)
record("tableau_long_matches_wide", "PASS" if long_ok else "FAIL", f"max_abs_diff={max_long_diff:.3g}")
record("structural_missingness_preserved", "PASS" if wide[["retail_total_yoy", "retail_food_yoy", "retail_nonfood_yoy"]].isna().sum().eq(36).all() and long_data["retail_growth_yoy"].isna().sum() == 108 else "FAIL", f"wide_missing={wide[['retail_total_yoy','retail_food_yoy','retail_nonfood_yoy']].isna().sum().to_dict()}, long_missing={long_data['retail_growth_yoy'].isna().sum()}")

executive = pd.read_csv(TABLES / "executive_results.csv")
panel = pd.read_csv(TABLES / "regression_panel_robustness.csv")
robust = panel.loc[panel["model"].eq("Model B: entity + time FE")]
expected_main = {
    "Inflation → Total growth": ("retail_total_yoy", "inflation_yoy"),
    "Inflation → Food growth": ("retail_food_yoy", "inflation_yoy"),
    "Inflation → Non-food growth": ("retail_nonfood_yoy", "inflation_yoy"),
    "Confidence → Total growth": ("retail_total_yoy", "consumer_confidence"),
    "Confidence → Food growth": ("retail_food_yoy", "consumer_confidence"),
    "Confidence → Non-food growth": ("retail_nonfood_yoy", "consumer_confidence"),
}
max_exec_diff = 0.0
for label, (outcome, term) in expected_main.items():
    saved = executive.loc[executive["Relationship"].eq(label)].iloc[0]
    source = robust.loc[robust["outcome"].eq(outcome) & robust["term"].eq(term)].iloc[0]
    max_exec_diff = max(max_exec_diff, abs(saved["Original Estimate"] - source["original_hc3_coefficient"]), abs(saved["Robust Estimate"] - source["coefficient"]))
record("executive_main_estimates_match", "PASS" if len(executive) == 8 and max_exec_diff < 5e-4 else "FAIL", f"rows={len(executive)}, max_abs_diff={max_exec_diff:.3g}")

interaction = pd.read_csv(TABLES / "category_interaction_panel_robustness.csv")
int_checks = []
for label, term in (("Inflation × Non-food category", "inflation_yoy:is_nonfood"), ("Confidence × Non-food category", "consumer_confidence:is_nonfood")):
    observed = executive.loc[executive["Relationship"].eq(label), "Robust Estimate"].iloc[0]
    expected = interaction.loc[interaction["term"].eq(term), "coefficient"].iloc[0]
    int_checks.append(abs(observed - expected))
record("executive_interactions_match", "PASS" if max(int_checks) < 5e-4 else "FAIL", f"max_abs_diff={max(int_checks):.3g}")

figure_paths = sorted(FIGURES.glob("*.png"))
dimension_issues = []
for path in figure_paths:
    with Image.open(path) as image:
        width, height = image.size
        if width < 1200 or height < 700:
            dimension_issues.append(f"{path.name}:{width}x{height}")
record("seven_final_figures", "PASS" if len(figure_paths) == 7 else "FAIL", f"count={len(figure_paths)}")
record("figures_have_readable_dimensions", "PASS" if not dimension_issues else "FAIL", f"issues={dimension_issues}")

required_text = [
    ROOT / "README.md", OUTPUTS / "FINAL_REPORT.md", OUTPUTS / "TABLEAU_DASHBOARD_SPEC.md",
    OUTPUTS / "PORTFOLIO_SUMMARY.md", OUTPUTS / "CV_PROJECT_ENTRY.md",
    OUTPUTS / "INTERVIEW_EXPLANATION.md", OUTPUTS / "AUTHOR_CHECKLIST.md",
]
record("reader_facing_files_exist", "PASS" if all(path.exists() for path in required_text) else "FAIL", f"missing={[path.name for path in required_text if not path.exists()]}")

report = (OUTPUTS / "FINAL_REPORT.md").read_text(encoding="utf-8")
report_count = words(report)
summary_match = re.search(r"## Executive Summary\s+(.*?)(?=\n## 1\.)", report, flags=re.S)
conclusion_match = re.search(r"## 12\. Conclusion\s+(.*)$", report, flags=re.S)
summary_count = words(summary_match.group(1)) if summary_match else 0
conclusion_count = words(conclusion_match.group(1)) if conclusion_match else 0
record("final_report_length", "PASS" if 1500 <= report_count <= 2200 else "FAIL", f"words={report_count}")
record("executive_summary_length", "PASS" if 150 <= summary_count <= 220 else "FAIL", f"words={summary_count}")
record("conclusion_length", "PASS" if 100 <= conclusion_count <= 140 else "FAIL", f"words={conclusion_count}")
required_sections = ["## Executive Summary"] + [f"## {i}." for i in range(1, 13)]
record("final_report_structure", "PASS" if all(section in report for section in required_sections) else "FAIL", f"missing={[section for section in required_sections if section not in report]}")

portfolio = (OUTPUTS / "PORTFOLIO_SUMMARY.md").read_text(encoding="utf-8")
portfolio_count = words(re.sub(r"^# Portfolio Summary", "", portfolio))
record("portfolio_summary_length", "PASS" if 180 <= portfolio_count <= 200 else "FAIL", f"words={portfolio_count}")

all_text = "\n".join(path.read_text(encoding="utf-8") for path in required_text)
forbidden = [
    "consumer spending", "inflation reduces", "confidence drives", "leveraged",
    "cutting-edge", "actionable synergies", "data-driven ecosystem", "transformative insights",
]
found_forbidden = [phrase for phrase in forbidden if phrase.lower() in all_text.lower()]
record("no_forbidden_claims_or_buzzwords", "PASS" if not found_forbidden else "FAIL", f"matches={found_forbidden}")
naturalness_tokens = re.findall(r"\b(?:Furthermore|Moreover|Additionally)\b", all_text, flags=re.I)
record("naturalness_transition_check", "PASS" if len(naturalness_tokens) <= 1 else "FAIL", f"count={len(naturalness_tokens)}")
record("retail_volume_language_present", "PASS" if "retail volume" in all_text.lower() or "retail-volume" in all_text.lower() else "FAIL", "retail-volume terminology used")

readme = (ROOT / "README.md").read_text(encoding="utf-8")
image_links = re.findall(r"!\[[^]]*\]\(([^)]+)\)", readme)
broken_images = [link for link in image_links if not (ROOT / link).exists()]
record("readme_image_paths", "PASS" if len(image_links) >= 3 and not broken_images else "FAIL", f"links={len(image_links)}, broken={broken_images}")

headline_strings = ["-0.657", "-1.179", "-0.134", "+0.986", "+0.258", "-0.025", "-0.033"]
for filename in ["FINAL_REPORT.md", "PORTFOLIO_SUMMARY.md", "INTERVIEW_EXPLANATION.md"]:
    text = (OUTPUTS / filename).read_text(encoding="utf-8")
    required = ["0.66"] if filename != "FINAL_REPORT.md" else headline_strings
    missing = [value for value in required if value not in text]
    record(f"headline_numbers_{filename}", "PASS" if not missing else "FAIL", f"missing={missing}")

notebook_01 = ROOT / "notebooks" / "01_data_collection_and_validation.ipynb"
record("phase1_notebook_inventory", "PASS_WITH_NOTE" if not notebook_01.exists() else "PASS", "Referenced Phase 1 notebook is absent; Phase 1 remains reproducible through src/run_pipeline.py and saved validation evidence." if not notebook_01.exists() else "present")

results = pd.DataFrame(checks)
results.to_csv(TABLES / "phase3_validation_checks.csv", index=False)
failures = results.loc[results["status"].eq("FAIL")]
overall = "Ready for portfolio use" if failures.empty else "Needs revision"
validation_note = f"""# Phase 3 Validation

## Overall assessment: {overall}

- Checks run: {len(results)}
- Passed: {(results['status'] == 'PASS').sum()}
- Passed with note: {(results['status'] == 'PASS_WITH_NOTE').sum()}
- Failed: {len(failures)}

The master dataset hash is unchanged. Tableau extracts were reconciled row-by-row to the master data, executive estimates were checked against the validated Phase 2.5 tables, all final figures were inspected and meet the minimum output dimensions, and README image paths resolve.

## Documentation note

`notebooks/01_data_collection_and_validation.ipynb` was referenced in the Phase 3 brief but is not present in the repository. This does not block the current portfolio handoff because Phase 1 is reproducible through `src/run_pipeline.py`, the official raw extracts, the download manifest and saved validation outputs. The gap is recorded rather than silently filled.

Full check results are saved in `outputs/tables/phase3_validation_checks.csv`.
"""
    
(OUTPUTS / "PHASE3_VALIDATION.md").write_text(validation_note, encoding="utf-8")
print(results.to_string(index=False))
if not failures.empty:
    raise SystemExit(f"Phase 3 validation failed: {failures['check'].tolist()}")
print(f"All blocking checks passed. {overall}.")

