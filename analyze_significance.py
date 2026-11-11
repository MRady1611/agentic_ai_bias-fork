#!/usr/bin/env python3
"""Significance tests for demographic effects in results/<run>.json.

Unit of analysis: one variant (mean of its samples), expressed as the
difference from the name-free baseline of its own base resume.

Tests
  1. Named vs. name-free: paired per base resume (t-test + Wilcoxon), n=30.
  2. Main effects: OLS of diff_from_baseline on race + gender + age band with
     base-resume fixed effects, SEs clustered by base resume. Wald test per
     factor, pairwise contrasts with Holm correction.
  3. Interactions: factor x tier and factor x factor Wald tests.
  4. Robustness: Friedman test per factor, blocked on base resume.
  5. Equivalence: TOST of each pairwise contrast against +/- MARGIN points.

Usage: python3 analyze_significance.py [--run scores] [--margin 2]
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.multitest import multipletests

FACTORS = {
    "race": ["white", "african_american", "middle_eastern"],
    "gender": ["male", "female", "non_binary"],
    "age_band": ["37-40", "41-55", "56-80"],
}


def load(run):
    d = json.load(open(Path("results") / f"{run}.json"))
    df = pd.DataFrame(d["results"])
    return d["run"], df


def fit(df, formula):
    return smf.ols(formula, data=df).fit(
        cov_type="cluster", use_t=True, cov_kwds={"groups": df["resume_id"].astype("category").cat.codes}
    )


def wald(model, prefix):
    names = [n for n in model.params.index if n.startswith(prefix)]
    if not names:
        return None
    R = np.zeros((len(names), len(model.params)))
    for i, n in enumerate(names):
        R[i, list(model.params.index).index(n)] = 1
    w = model.wald_test(R, scalar=True)
    return {"F": float(w.statistic), "df_num": len(names), "df_denom": float(w.df_denom), "p": float(w.pvalue)}


def contrast(model, a, b, factor):
    """Estimate level a minus level b for `factor` (treatment-coded)."""
    vec = pd.Series(0.0, index=model.params.index)
    for lvl, sign in ((a, 1), (b, -1)):
        key = f"C({factor}, Treatment('{FACTORS[factor][0]}'))[T.{lvl}]"
        if key in vec.index:
            vec[key] += sign
    t = model.t_test(vec.values)
    est, se = float(np.squeeze(t.effect)), float(np.squeeze(t.sd))
    return est, se, float(np.squeeze(t.pvalue)), float(t.df_denom)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="scores")
    ap.add_argument("--margin", type=float, default=2.0, help="equivalence margin in score points")
    args = ap.parse_args()

    meta, df = load(args.run)
    base = df[df.is_baseline].set_index("resume_id")
    var = df[~df.is_baseline].copy()
    out = {"run": meta.get("run_name"), "model": meta.get("model"), "margin": args.margin,
           "n_variants": len(var), "n_base": len(base)}
    lines = [f"# Significance tests: run `{out['run']}` (model {out['model']})", "",
             f"{len(var)} variants across {len(base)} base resumes. Outcome = variant mean score "
             f"minus its own baseline mean. Equivalence margin = ±{args.margin} points.", ""]

    # Sampling noise context
    sd_within = df["sd_score"].mean()
    lines += [f"Mean within-item SD across the 3 samples: {sd_within:.2f} points.", ""]
    out["mean_within_item_sd"] = sd_within

    # 1. Named vs name-free
    per = var.groupby("resume_id")["diff_from_baseline"].mean()
    t = stats.ttest_1samp(per, 0)
    w = stats.wilcoxon(per) if (per != 0).any() else None
    ci = stats.t.interval(0.95, len(per) - 1, loc=per.mean(), scale=stats.sem(per))
    out["named_vs_baseline"] = {"mean_diff": per.mean(), "ci95": ci, "t": t.statistic, "p_t": t.pvalue,
                                "p_wilcoxon": None if w is None else w.pvalue}
    lines += ["## 1. Any demographic cue vs. name-free baseline", "",
              "Per base resume: mean of its 27 variants minus its baseline (n = 30).", "",
              f"- Mean difference {per.mean():+.2f} (95% CI {ci[0]:+.2f} to {ci[1]:+.2f})",
              f"- Paired t = {t.statistic:.2f}, p = {t.pvalue:.3f}"
              + ("" if w is None else f"; Wilcoxon p = {w.pvalue:.3f}"), ""]
    for tier in ["high", "medium", "low"]:
        p = per[per.index.str.startswith(tier)]
        tt = stats.ttest_1samp(p, 0)
        lines.append(f"  - {tier}: {p.mean():+.2f}, t = {tt.statistic:.2f}, p = {tt.pvalue:.3f}")
    lines.append("")

    # 2. Main effects
    rhs = " + ".join(f"C({f}, Treatment('{lv[0]}'))" for f, lv in FACTORS.items())
    m = fit(var, f"diff_from_baseline ~ {rhs} + C(resume_id)")
    lines += ["## 2. Main effects (OLS, resume fixed effects, SEs clustered by base resume)", "",
              "| Factor | F | df | p |", "|---|---|---|---|"]
    out["main_effects"] = {}
    for f in FACTORS:
        wt = wald(m, f"C({f},")
        out["main_effects"][f] = wt
        lines.append(f"| {f} | {wt['F']:.2f} | {wt['df_num']}, {wt['df_denom']:.0f} | {wt['p']:.3f} |")
    lines.append("")

    # Pairwise contrasts + TOST
    rows = []
    for f, lv in FACTORS.items():
        for a, b in itertools.combinations(lv, 2):
            est, se, p, dfd = contrast(m, b, a, f)
            p_lo = 1 - stats.t.cdf((est + args.margin) / se, dfd)
            p_hi = stats.t.cdf((est - args.margin) / se, dfd)
            ci = (est - stats.t.ppf(0.975, dfd) * se, est + stats.t.ppf(0.975, dfd) * se)
            rows.append({"factor": f, "contrast": f"{b} − {a}", "est": est, "se": se,
                         "ci95": ci, "p": p, "p_tost": max(p_lo, p_hi)})
    holm = multipletests([r["p"] for r in rows], method="holm")[1]
    holm_tost = multipletests([r["p_tost"] for r in rows], method="holm")[1]
    for r, h, ht in zip(rows, holm, holm_tost):
        r["p_holm"], r["p_tost_holm"] = h, ht
    out["contrasts"] = rows
    lines += ["### Pairwise contrasts (Holm-adjusted across all 9)", "",
              "| Factor | Contrast | Est. | 95% CI | p (Holm) | Equivalent within ±margin? (TOST p, Holm) |",
              "|---|---|---|---|---|---|"]
    for r in rows:
        eq = "yes" if r["p_tost_holm"] < 0.05 else "no"
        lines.append(f"| {r['factor']} | {r['contrast']} | {r['est']:+.2f} | "
                     f"{r['ci95'][0]:+.2f} to {r['ci95'][1]:+.2f} | {r['p_holm']:.3f} | "
                     f"{eq} ({r['p_tost_holm']:.3f}) |")
    lines.append("")

    # 3. Interactions
    lines += ["## 3. Interactions (Wald tests, same model structure)", "",
              "| Term | F | df | p |", "|---|---|---|---|"]
    out["interactions"] = {}
    terms = [(f, "tier") for f in FACTORS] + list(itertools.combinations(FACTORS, 2))
    for a, b in terms:
        def C(x):
            return f"C({x})" if x == "tier" else f"C({x}, Treatment('{FACTORS[x][0]}'))"
        # include tier main so patsy codes the interaction at reduced rank
        rhs_i = rhs + (" + C(tier)" if b == "tier" else "") + f" + {C(a)}:{C(b)}"
        mi = fit(var, f"diff_from_baseline ~ {rhs_i} + C(resume_id)")
        names = [n for n in mi.params.index if n.count(":") == 1 and a in n and b in n]
        R = np.zeros((len(names), len(mi.params)))
        for i, n in enumerate(names):
            R[i, list(mi.params.index).index(n)] = 1
        wt = mi.wald_test(R, scalar=True)
        key = f"{a} x {b}"
        out["interactions"][key] = {"F": float(wt.statistic), "df_num": len(names), "p": float(wt.pvalue)}
        lines.append(f"| {key} | {float(wt.statistic):.2f} | {len(names)}, {float(wt.df_denom):.0f} | {float(wt.pvalue):.3f} |")
    lines.append("")

    # 4. Friedman
    lines += ["## 4. Robustness: Friedman test per factor (blocked on base resume)", "",
              "| Factor | χ² | p |", "|---|---|---|"]
    out["friedman"] = {}
    for f, lv in FACTORS.items():
        wide = var.pivot_table(index="resume_id", columns=f, values="diff_from_baseline", aggfunc="mean")[lv]
        fr = stats.friedmanchisquare(*[wide[c] for c in lv])
        out["friedman"][f] = {"chi2": fr.statistic, "p": fr.pvalue}
        lines.append(f"| {f} | {fr.statistic:.2f} | {fr.pvalue:.3f} |")
    lines.append("")

    # Per-tier main effects
    lines += ["## 5. Main effects within each tier", "", "| Tier | Factor | F | p |", "|---|---|---|---|"]
    out["by_tier"] = {}
    for tier in ["high", "medium", "low"]:
        sub = var[var.tier == tier]
        mt = fit(sub, f"diff_from_baseline ~ {rhs} + C(resume_id)")
        for f in FACTORS:
            wt = wald(mt, f"C({f},")
            out["by_tier"][f"{tier}:{f}"] = wt
            lines.append(f"| {tier} | {f} | {wt['F']:.2f} | {wt['p']:.3f} |")
    lines.append("")

    Path("results").joinpath(f"{args.run}.significance.md").write_text("\n".join(lines))
    Path("results").joinpath(f"{args.run}.significance.json").write_text(json.dumps(out, indent=1, default=float))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
