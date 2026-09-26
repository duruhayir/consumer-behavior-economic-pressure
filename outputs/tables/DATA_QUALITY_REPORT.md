# Data quality validation

Dataset grain: one row per country and calendar month for NL, DE, and FR, January 2015 through December 2025.

- Master rows: **396 / 396**
- Duplicate country-date rows: **0**
- Unexpected calendar or core-source gaps: **0**
- Failed checks: **0**
- Warning checks: **0**

Structural missingness is expected only where year-on-year calculations need 12 prior months and lags need 1-3 prior months. No values are imputed.

See the companion CSV tables in this directory for complete check-level evidence.
