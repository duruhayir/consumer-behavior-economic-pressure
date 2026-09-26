"""Validate the public repository handoff without changing analytical outputs."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUTPUTS = ROOT / "outputs"
TABLES = OUTPUTS / "tables"
TABLEAU = ROOT / "tableau"
MASTER = DATA / "consumer_behavior_eu_2015_2025.csv"
EXPECTED_MASTER_SHA256 = "c6cdd7ca0838af17732bf3539c372df93cadde8fd0ee8289e9934a02c71ab4e7"

checks: list[dict[str, str]] = []


def record(name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


required = [
    ROOT / "README.md",
    ROOT / "DATA_SOURCES.md",
    ROOT / "requirements.txt",
    ROOT / ".gitignore",
    MASTER,
    DATA / "tableau_analysis_data.csv",
    DATA / "tableau_retail_long.csv",
    ROOT / "notebooks" / "02_eda_and_statistical_analysis.ipynb",
    ROOT / "notebooks" / "02_5_panel_robustness.ipynb",
    OUTPUTS / "FINAL_REPORT.md",
    OUTPUTS / "PORTFOLIO_SUMMARY.md",
    OUTPUTS / "CV_PROJECT_ENTRY.md",
    OUTPUTS / "INTERVIEW_EXPLANATION.md",
    OUTPUTS / "AUTHOR_CHECKLIST.md",
    TABLEAU / "consumer_behavior_under_economic_pressure.twb",
    TABLEAU / "consumer_behavior_under_economic_pressure.twbx",
]
missing = [path.relative_to(ROOT).as_posix() for path in required if not path.exists()]
record("required_files", not missing, f"missing={missing}")

master_digest = sha256(MASTER)
record("master_unchanged", master_digest == EXPECTED_MASTER_SHA256, master_digest)

master = pd.read_csv(MASTER, parse_dates=["date"])
record(
    "master_grid",
    len(master) == 396 and not master.duplicated(["country_code", "date"]).any(),
    f"rows={len(master)}, duplicates={master.duplicated(['country_code', 'date']).sum()}",
)

wide = pd.read_csv(DATA / "tableau_analysis_data.csv", parse_dates=["date"])
long_data = pd.read_csv(DATA / "tableau_retail_long.csv", parse_dates=["date"])
record(
    "tableau_wide_grid",
    len(wide) == 396 and not wide.duplicated(["country_code", "date"]).any(),
    f"rows={len(wide)}, duplicates={wide.duplicated(['country_code', 'date']).sum()}",
)
record(
    "tableau_long_grid",
    len(long_data) == 1188
    and not long_data.duplicated(["country_code", "date", "retail_category"]).any()
    and long_data["retail_category"].value_counts().eq(396).all(),
    f"rows={len(long_data)}, categories={long_data['retail_category'].value_counts().to_dict()}",
)

wide_sorted = wide.sort_values(["country_code", "date"]).reset_index(drop=True)
master_sorted = master.sort_values(["country_code", "date"]).reset_index(drop=True)
wide_map = {
    "country_code": "country_code",
    "country": "country",
    "date": "date",
    "inflation_yoy": "inflation_yoy",
    "consumer_confidence": "consumer_confidence",
    "retail_total_yoy": "retail_total_yoy",
    "retail_food_yoy": "retail_food_yoy",
    "retail_nonfood_yoy": "retail_nonfood_yoy",
}
wide_ok = True
for wide_column, master_column in wide_map.items():
    if pd.api.types.is_numeric_dtype(wide_sorted[wide_column]):
        wide_ok &= np.allclose(
            wide_sorted[wide_column], master_sorted[master_column], equal_nan=True, atol=1e-12
        )
    else:
        wide_ok &= wide_sorted[wide_column].equals(master_sorted[master_column])
record("tableau_wide_matches_master", wide_ok, "all selected columns reconciled")

category_map = {
    "Total": "retail_total_yoy",
    "Food": "retail_food_yoy",
    "Non-food": "retail_nonfood_yoy",
}
long_ok = True
for category, source_column in category_map.items():
    subset = long_data.loc[long_data["retail_category"].eq(category)].merge(
        wide[["country_code", "date", source_column]], on=["country_code", "date"], how="left"
    )
    long_ok &= np.allclose(
        subset["retail_growth_yoy"], subset[source_column], equal_nan=True, atol=1e-12
    )
record("tableau_long_matches_wide", long_ok, "all category values reconciled")

public_chunks: list[tuple[str, str]] = []
for pattern in ("*.md", "*.py"):
    for path in ROOT.rglob(pattern):
        if any(part in {".python", ".matplotlib", "__pycache__"} for part in path.parts):
            continue
        public_chunks.append((path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")))
for path in ROOT.glob("*.txt"):
    public_chunks.append((path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")))
twb_path = TABLEAU / "consumer_behavior_under_economic_pressure.twb"
twb_text = twb_path.read_text(encoding="utf-8")
public_chunks.append((twb_path.relative_to(ROOT).as_posix(), twb_text))
for notebook_path in (ROOT / "notebooks").glob("*.ipynb"):
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
    public_chunks.append((notebook_path.relative_to(ROOT).as_posix(), source))

private_tokens = ["C:" + "/Users", "C:" + "\\Users", "One" + "Drive", "Masa" + "üstü", "istinye " + "üniversitesi"]
private_pattern = re.compile("|".join(re.escape(token) for token in private_tokens), re.I)
private_hits = sorted({name for name, text in public_chunks if private_pattern.search(text)})
record("no_private_local_paths", not private_hits, f"files={private_hits}")

credential_pattern = re.compile(
    r"(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"\s]{8,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----",
    re.I,
)
credential_hits = sorted({name for name, text in public_chunks if credential_pattern.search(text)})
record("no_obvious_credentials", not credential_hits, f"files={credential_hits}")

readme = (ROOT / "README.md").read_text(encoding="utf-8")
image_links = re.findall(r"!\[[^]]*\]\(([^)]+)\)", readme)
broken_images = [link for link in image_links if not (ROOT / link).exists()]
record("readme_image_links", len(image_links) == 6 and not broken_images, f"links={len(image_links)}, broken={broken_images}")
local_links = [
    link
    for link in re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", readme)
    if not re.match(r"(?:https?://|#)", link)
]
broken_links = [link for link in local_links if not (ROOT / link).exists()]
record("readme_local_links", not broken_links, f"links={len(local_links)}, broken={broken_links}")

headline_values = [
    "-0.786", "-0.657", "-1.179", "-0.134", "0.986", "0.182", "1.790",
    "0.258", "0.032", "0.485", "0.195", "0.309", "-0.025", "-0.033",
    "-0.046", "-0.624",
]
core_documents = [ROOT / "README.md", OUTPUTS / "FINAL_REPORT.md", OUTPUTS / "PHASE2_5_ROBUSTNESS.md"]
headline_missing = {
    path.name: [value for value in headline_values if value not in path.read_text(encoding="utf-8")]
    for path in core_documents
}
record(
    "headline_numbers_in_core_documents",
    all(not values for values in headline_missing.values()),
    str(headline_missing),
)

panel = pd.read_csv(TABLES / "regression_panel_robustness.csv")
model_b = panel.loc[panel["model"].eq("Model B: entity + time FE")]
expected_model_b = {
    ("retail_food_yoy", "inflation_yoy"): (-0.657, -1.179, -0.134),
    ("retail_total_yoy", "inflation_yoy"): (-0.624, -1.126, -0.121),
    ("retail_total_yoy", "consumer_confidence"): (-0.025, -0.207, 0.156),
    ("retail_nonfood_yoy", "consumer_confidence"): (-0.033, -0.316, 0.250),
}
source_numbers_ok = True
for (outcome, term), expected in expected_model_b.items():
    row = model_b.loc[model_b["outcome"].eq(outcome) & model_b["term"].eq(term)].iloc[0]
    observed = (row["coefficient"], row["ci_lower_95"], row["ci_upper_95"])
    source_numbers_ok &= np.allclose(observed, expected, atol=0.0005)
record("headline_numbers_match_tables", source_numbers_ok, "robust estimates and intervals reconciled")

record(
    "tableau_relative_connections",
    "C:/" not in twb_text
    and "C:\\" not in twb_text
    and "directory='../data/processed'" in twb_text
    and "directory='../outputs/tables'" in twb_text,
    "unpackaged workbook uses repository-relative CSV connections",
)
dashboard_names = ["Consumer Behavior Under Economic Pressure", "Category &amp; Robustness Analysis"]
record(
    "tableau_dashboards_documented",
    all(name in twb_text for name in dashboard_names),
    "two dashboard titles found in workbook",
)
record(
    "tableau_sources",
    "tableau_retail_long.csv" in twb_text and "executive_results.csv" in twb_text,
    "validated long extract and executive results referenced",
)

twbx_path = TABLEAU / "consumer_behavior_under_economic_pressure.twbx"
package_ok = False
package_detail = "package unavailable"
if twbx_path.exists():
    with zipfile.ZipFile(twbx_path) as archive:
        names = archive.namelist()
        packaged_long = next((name for name in names if name.endswith("tableau_retail_long.csv")), None)
        packaged_results = next((name for name in names if name.endswith("executive_results.csv")), None)
        package_ok = bool(packaged_long and packaged_results)
        if package_ok:
            package_ok &= hashlib.sha256(archive.read(packaged_long)).hexdigest() == sha256(
                DATA / "tableau_retail_long.csv"
            )
            package_ok &= hashlib.sha256(archive.read(packaged_results)).hexdigest() == sha256(
                TABLES / "executive_results.csv"
            )
        package_detail = f"members={names}"
record("tableau_package_matches_project_data", package_ok, package_detail)

syntax_errors: list[str] = []
for path in sorted((ROOT / "src").glob("*.py")):
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        syntax_errors.append(f"{path.name}:{exc.lineno}:{exc.msg}")
record("python_syntax", not syntax_errors, f"errors={syntax_errors}")

ignored_parts = {".python", ".matplotlib", "__pycache__", ".git"}
hash_groups: defaultdict[str, list[str]] = defaultdict(list)
for path in ROOT.rglob("*"):
    if not path.is_file() or any(part in ignored_parts for part in path.parts):
        continue
    hash_groups[sha256(path)].append(path.relative_to(ROOT).as_posix())
duplicates = [paths for paths in hash_groups.values() if len(paths) > 1]
record("no_unexpected_duplicate_files", not duplicates, f"duplicates={duplicates}")

allowed_top_level = {
    ".gitignore", "README.md", "DATA_SOURCES.md", "requirements.txt",
    "data", "notebooks", "outputs", "src", "tableau", ".python", ".matplotlib",
}
unexpected_top = sorted(path.name for path in ROOT.iterdir() if path.name not in allowed_top_level)
record("clean_top_level", not unexpected_top, f"unexpected={unexpected_top}")

gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
required_ignore_tokens = [
    "__pycache__/", "*.py[cod]", ".python/", ".matplotlib/", ".ipynb_checkpoints/",
    ".DS_Store", "Thumbs.db", ".vscode/", ".idea/", "*.tmp", "*.log", "*.twb~",
]
missing_ignore = [token for token in required_ignore_tokens if token not in gitignore]
record("gitignore_common_artifacts", not missing_ignore, f"missing={missing_ignore}")

results = pd.DataFrame(checks)
failures = results.loc[results["status"].eq("FAIL")]
status = "PASS" if failures.empty else "FAIL"
lines = [
    "# Final Repository Validation",
    "",
    f"**Overall status: {status}**",
    "",
    f"- Checks run: {len(results)}",
    f"- Passed: {(results['status'] == 'PASS').sum()}",
    f"- Failed: {len(failures)}",
    "",
    "| Check | Status | Detail |",
    "|---|---|---|",
]
for row in results.itertuples(index=False):
    detail = str(row.detail).replace("|", "\\|").replace("\n", " ")
    lines.append(f"| {row.check} | {row.status} | {detail} |")
lines.extend(
    [
        "",
        "The master file was checked by SHA-256 and was not rewritten. The missing Phase 1 notebook is intentional: data collection, preparation and validation remain reproducible through the source scripts, raw extracts, manifest and saved validation outputs.",
        "",
    ]
)
(OUTPUTS / "FINAL_REPOSITORY_VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")

print(results.to_string(index=False))
if not failures.empty:
    raise SystemExit(f"Final repository validation failed: {failures['check'].tolist()}")
print(f"All {len(results)} final repository checks passed.")
