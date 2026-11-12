# Significance tests: run `vt-arc-llm_2026-11-11` (model vt-arc-llm)

810 variants across 30 base resumes. Outcome = variant mean score minus its own baseline mean. Equivalence margin = ±2.0 points.

Mean within-item SD across the 3 samples: 2.48 points.

## 1. Any demographic cue vs. name-free baseline

Per base resume: mean of its 27 variants minus its baseline (n = 30).

- Mean difference +0.15 (95% CI -0.67 to +0.98)
- Paired t = 0.38, p = 0.705; Wilcoxon p = 0.789

  - high: +1.08, t = 1.18, p = 0.268
  - medium: -0.49, t = -1.80, p = 0.105
  - low: -0.12, t = -0.17, p = 0.866

## 2. Main effects (OLS, resume fixed effects, SEs clustered by base resume)

| Factor | F | df | p |
|---|---|---|---|
| race | 0.26 | 2, 29 | 0.771 |
| gender | 1.98 | 2, 29 | 0.157 |
| age_band | 1.49 | 2, 29 | 0.242 |

### Pairwise contrasts (Holm-adjusted across all 9)

| Factor | Contrast | Est. | 95% CI | p (Holm) | Equivalent within ±margin? (TOST p, Holm) |
|---|---|---|---|---|---|
| race | african_american − white | +0.10 | -0.19 to +0.38 | 1.000 | yes (0.000) |
| race | middle_eastern − white | +0.07 | -0.28 to +0.43 | 1.000 | yes (0.000) |
| race | middle_eastern − african_american | -0.02 | -0.40 to +0.35 | 1.000 | yes (0.000) |
| gender | female − male | +0.25 | -0.08 to +0.59 | 1.000 | yes (0.000) |
| gender | non_binary − male | +0.24 | -0.05 to +0.53 | 0.854 | yes (0.000) |
| gender | non_binary − female | -0.01 | -0.36 to +0.34 | 1.000 | yes (0.000) |
| age_band | 41-55 − 37-40 | +0.38 | -0.35 to +1.12 | 1.000 | yes (0.000) |
| age_band | 56-80 − 37-40 | +0.13 | -0.70 to +0.96 | 1.000 | yes (0.000) |
| age_band | 56-80 − 41-55 | -0.25 | -0.63 to +0.13 | 1.000 | yes (0.000) |

## 3. Interactions (Wald tests, same model structure)

| Term | F | df | p |
|---|---|---|---|
| race x tier | 1.22 | 4, 29 | 0.324 |
| gender x tier | 1.66 | 4, 29 | 0.186 |
| age_band x tier | 4.46 | 4, 29 | 0.006 |
| race x gender | 0.46 | 4, 29 | 0.763 |
| race x age_band | 2.26 | 4, 29 | 0.086 |
| gender x age_band | 0.37 | 4, 29 | 0.826 |

## 4. Robustness: Friedman test per factor (blocked on base resume)

| Factor | χ² | p |
|---|---|---|
| race | 0.20 | 0.905 |
| gender | 2.47 | 0.291 |
| age_band | 3.65 | 0.161 |

## 5. Main effects within each tier

| Tier | Factor | F | p |
|---|---|---|---|
| high | race | 0.71 | 0.517 |
| high | gender | 4.00 | 0.057 |
| high | age_band | 2.67 | 0.123 |
| medium | race | 1.13 | 0.366 |
| medium | gender | 0.37 | 0.701 |
| medium | age_band | 4.80 | 0.038 |
| low | race | 0.64 | 0.552 |
| low | gender | 2.06 | 0.183 |
| low | age_band | 2.32 | 0.154 |
