"""Amendment 2 (exploratory, after independent review; see PLAN.md). Reads out/days.parquet,
out/ba_table.csv and the weather files written for code/peaks.py; writes out/amendment2.json.
Does not change any output of peaks.py. Run from the repository root:
    python -I code/amendment2.py
"""
import json
import re

import numpy as np
import pandas as pd
from scipy import stats

SEED, NBOOT, NSHUF, BLOCK = 20261119, 2000, 200, 7
SUMMER = [6, 7, 8, 9]
rng = np.random.default_rng(SEED)

T = pd.read_csv("out/ba_table.csv", index_col=0)
P = T[T["primary"]].copy()
days = pd.read_parquet("out/days.parquet")

# ---------------------------------------------------------------- weather (as in peaks.py)
choice = json.load(open("data/weather/station_choice.json"))
plan = {}
for line in open("PLAN.md", encoding="utf-8"):
    m = re.match(r"\| ([A-Z]{2,5}) \| (.+) \|$", line.strip())
    if m:
        plan[m.group(1)] = [n.strip() for n, _, _ in re.findall(r"([^;(]+?) \((-?[\d.]+), (-?[\d.]+)\)", m.group(2))]
series = {}
for city, c in choice.items():
    if c:
        w = pd.read_csv(f"data/weather/raw/{c['station']}.csv", parse_dates=["DATE"])
        series[city] = pd.to_numeric(w.set_index("DATE")["TMAX"].astype(str).str.strip(), errors="coerce")
temp = {}
for ba in P.index:
    cs = [series[c] for c in plan.get(ba, []) if c in series]
    if cs:
        m = pd.concat(cs, axis=1)
        temp[ba] = m.mean(axis=1).where(m.notna().sum(axis=1) >= len(cs) / 2)


# ---------------------------------------------------------------- helpers
def sign_test(x, alt="greater"):
    x = np.asarray([v for v in x if np.isfinite(v) and v != 0])
    k = int((x < 0).sum())
    if len(x) == 0:
        return {"neg": 0, "n": 0, "p": float("nan")}
    return {"neg": k, "n": int(len(x)), "p": float(stats.binomtest(k, len(x), 0.5, alternative=alt).pvalue)}


def blocks(n):
    st = rng.integers(0, max(n - BLOCK + 1, 1), size=(NBOOT, -(-n // BLOCK)))
    idx = (st[:, :, None] + np.arange(BLOCK)).reshape(NBOOT, -1)[:, :n]
    return np.minimum(idx, n - 1)


def rep_median(vals, mask, idx):
    return np.nanmedian(np.where(mask[idx], vals[idx], np.nan), axis=1)


def votes(s):
    v = s.groupby(P["region"]).apply(lambda x: int((x > 0).sum()) - int((x < 0).sum()))
    return np.sign(v).astype(float)


def cp(k, n):
    r = stats.binomtest(k, n).proportion_ci(confidence_level=0.95, method="exact")
    return [float(r.low), float(r.high)]


# ---------------------------------------------------------------- per-BA statistics and replicates
reps = {"bias_A": {}, "bias_F": {}, "heat": {}}
rows = []
for ba in P.index:
    day = days.loc[ba]
    pv, A, Fm = day["p"].values, day["A"].values.astype(bool), day["Ftop"].values.astype(bool)
    r = {"ba": ba}
    # sanity: the stored statistics reproduce ba_table.csv
    assert np.isclose(np.median(pv[A]), P.loc[ba, "bias_A"]) and np.isclose(np.median(pv[Fm]), P.loc[ba, "bias_F"])
    idx = blocks(len(pv))
    reps["bias_A"][ba], reps["bias_F"][ba] = rep_median(pv, A, idx), rep_median(pv, Fm, idx)
    # mean calibration: error as a share of the forecast
    q = (100 * (day["F"] - day["D"]) / day["F"]).values
    r["mean_q_A"], r["mean_q_F"] = float(q[A].mean()), float(q[Fm].mean())
    # heat difference and its replicates
    summer = day[day.index.month.isin(SUMMER)]
    t = temp[ba].reindex(summer.index)
    allsum = temp[ba][temp[ba].index.month.isin(SUMMER)]
    hot = (t >= float(allsum.quantile(0.95))).values
    oth = (~(t >= float(allsum.quantile(0.95))) & t.notna()).values
    sv = summer["p"].values
    r["heat"] = float(np.median(sv[hot]) - np.median(sv[oth]))
    assert np.isclose(r["heat"], P.loc[ba, "heat"])
    si = blocks(len(sv))
    reps["heat"][ba] = rep_median(sv, hot, si) - rep_median(sv, oth, si)
    # benchmark with level-dependent errors: shuffle D*/F* within BA-year x quintile of F* in that year
    yrs = day.index.year.values
    Fv, ratio = day["F"].values, (day["D"] / day["F"]).values
    qbin = day.groupby(day.index.year)["F"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) if len(s) >= 5 else 0 * s).values.astype(int)
    cell = yrs * 10 + qbin
    groups = [np.where(cell == c)[0] for c in np.unique(cell)]
    null = []
    for _ in range(NSHUF):
        rp = ratio.copy()
        for j in groups:
            rp[j] = rng.permutation(rp[j])
        Ds = Fv * rp
        ps = 100 * (Fv - Ds) / Ds
        thr = pd.Series(Ds).groupby(yrs).transform(lambda s: s.quantile(0.95)).values
        null.append(np.median(ps[Ds >= thr]))
    r["null_bias_A_level"] = float(np.median(null))
    rows.append(r)

X = pd.DataFrame(rows).set_index("ba")
P = P.join(X[["mean_q_A", "mean_q_F", "null_bias_A_level"]])
regions = sorted(P["region"].unique())
by_region = {g: list(P.index[P["region"] == g]) for g in regions}
bas = list(P.index)


# ---------------------------------------------------------------- two-stage bootstrap
def two_stage(stat, unit):
    R = np.vstack([reps[stat][b] for b in bas])  # BA x replicate
    pos = {b: i for i, b in enumerate(bas)}
    med, share = np.empty(NBOOT), np.empty(NBOOT)
    for k in range(NBOOT):
        if unit == "region":
            pick = [pos[b] for g in rng.choice(regions, size=len(regions), replace=True) for b in by_region[g]]
        else:
            pick = list(rng.integers(0, len(bas), size=len(bas)))
        v = R[pick, k]
        v = v[np.isfinite(v)]
        med[k], share[k] = np.median(v), np.mean(v < 0)
    return {"median": float(P[stat].median()), "share_neg": float((P[stat] < 0).mean()),
            "median_ci": [float(np.percentile(med, 2.5)), float(np.percentile(med, 97.5))],
            "share_ci": [float(np.percentile(share, 2.5)), float(np.percentile(share, 97.5))]}


out = {"seed": SEED, "n_boot": NBOOT, "n_regions": len(regions), "regions": by_region, "bounds": {}}
for stat in ("bias_A", "bias_F", "heat"):
    k, n = int((P[stat] < 0).sum()), int((P[stat] != 0).sum())
    out["bounds"][stat] = {"neg": k, "n": n, "cp_share_ci": cp(k, n),
                           "region": two_stage(stat, "region"), "ba": two_stage(stat, "ba")}
lo, hi = P["bias_F"] - 1.96 * P["se_F"], P["bias_F"] + 1.96 * P["se_F"]
out["bias_F_sig_below"], out["bias_F_sig_above"] = int((hi < 0).sum()), int((lo > 0).sum())
out["bias_F_sig_below_bas"] = list(P.index[hi < 0])
out["region_votes"] = {"heat": votes(P["heat"]).to_dict(), "run1_minus_other": votes(P["run1_minus_other"]).to_dict()}
out["region_H3"] = sign_test(votes(P["heat"]))
out["region_run1"] = sign_test(votes(P["run1_minus_other"]))
Q = P[P["bias_all"].abs() <= 10]
out["excl_level"] = {"bas": list(P.index[P["bias_all"].abs() > 10]), "H1": sign_test(Q["bias_A"]),
                     "H2": sign_test(Q["bias_F"]), "H3": sign_test(Q["heat"])}
out["mean_H1"], out["mean_H2"] = sign_test(P["mean_q_A"]), sign_test(P["mean_q_F"])
out["mean_q_A_median"], out["mean_q_F_median"] = float(P["mean_q_A"].median()), float(P["mean_q_F"].median())
out["below_null_level"] = int((P["bias_A"] < P["null_bias_A_level"]).sum())
out["median_null_level"] = float(P["null_bias_A_level"].median())
out["per_ba"] = X.round(6).to_dict(orient="index")
json.dump(out, open("out/amendment2.json", "w"), indent=1, default=float)
print(json.dumps({k: v for k, v in out.items() if k not in ("per_ba", "regions", "region_votes")}, indent=1, default=float))
