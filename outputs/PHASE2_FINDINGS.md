# Phase 2 findings: EDA and statistical analysis

> This file records the Phase 2 results before the panel robustness checks. The final interpretation is in `FINAL_REPORT.md`; Phase 2.5 showed that the initial positive confidence estimates weakened after common month effects were added.

## 1. Dataset used

The analysis uses `data/processed/consumer_behavior_eu_2015_2025.csv`: 396 monthly country observations for the Netherlands, Germany, and France from January 2015 through December 2025. Retail outcomes are year-on-year changes in Eurostat retail **volume-of-sales** indices, interpreted as real retail-activity proxies, not nominal expenditure or total household consumption. Each retail-growth outcome has 360 usable observations because the first 12 months per country are structurally unavailable.

The hypotheses were recorded before reviewing the results: higher inflation was expected to be associated with weaker retail-volume growth (H1), higher confidence with stronger growth (H2), and non-food growth with greater sensitivity than food growth (H3).

## 2. Main descriptive patterns

- Pooled mean annual inflation was 2.53% (median 1.70%; range -1.0% to 17.1%). Mean confidence was -8.95 balance points (range -35.9 to 7.1).
- Mean total retail-volume growth was 2.02% YoY. Food growth averaged 0.69%, compared with 3.39% for non-food excluding automotive fuel.
- Non-food growth was substantially more volatile than food growth: pooled standard deviations were 7.75 versus 3.47 percentage points. Non-food ranged from -46.50% to 77.10%, largely reflecting pandemic/reopening extremes; food ranged from -9.70% to 13.73%.
- France had the highest total-growth volatility (SD 6.58) and non-food volatility (SD 10.79). The Netherlands had the highest mean inflation (2.90%), while France had the lowest mean confidence (-11.96).

## 3. RQ1 — Inflation and real retail-sales growth

The descriptive association was negative for total growth but much stronger for food:

- Pooled Pearson correlations: total **r = -0.250**, food **r = -0.646**, non-food **r = -0.097** (N=360).
- Pooled Spearman correlations: total **rho = -0.365**, food **rho = -0.575**, non-food **rho = -0.223**.
- The pooled country-fixed-effects model gave an inflation coefficient of **-0.046** percentage points for total growth (95% CI **[-0.342, 0.250]**), **-0.786** for food growth (95% CI **[-0.981, -0.591]**), and **0.321** for non-food growth (95% CI **[-0.135, 0.778]**).

H1 therefore received **partial, outcome-specific support**. The negative inflation association was clear and consistent for food volume growth, but the adjusted association with total and non-food growth was not clearly different from zero.

## 4. RQ2 — Consumer confidence and real retail-sales growth

Confidence showed positive descriptive relationships with all three outcomes:

- Pooled Pearson correlations: total **r = 0.294**, food **r = 0.354**, non-food **r = 0.194**.
- Pooled Spearman correlations: total **rho = 0.377**, food **rho = 0.307**, non-food **rho = 0.300**.
- In pooled country-fixed-effects models, the confidence coefficient was **0.195** for total growth (95% CI **[0.089, 0.302]**) and **0.309** for non-food growth (95% CI **[0.148, 0.470]**). The adjusted food coefficient was **-0.007** (95% CI **[-0.061, 0.048]**).

H2 was supported for total and non-food volume growth in the primary adjusted models, but not for food after contemporaneous inflation and country differences were held constant.

## 5. RQ3 — Food versus non-food sensitivity

The interaction model used 720 category observations and standard errors clustered across 360 country-months.

- The food inflation slope was **-0.725** (95% CI **[-0.921, -0.530]**). The inflation-by-non-food interaction was **+0.986** (95% CI **[0.537, 1.436]**), producing an estimated non-food inflation slope of **+0.261** (95% CI **[-0.183, 0.705]**).
- The food confidence slope was **0.022** (95% CI **[-0.039, 0.082]**). The confidence-by-non-food interaction was **+0.258** (95% CI **[0.116, 0.401]**), producing a non-food confidence slope of **0.280** (95% CI **[0.127, 0.434]**).

H3 was **mixed rather than confirmed**. Non-food growth was more volatile and more positively associated with confidence, but it was not more negatively associated with inflation. The inflation result instead showed a materially more negative relationship for food.

## 6. RQ4 — Cross-country differences

Country-specific HAC regressions showed substantial heterogeneity:

- For total growth, inflation coefficients were **0.123** in NL (95% CI [-0.273, 0.520]), **-0.691** in DE ([-1.184, -0.197]), and **0.366** in FR ([-0.588, 1.320]). Only Germany showed a clearly negative full-sample estimate.
- Total-growth confidence coefficients were **0.165** in NL ([0.058, 0.272]), **0.046** in DE ([-0.102, 0.193]), and **0.509** in FR ([0.099, 0.918]).
- Food inflation coefficients were negative in all three countries: **-0.539** in NL, **-1.283** in DE, and **-0.647** in FR.
- Non-food confidence coefficients were **0.207** in NL, **0.180** in DE, and **0.747** in FR; intervals excluded zero in NL and FR but not DE.

These are descriptive coefficient differences, not formal rankings or causal country effects. Some differences were sensitive to the COVID exclusion.

## 7. Exploratory lag analysis

All lags 0–3 are reported in `lag_correlations.csv`; no single lag was selected as pre-specified or predictive.

- For pooled total growth, the inflation Pearson association became progressively more negative from **r = -0.250** at lag 0 to **-0.324** at lag 3. Spearman rho moved from **-0.365** to **-0.405**.
- Pooled food-inflation Pearson correlations were similar across lags (**-0.646, -0.658, -0.659, -0.643** for lags 0–3).
- Pooled non-food inflation correlations were weaker but became more negative from **-0.097** at lag 0 to **-0.180** at lag 3.
- Confidence was most strongly associated contemporaneously in the pooled Pearson results: total **0.294**, food **0.354**, and non-food **0.194** at lag 0; corresponding lag 1–3 total correlations ranged from **0.217 to 0.241**.

These patterns describe timing associations only. They are not forecasting validation and do not establish that earlier inflation or confidence predicts later retail activity.

## 8. Regression and standardized-effect summary

Primary pooled models used HC3 standard errors and country indicators (N=360). R-squared values were **0.117** for total, **0.445** for food, and **0.062** for non-food growth.

With predictors standardized but outcomes kept in percentage points, a one-standard-deviation increase in confidence was associated with **1.52 pp** higher total growth and **2.40 pp** higher non-food growth. A one-standard-deviation increase in inflation was associated with **2.19 pp** lower food growth. These standardized results reproduce the raw-unit model conclusions and are secondary effect-size comparisons.

## 9. COVID/reopening robustness check

Excluding March 2020 through December 2021 left 294 pooled observations:

- Total confidence remained positive: **0.195** in the full sample versus **0.141** excluding the period; its 95% CI remained above zero (**[0.084, 0.197]**).
- Food inflation remained negative but decreased in magnitude: **-0.786** versus **-0.485**, with an exclusion-sample CI of **[-0.658, -0.312]**.
- Non-food confidence remained positive: **0.309** versus **0.201**, with an exclusion-sample CI of **[0.104, 0.298]**.
- Total inflation remained imprecise: **-0.046** versus **-0.126**, with an exclusion-sample CI of **[-0.328, 0.076]**.
- R-squared increased from **0.117 to 0.267** for total, **0.445 to 0.553** for food, and **0.062 to 0.107** for non-food.

The main pooled confidence/total, confidence/non-food, and inflation/food signs were not entirely driven by the pandemic period. However, food confidence changed from approximately zero to **0.087** ([0.048, 0.126]), and several country-specific coefficients changed materially, so pandemic/reopening observations affect inference.

## 10. Diagnostics and limitations

- Predictor VIF values were low (approximately **1.93–2.02**), so severe multicollinearity was not indicated.
- Durbin-Watson statistics were about **1.00–1.05**, and Breusch-Godfrey lag-3 p-values were below 0.001 for every pooled outcome, indicating material serial dependence. HC3 addresses heteroskedasticity but not serial correlation; pooled p-values and confidence intervals should therefore be treated cautiously.
- Residuals were non-normal and influential pandemic observations were present. Maximum Cook's distance was **0.265** for total growth and **0.205** for non-food growth, both at France in April 2020. These observations were retained as pre-specified.
- The data are observational and cannot establish causality. Retail volume is not total household consumption; confidence and retail activity may influence each other; omitted macroeconomic variables and common European shocks remain; annual growth rates overlap across months; only three countries and broad categories are included; and this period may not generalize to other environments.

## 11. Readiness for Phase 3

The evidence is sufficiently coherent to proceed to dashboard/report design **if Phase 3 foregrounds the mixed results and uncertainty**. The strongest recurring findings are the negative inflation–food association and the positive confidence associations with total and non-food growth. The weaker total-inflation result, country heterogeneity, serial dependence, and pandemic sensitivity must remain visible rather than being simplified into a single causal story.
