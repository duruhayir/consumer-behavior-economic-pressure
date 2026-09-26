"""Build Phase 3 presentation artifacts from the validated Phase 1-2.5 outputs.

This script does not refit models or modify the master dataset. It creates the
curated figure set, executive results table, and Tableau-ready extracts.
"""

from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MPL_CONFIG = _PROJECT_ROOT / ".matplotlib"
_MPL_CONFIG.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CONFIG))

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "data" / "processed" / "consumer_behavior_eu_2015_2025.csv"
TABLES = ROOT / "outputs" / "tables"
FIGURES = ROOT / "outputs" / "final_figures"

COUNTRY_ORDER = ["NL", "DE", "FR"]
COUNTRY_NAMES = {"NL": "Netherlands", "DE": "Germany", "FR": "France"}
COUNTRY_COLORS = {"NL": "#256D85", "DE": "#D6A21C", "FR": "#CC5A7A"}
COUNTRY_MARKERS = {"NL": "o", "DE": "s", "FR": "^"}
COUNTRY_LINES = {"NL": "-", "DE": "--", "FR": "-."}
FOOD_COLOR = "#73843C"
NONFOOD_COLOR = "#D66F2C"
INK = "#25313C"
GRID = "#DCE2E7"
NOTE = "Source: Eurostat / European Commission; author calculations. Retail measures are real retail-sales volume proxies."


def set_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#697684",
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "text.color": INK,
            "xtick.color": INK,
            "ytick.color": INK,
            "font.family": "DejaVu Sans",
            "font.size": 10.5,
            "axes.titlesize": 15,
            "axes.labelsize": 11,
            "legend.fontsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def finish(fig: plt.Figure, filename: str, source_note: str = NOTE) -> None:
    fig.text(0.01, 0.012, source_note, ha="left", va="bottom", fontsize=8.5, color="#64707C")
    fig.savefig(FIGURES / filename, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def add_month_axis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.axhline(0, color="#3D4650", linewidth=0.8)


def create_tableau_extracts(data: pd.DataFrame) -> None:
    columns = [
        "country_code",
        "country",
        "date",
        "inflation_yoy",
        "consumer_confidence",
        "retail_total_yoy",
        "retail_food_yoy",
        "retail_nonfood_yoy",
    ]
    wide = data[columns].sort_values(["country_code", "date"])
    wide.to_csv(ROOT / "data" / "processed" / "tableau_analysis_data.csv", index=False, date_format="%Y-%m-%d")

    long_parts = []
    for category, variable in (
        ("Total", "retail_total_yoy"),
        ("Food", "retail_food_yoy"),
        ("Non-food", "retail_nonfood_yoy"),
    ):
        part = data[["country_code", "country", "date", "inflation_yoy", "consumer_confidence", variable]].rename(
            columns={variable: "retail_growth_yoy"}
        )
        part["retail_category"] = category
        long_parts.append(part)
    long_data = pd.concat(long_parts, ignore_index=True)
    long_data["retail_category"] = pd.Categorical(
        long_data["retail_category"], categories=["Total", "Food", "Non-food"], ordered=True
    )
    long_data = long_data.sort_values(["country_code", "date", "retail_category"])
    long_data = long_data[
        [
            "country_code",
            "country",
            "date",
            "inflation_yoy",
            "consumer_confidence",
            "retail_category",
            "retail_growth_yoy",
        ]
    ]
    long_data.to_csv(ROOT / "data" / "processed" / "tableau_retail_long.csv", index=False, date_format="%Y-%m-%d")


def create_executive_table() -> pd.DataFrame:
    panel = pd.read_csv(TABLES / "regression_panel_robustness.csv")
    robust = panel.loc[panel["model"].eq("Model B: entity + time FE")].copy()
    interaction = pd.read_csv(TABLES / "category_interaction_panel_robustness.csv")

    labels = {
        ("retail_total_yoy", "inflation_yoy"): "Inflation → Total growth",
        ("retail_food_yoy", "inflation_yoy"): "Inflation → Food growth",
        ("retail_nonfood_yoy", "inflation_yoy"): "Inflation → Non-food growth",
        ("retail_total_yoy", "consumer_confidence"): "Confidence → Total growth",
        ("retail_food_yoy", "consumer_confidence"): "Confidence → Food growth",
        ("retail_nonfood_yoy", "consumer_confidence"): "Confidence → Non-food growth",
    }
    interpretations = {
        ("retail_total_yoy", "inflation_yoy"): "The estimate became more negative after common monthly effects were included.",
        ("retail_food_yoy", "inflation_yoy"): "Higher inflation was consistently associated with weaker food retail-volume growth.",
        ("retail_nonfood_yoy", "inflation_yoy"): "The direction changed and the robust interval included zero.",
        ("retail_total_yoy", "consumer_confidence"): "The original positive relationship moved close to zero with month effects.",
        ("retail_food_yoy", "consumer_confidence"): "The estimate remained close to zero in both specifications.",
        ("retail_nonfood_yoy", "consumer_confidence"): "The original positive relationship moved close to zero with month effects.",
    }
    statuses = {
        ("retail_total_yoy", "inflation_yoy"): "Specification-sensitive",
        ("retail_food_yoy", "inflation_yoy"): "Robust",
        ("retail_nonfood_yoy", "inflation_yoy"): "Specification-sensitive",
        ("retail_total_yoy", "consumer_confidence"): "Specification-sensitive",
        ("retail_food_yoy", "consumer_confidence"): "Stable near zero",
        ("retail_nonfood_yoy", "consumer_confidence"): "Specification-sensitive",
    }

    rows = []
    for key, label in labels.items():
        outcome, term = key
        row = robust.loc[robust["outcome"].eq(outcome) & robust["term"].eq(term)].iloc[0]
        rows.append(
            {
                "Relationship": label,
                "Original Estimate": row["original_hc3_coefficient"],
                "Robust Estimate": row["coefficient"],
                "95% CI": f"[{row['ci_lower_95']:.3f}, {row['ci_upper_95']:.3f}]",
                "Interpretation": interpretations[key],
                "Robustness Status": statuses[key],
            }
        )

    for term, label, interpretation in (
        (
            "inflation_yoy:is_nonfood",
            "Inflation × Non-food category",
            "Food had the more negative inflation association.",
        ),
        (
            "consumer_confidence:is_nonfood",
            "Confidence × Non-food category",
            "Non-food had the more positive confidence association relative to food.",
        ),
    ):
        row = interaction.loc[interaction["term"].eq(term)].iloc[0]
        rows.append(
            {
                "Relationship": label,
                "Original Estimate": row["coefficient"],
                "Robust Estimate": row["coefficient"],
                "95% CI": f"[{row['ci_lower_95']:.3f}, {row['ci_upper_95']:.3f}]",
                "Interpretation": interpretation,
                "Robustness Status": "Robust category difference",
            }
        )

    result = pd.DataFrame(rows)
    result.to_csv(TABLES / "executive_results.csv", index=False, float_format="%.3f")
    headers = list(result.columns)
    lines = [
        "# Executive results",
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for _, row in result.iterrows():
        values = []
        for header in headers:
            value = row[header]
            if header in {"Original Estimate", "Robust Estimate"}:
                value = f"{float(value):.3f}"
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    markdown = "\n".join(lines) + "\n"
    (TABLES / "executive_results.md").write_text(markdown, encoding="utf-8")
    return result


def figure_1_inflation(data: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.3))
    for code in COUNTRY_ORDER:
        part = data.loc[data["country_code"].eq(code)]
        ax.plot(part["date"], part["inflation_yoy"], color=COUNTRY_COLORS[code], linestyle=COUNTRY_LINES[code], linewidth=2.0, label=COUNTRY_NAMES[code])
    ax.set_title("Headline HICP inflation by country", loc="left", fontweight="bold", pad=28)
    ax.text(0, 1.015, "Annual rate of change, January 2015–December 2025", transform=ax.transAxes, color="#64707C")
    ax.set_ylabel("Annual inflation rate (%)")
    ax.set_xlabel("Month")
    add_month_axis(ax)
    ax.legend(ncol=3, loc="upper left", frameon=False)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    finish(fig, "01_inflation_over_time.png")


def figure_2_total_growth(data: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11.5, 6.3))
    for code in COUNTRY_ORDER:
        part = data.loc[data["country_code"].eq(code)]
        ax.plot(part["date"], part["retail_total_yoy"], color=COUNTRY_COLORS[code], linestyle=COUNTRY_LINES[code], linewidth=1.9, label=COUNTRY_NAMES[code])
    ax.axvspan(pd.Timestamp("2020-03-01"), pd.Timestamp("2021-12-01"), color="#7B8792", alpha=0.10, linewidth=0)
    ax.text(pd.Timestamp("2020-04-01"), 41, "COVID/reopening period", color="#64707C", fontsize=9)
    ax.set_title("Total retail-sales volume growth by country", loc="left", fontweight="bold", pad=28)
    ax.text(0, 1.015, "Year-on-year change, January 2016–December 2025", transform=ax.transAxes, color="#64707C")
    ax.set_ylabel("Retail-volume growth (% YoY)")
    ax.set_xlabel("Month")
    add_month_axis(ax)
    ax.legend(ncol=3, loc="upper left", frameon=False)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    finish(fig, "02_total_retail_growth_over_time.png")


def figure_3_categories(data: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11.5, 10.5), sharex=True, sharey=True)
    for ax, code in zip(axes, COUNTRY_ORDER):
        part = data.loc[data["country_code"].eq(code)]
        ax.plot(part["date"], part["retail_food_yoy"], color=FOOD_COLOR, linewidth=1.7, label="Food")
        ax.plot(part["date"], part["retail_nonfood_yoy"], color=NONFOOD_COLOR, linestyle="--", linewidth=1.7, label="Non-food excluding automotive fuel")
        ax.axvspan(pd.Timestamp("2020-03-01"), pd.Timestamp("2021-12-01"), color="#7B8792", alpha=0.09, linewidth=0)
        ax.set_title(COUNTRY_NAMES[code], loc="left", fontsize=12, fontweight="bold")
        ax.set_ylabel("Growth (% YoY)")
        add_month_axis(ax)
    axes[0].legend(ncol=2, loc="upper left", frameon=False)
    axes[-1].set_xlabel("Month")
    fig.suptitle("Food and non-food retail-volume growth", x=0.08, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.08, 0.955, "Common scale across countries, January 2016–December 2025", color="#64707C")
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    finish(fig, "03_food_nonfood_growth_by_country.png")


def scatter_with_fit(ax: plt.Axes, data: pd.DataFrame, x: str, y: str) -> None:
    for code in COUNTRY_ORDER:
        part = data.loc[data["country_code"].eq(code), [x, y]].dropna()
        ax.scatter(part[x], part[y], s=26, alpha=0.50, color=COUNTRY_COLORS[code], marker=COUNTRY_MARKERS[code], edgecolor="white", linewidth=0.35, label=COUNTRY_NAMES[code])
    pooled = data[[x, y]].dropna()
    slope, intercept = np.polyfit(pooled[x], pooled[y], 1)
    grid = np.linspace(pooled[x].min(), pooled[x].max(), 200)
    ax.plot(grid, intercept + slope * grid, color=INK, linestyle="--", linewidth=1.8, label="Pooled descriptive fit")
    ax.axhline(0, color="#3D4650", linewidth=0.8)
    ax.grid(color=GRID, linewidth=0.75)


def figure_4_inflation_food(data: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.6))
    scatter_with_fit(ax, data, "inflation_yoy", "retail_food_yoy")
    ax.set_title("Higher inflation was associated with weaker food retail growth", loc="left", fontweight="bold", pad=28)
    ax.text(0, 1.015, "Descriptive country-month relationship; 360 observations, 2016–2025", transform=ax.transAxes, color="#64707C")
    ax.set_xlabel("Annual HICP inflation rate (%)")
    ax.set_ylabel("Food retail-volume growth (% YoY)")
    ax.legend(ncol=2, loc="upper right", frameon=False)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    finish(fig, "04_inflation_food_growth_association.png")


def figure_5_confidence_nonfood(data: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.6))
    scatter_with_fit(ax, data, "consumer_confidence", "retail_nonfood_yoy")
    ax.set_title("Consumer confidence and non-food retail growth", loc="left", fontweight="bold", pad=28)
    ax.text(0, 1.015, "Descriptive relationship; it weakened after common-month controls", transform=ax.transAxes, color="#64707C")
    ax.set_xlabel("Consumer Confidence Indicator (balance)")
    ax.set_ylabel("Non-food retail-volume growth (% YoY)")
    ax.legend(ncol=2, loc="upper right", frameon=False)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    finish(fig, "05_confidence_nonfood_growth_descriptive.png")


def figure_6_robustness() -> None:
    original = pd.read_csv(TABLES / "regression_pooled.csv")
    robust = pd.read_csv(TABLES / "regression_panel_robustness.csv")
    robust = robust.loc[robust["model"].eq("Model B: entity + time FE")]
    outcomes = ["retail_total_yoy", "retail_food_yoy", "retail_nonfood_yoy"]
    outcome_labels = ["Total", "Food", "Non-food"]
    terms = [("inflation_yoy", "Inflation coefficient"), ("consumer_confidence", "Confidence coefficient")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 6.6), sharey=True)
    y = np.arange(len(outcomes))[::-1]
    for ax, (term, title) in zip(axes, terms):
        old = original.loc[original["term"].eq(term)].set_index("outcome").loc[outcomes]
        new = robust.loc[robust["term"].eq(term)].set_index("outcome").loc[outcomes]
        ax.errorbar(old["coefficient"], y + 0.10, xerr=[old["coefficient"] - old["ci_lower_95"], old["ci_upper_95"] - old["coefficient"]], fmt="o", mfc="white", mec="#697684", ecolor="#697684", capsize=3, label="Original country FE (HC3)")
        ax.errorbar(new["coefficient"], y - 0.10, xerr=[new["coefficient"] - new["ci_lower_95"], new["ci_upper_95"] - new["coefficient"]], fmt="o", color="#256D85", ecolor="#256D85", capsize=3, label="Country + month FE (DK)")
        ax.axvline(0, color="#3D4650", linewidth=1.0)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold")
        ax.set_xlabel("Coefficient with 95% CI")
        ax.set_yticks(y, outcome_labels)
    handles = [
        Line2D([0], [0], marker="o", color="#697684", markerfacecolor="white", linestyle="None", label="Original country FE (HC3)"),
        Line2D([0], [0], marker="o", color="#256D85", linestyle="None", label="Country + month FE (Driscoll–Kraay)"),
    ]
    fig.legend(handles=handles, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 0.905), frameon=False)
    fig.suptitle("Regression estimates before and after common-month controls", x=0.07, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.07, 0.925, "Outcome: percentage-point change in annual retail-volume growth; 360 country-months", color="#64707C")
    fig.tight_layout(rect=(0, 0.045, 1, 0.84))
    finish(fig, "06_regression_robustness_coefficients.png", "Source: validated Phase 2 and Phase 2.5 model outputs. DK = Driscoll–Kraay, Bartlett bandwidth 3.")


def figure_7_category_sensitivity() -> None:
    table = pd.read_csv(TABLES / "category_interaction_panel_robustness.csv").set_index("term")
    panels = [
        ("Inflation", ["food_inflation_slope", "nonfood_inflation_slope"]),
        ("Consumer confidence", ["food_confidence_slope", "nonfood_confidence_slope"]),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.8), sharey=True)
    y = np.array([1, 0])
    for ax, (title, terms) in zip(axes, panels):
        rows = table.loc[terms]
        colors = [FOOD_COLOR, NONFOOD_COLOR]
        for ypos, (_, row), color in zip(y, rows.iterrows(), colors):
            ax.errorbar(row["coefficient"], ypos, xerr=[[row["coefficient"] - row["ci_lower_95"]], [row["ci_upper_95"] - row["coefficient"]]], fmt="o", color=color, ecolor=color, capsize=4, markersize=7)
        ax.axvline(0, color="#3D4650", linewidth=1.0)
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold")
        ax.set_xlabel("Estimated category slope with 95% CI")
        ax.set_yticks(y, ["Food", "Non-food"])
    fig.suptitle("Food and non-food showed different sensitivity patterns", x=0.07, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.07, 0.91, "Derived slopes from the interaction model with Driscoll–Kraay uncertainty", color="#64707C")
    fig.tight_layout(rect=(0, 0.05, 1, 0.86))
    finish(fig, "07_category_sensitivity_interactions.png", "Source: validated Phase 2.5 category-interaction robustness output; 720 category observations.")


def write_figure_manifest() -> None:
    rows = [
        ("01_inflation_over_time.png", "Context", "How did inflation change across the three countries?", "Line", "Inflation rose sharply after 2021, with different peaks by country."),
        ("02_total_retail_growth_over_time.png", "Context", "How volatile was total retail-volume growth?", "Line", "Pandemic and reopening months created exceptional movements."),
        ("03_food_nonfood_growth_by_country.png", "Category comparison", "Did food and non-food follow the same pattern?", "Small-multiple line", "Non-food growth was visibly more volatile than food growth."),
        ("04_inflation_food_growth_association.png", "Main finding", "How was inflation related to food growth?", "Scatter with descriptive fit", "Higher inflation was associated with weaker food retail-volume growth."),
        ("05_confidence_nonfood_growth_descriptive.png", "Secondary finding", "How was confidence related to non-food growth?", "Scatter with descriptive fit", "The descriptive positive relationship weakened with month effects."),
        ("06_regression_robustness_coefficients.png", "Robustness", "Which coefficients changed after common-month controls?", "Faceted dot-and-interval", "Food inflation remained stable while several other estimates changed."),
        ("07_category_sensitivity_interactions.png", "Category sensitivity", "How did food and non-food slopes differ?", "Faceted dot-and-interval", "Food had the more negative inflation slope; non-food had the more positive confidence slope."),
    ]
    pd.DataFrame(rows, columns=["figure", "report_role", "analytical_question", "chart_type", "supported_takeaway"]).to_csv(TABLES / "final_figure_manifest.csv", index=False)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    set_style()
    data = pd.read_csv(MASTER_PATH, parse_dates=["date"]).sort_values(["country_code", "date"])
    if len(data) != 396 or data.duplicated(["country_code", "date"]).any():
        raise ValueError("Validated master structure changed; Phase 3 generation stopped")
    create_tableau_extracts(data)
    create_executive_table()
    figure_1_inflation(data)
    figure_2_total_growth(data)
    figure_3_categories(data)
    figure_4_inflation_food(data)
    figure_5_confidence_nonfood(data)
    figure_6_robustness()
    figure_7_category_sensitivity()
    write_figure_manifest()
    print("Phase 3 presentation artifacts created from validated outputs.")


if __name__ == "__main__":
    main()
