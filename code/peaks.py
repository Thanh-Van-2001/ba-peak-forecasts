"""Peak-day bias of BA day-ahead forecasts (PLAN.md). Writes out/results.json, out/ba_table.csv,
out/days.parquet. Run from the repository root:
    python -I code/peaks.py            full run
    python -I code/peaks.py --check    pipeline check (CISO and ERCO, 2018 only) -> out_check/
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm

CHECK = "--check" in sys.argv
OUT = "out_check" if CHECK else "out"
os.makedirs(OUT, exist_ok=True)
SEED, NBOOT, NSHUF, BLOCK = 20261118, 2000, 200, 7
START, END = "2016-01-01", "2026-09-30"
REGION = {  # EIA-930 region of each BA
    "CISO": "CAL", "BANC": "CAL", "LDWP": "CAL", "IID": "CAL", "TIDC": "CAL",
    "CPLE": "CAR", "CPLW": "CAR", "DUK": "CAR", "SC": "CAR", "SCEG": "CAR",
    "SWPP": "CENT", "SPA": "CENT",
    "FPL": "FLA", "FPC": "FLA", "FMPP": "FLA", "JEA": "FLA", "TEC": "FLA", "TAL": "FLA",
    "GVL": "FLA", "SEC": "FLA", "HST": "FLA", "NSB": "FLA",
    "PJM": "MIDA", "MISO": "MIDW", "AECI": "MIDW", "LGEE": "MIDW", "ISNE": "NE", "NYIS": "NY",
    "BPAT": "NW", "PACE": "NW", "PACW": "NW", "PGE": "NW", "PSEI": "NW", "SCL": "NW", "TPWR": "NW",
    "AVA": "NW", "IPCO": "NW", "NWMT": "NW", "CHPD": "NW", "DOPD": "NW", "GCPD": "NW", "NEVP": "NW",
    "PSCO": "NW", "WACM": "NW", "WAUW": "NW",
    "SOCO": "SE", "AEC": "SE", "TVA": "TEN", "ERCO": "TEX",
    "AZPS": "SW", "SRP": "SW", "TEPC": "SW", "EPE": "SW", "PNM": "SW", "WALC": "SW",
}

# ---------------------------------------------------------------- data and sample
d = pd.read_parquet("data/eia930_all.parquet",
                    columns=["ba", "date", "hour", "utc_end", "forecast", "demand", "demand_adj"])
d = d[(d["date"] >= START) & (d["date"] <= END)]
if CHECK:
    d = d[d["ba"].isin(["CISO", "ERCO"]) & (d["date"].dt.year == 2018)]
both = d["demand"].notna() & d["forecast"].notna()
cov = both.groupby([d["ba"], d["date"].dt.year]).mean()
yrs80 = (cov >= 0.8).groupby(level=0).sum()
med = d["demand"].where(d["demand"] > 0).groupby(d["ba"]).median()
need_years = 1 if CHECK else 8
eligible = sorted(yrs80[yrs80 >= need_years].index)
primary = [b for b in eligible if med[b] >= 500]
log = {"eligible": eligible, "primary": primary, "median_mw": med.round(0).to_dict()}


# ---------------------------------------------------------------- screening and days
def screen(g):
    g = g.set_index("utc_end").sort_index()
    full = pd.date_range(g.index.min(), g.index.max(), freq="h")
    g = g.reindex(full)
    ref = g["demand"].where(g["demand"] > 0).rolling(168, center=True, min_periods=24).median()
    out = {}
    for c in ("demand", "forecast", "demand_adj"):
        x = g[c]
        bad = (x <= 0) | (x > 2.0 * ref) | (x < 0.3 * ref)
        out[c] = int((bad & x.notna()).sum())
        if c != "demand_adj":
            g[c] = x.mask(bad)
    return g.dropna(subset=["date"]), out


def daylevel(g, dem="demand"):
    g = g.assign(ok=g[dem].notna() & g["forecast"].notna())
    grp = g.groupby("date")
    n, nok = grp.size(), grp["ok"].sum()
    dates = pd.DatetimeIndex(n.index)
    dst = (dates.month == 3) & (dates.dayofweek == 6) & (dates.day >= 8) & (dates.day <= 14)
    good = n.index[(n >= np.where(dst, 23, 24)) & (nok == n)]
    if len(good) == 0:
        return pd.DataFrame(columns=["D", "F", "p", "e", "mape"], dtype=float)
    g = g[g["date"].isin(good)]
    grp = g.groupby("date")
    i = grp[dem].idxmax()
    D, F = grp[dem].max(), grp["forecast"].max()
    Dh, Fh = g.loc[i, dem].values, g.loc[i, "forecast"].values
    ape = (100 * (g["forecast"] - g[dem]).abs() / g[dem]).groupby(g["date"]).mean()
    D2 = g.sort_values(dem, ascending=False).groupby("date")[dem].nth(1)
    F2 = g.sort_values("forecast", ascending=False).groupby("date")["forecast"].nth(1)
    D2 = pd.Series(D2.values, index=g.loc[D2.index, "date"].values).reindex(D.index)
    F2 = pd.Series(F2.values, index=g.loc[F2.index, "date"].values).reindex(D.index)
    return pd.DataFrame({"D": D, "F": F, "p": 100 * (F - D) / D, "e": 100 * (Fh - Dh) / Dh, "mape": ape,
                         "D2": D2, "F2": F2, "p2": 100 * (F2 - D2) / D2})


def tops(day, q):
    yr = day.index.year
    a = day["D"] >= day.groupby(yr)["D"].transform(lambda s: s.quantile(q))
    f = day["F"] >= day.groupby(yr)["F"].transform(lambda s: s.quantile(q))
    return a, f


days, scr = {}, {}
for ba in eligible:
    g, s = screen(d[d["ba"] == ba])
    scr[ba] = s
    day = daylevel(g)
    day["A"], day["Ftop"] = tops(day, 0.95)
    day["A10"], day["F10"] = tops(day, 0.90)
    t2 = day[["D2", "F2"]].rename(columns={"D2": "D", "F2": "F"})
    day["A2"], day["Ftop2"] = tops(t2, 0.95)
    adj = daylevel(g, "demand_adj")
    adj["A"], adj["Ftop"] = tops(adj, 0.95)
    day = day.join(adj[["p", "A", "Ftop"]].add_suffix("_adj"), how="left")
    day[["A_adj", "Ftop_adj"]] = day[["A_adj", "Ftop_adj"]].fillna(False).astype(bool)
    days[ba] = day
log["screened_values"] = scr

# ---------------------------------------------------------------- weather
temp = {}
if not CHECK:
    choice = json.load(open("data/weather/station_choice.json"))
    plan = {}
    import re
    for line in open("PLAN.md", encoding="utf-8"):
        m = re.match(r"\| ([A-Z]{2,5}) \| (.+) \|$", line.strip())
        if m:
            plan[m.group(1)] = [n.strip() for n, _, _ in re.findall(r"([^;(]+?) \((-?[\d.]+), (-?[\d.]+)\)", m.group(2))]
    series = {}
    for city, c in choice.items():
        if c:
            w = pd.read_csv(f"data/weather/raw/{c['station']}.csv", parse_dates=["DATE"])
            series[city] = pd.to_numeric(w.set_index("DATE")["TMAX"].astype(str).str.strip(), errors="coerce")
    log["weather_missing_city"] = [k for k, v in choice.items() if not v]
    log["weather_ba_without_row"] = [b for b in primary if b not in plan]
    for ba in primary:
        cs = [series[c] for c in plan.get(ba, []) if c in series]
        if cs:
            m = pd.concat(cs, axis=1)
            temp[ba] = m.mean(axis=1).where(m.notna().sum(axis=1) >= len(cs) / 2)


# ---------------------------------------------------------------- statistics
def sign_test(x, alt):
    x = np.asarray([v for v in x if np.isfinite(v) and v != 0])
    k = int((x < 0).sum())
    if len(x) == 0:
        return {"neg": 0, "n": 0, "p": float("nan")}
    r = stats.binomtest(k, len(x), 0.5, alternative=alt)
    return {"neg": k, "n": int(len(x)), "p": float(r.pvalue)}


def blocks(n, rng):
    st = rng.integers(0, max(n - BLOCK + 1, 1), size=(NBOOT, -(-n // BLOCK)))
    idx = (st[:, :, None] + np.arange(BLOCK)).reshape(NBOOT, -1)[:, :n]
    return np.minimum(idx, n - 1)


def boot_se(vals, masks, rng):
    """Block-bootstrap SE of median(vals[mask]) for each mask (membership fixed)."""
    idx = blocks(len(vals), rng)
    v = vals[idx]
    res = []
    for m in masks:
        mm = m[idx]
        w = np.where(mm, v, np.nan)
        res.append(float(np.nanstd(np.nanmedian(w, axis=1), ddof=1)))
    return res


def dl(y, se):
    y, v = np.asarray(y), np.asarray(se) ** 2
    ok = np.isfinite(y) & np.isfinite(v) & (v > 0)
    y, v = y[ok], v[ok]
    if len(y) < 2:
        return None
    w = 1 / v
    yb = (w * y).sum() / w.sum()
    q = (w * (y - yb) ** 2).sum()
    k = len(y)
    t2 = max(0.0, (q - (k - 1)) / (w.sum() - (w ** 2).sum() / w.sum()))
    ws = 1 / (v + t2)
    mu, s = (ws * y).sum() / ws.sum(), (1 / ws.sum()) ** 0.5
    return {"mu": float(mu), "lo": float(mu - 1.96 * s), "hi": float(mu + 1.96 * s), "tau2": float(t2),
            "I2": float(max(0.0, (q - (k - 1)) / q)) if q > 0 else 0.0, "k": int(k)}


rng = np.random.default_rng(SEED)
rows = []
for ba in eligible:
    day = days[ba]
    r = {"ba": ba, "region": REGION.get(ba, "?"), "median_mw": float(med[ba]), "primary": ba in primary,
         "days": int(len(day)), "bias_all": float(day["p"].median()),
         "share_low_peakhour": float((day["e"] < 0).mean()),
         "bias_A": float(day.loc[day["A"], "p"].median()), "bias_F": float(day.loc[day["Ftop"], "p"].median()),
         "bias_A10": float(day.loc[day["A10"], "p"].median()), "bias_F10": float(day.loc[day["F10"], "p"].median()),
         "biasE_A": float(day.loc[day["A"], "e"].median()), "biasE_F": float(day.loc[day["Ftop"], "e"].median()),
         "nA": int(day["A"].sum()), "nF": int(day["Ftop"].sum()), "mape": float(day["mape"].mean())}
    ad = day.dropna(subset=["p_adj"])
    r["bias_A_adj"] = float(ad.loc[ad["A_adj"].astype(bool), "p_adj"].median()) if len(ad) else np.nan
    r["bias_F_adj"] = float(ad.loc[ad["Ftop_adj"].astype(bool), "p_adj"].median()) if len(ad) else np.nan
    summer = day[day.index.month.isin([6, 7, 8, 9])]
    late, early = summer[summer.index.year >= 2023], summer[summer.index.year <= 2019]
    r["trend"] = float(late["p"].abs().median() - early["p"].abs().median()) if len(late) and len(early) else np.nan
    pv = day["p"].values
    yrs = day.index.year.values
    msk = [day["A"].values, day["Ftop"].values]
    sA, sF = boot_se(pv, msk, rng)
    r["se_A"], r["se_F"] = sA, sF
    # trend SE: bootstrap the difference of medians of |p| within summer, blocks within each period
    if len(late) and len(early):
        a1, a2 = np.abs(late["p"].values), np.abs(early["p"].values)
        b1 = np.median(a1[blocks(len(a1), rng)], axis=1)
        b2 = np.median(a2[blocks(len(a2), rng)], axis=1)
        r["se_trend"] = float(np.std(b1 - b2, ddof=1))
    # selection benchmark (shuffle D*/F* within BA-year)
    ratio = (day["D"] / day["F"]).values
    Fv = day["F"].values
    nullA, nullF = [], []
    for _ in range(1 if CHECK else NSHUF):
        rp = ratio.copy()
        for y in np.unique(yrs):
            j = np.where(yrs == y)[0]
            rp[j] = rng.permutation(rp[j])
        Ds = Fv * rp
        ps = 100 * (Fv - Ds) / Ds
        thr = pd.Series(Ds).groupby(yrs).transform(lambda s: s.quantile(0.95)).values
        nullA.append(np.median(ps[Ds >= thr]))
        nullF.append(np.median(ps[day["Ftop"].values]))
    r["null_bias_A"], r["null_bias_F"] = float(np.median(nullA)), float(np.median(nullF))
    # --- amendment 1 (exploratory, added after the results) ---
    r["share_pneg"] = float((day["p"] < 0).mean())
    r["bias_A2"] = float(day.loc[day["A2"], "p2"].median())
    r["bias_F2"] = float(day.loc[day["Ftop2"], "p2"].median())
    ym = day.index.year.values * 100 + day.index.month.values
    nullM = []
    for _ in range(1 if CHECK else NSHUF):
        rp = ratio.copy()
        for y in np.unique(ym):
            j = np.where(ym == y)[0]
            rp[j] = rng.permutation(rp[j])
        Ds = Fv * rp
        ps = 100 * (Fv - Ds) / Ds
        thr = pd.Series(Ds).groupby(yrs).transform(lambda s: s.quantile(0.95)).values
        nullM.append(np.median(ps[Ds >= thr]))
    r["null_bias_A_month"] = float(np.median(nullM))
    # Mincer-Zarnowitz on summer days
    if len(summer) > 30:
        X = sm.add_constant(summer["F"].values)
        fit = sm.OLS(summer["D"].values, X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
        r["mz_slope"], r["mz_lo"], r["mz_hi"] = float(fit.params[1]), *map(float, fit.conf_int()[1])
        Xr = pd.get_dummies(pd.Series(summer.index.year), prefix="y", drop_first=True).astype(float)
        Xr.insert(0, "F", summer["F"].values)
        Xr = sm.add_constant(Xr.values)
        rf = sm.RLM(summer["D"].values, Xr, M=sm.robust.norms.HuberT()).fit()
        r["mzr_slope"] = float(rf.params[1])
        r["mzr_lo"], r["mzr_hi"] = float(rf.params[1] - 1.96 * rf.bse[1]), float(rf.params[1] + 1.96 * rf.bse[1])
    # heat
    if ba in temp:
        t = temp[ba].reindex(summer.index)
        allsum = temp[ba][temp[ba].index.month.isin([6, 7, 8, 9])]
        thr = float(allsum.quantile(0.95))
        hot = t >= thr
        r["hot_thr_c"], r["n_hot"] = thr, int(hot.sum())
        if hot.sum() and (~hot & t.notna()).sum():
            ph, po = summer.loc[hot.values, "p"].values, summer.loc[(~hot & t.notna()).values, "p"].values
            r["heat"] = float(np.median(ph) - np.median(po))
            r["heat_hot"], r["heat_other"] = float(np.median(ph)), float(np.median(po))
            sv = summer["p"].values
            hm, om = hot.values, (~hot & t.notna()).values
            idx = blocks(len(sv), rng)
            bh = np.nanmedian(np.where(hm[idx], sv[idx], np.nan), axis=1)
            bo = np.nanmedian(np.where(om[idx], sv[idx], np.nan), axis=1)
            r["se_heat"] = float(np.nanstd(bh - bo, ddof=1))
            # run length within consecutive hot days, counted on the full daily temperature series
            tf = temp[ba].asfreq("D")
            hf = (tf >= thr) & tf.index.month.isin([6, 7, 8, 9])
            grp_id = (~hf).cumsum()
            runf = hf.astype(int).groupby(grp_id).cumsum().where(hf, 0)
            lenf = hf.astype(int).groupby(grp_id).transform("sum").where(hf, 0)
            run = runf.reindex(summer.index).fillna(0).values
            spell = lenf.reindex(summer.index).fillna(0).values
            prevhot = hf.shift(1, fill_value=False).reindex(summer.index).fillna(False).values.astype(bool)
            prevok = tf.shift(1).reindex(summer.index).notna().values
            sp = summer["p"].values
            if prevhot.sum() and (~prevhot & prevok).sum():
                r["heat_lag"] = float(np.median(sp[prevhot]) - np.median(sp[~prevhot & prevok]))
            d1, d3 = (run == 1) & (spell >= 3), (run >= 3) & (spell >= 3)
            if d1.sum() and d3.sum():
                r["spell_d1_minus_d3"] = float(np.median(sp[d1]) - np.median(sp[d3]))
                r["n_spell3"] = int(d1.sum())
            for lab, m in (("run1", run == 1), ("run2", run == 2), ("run3", run >= 3)):
                r["heat_" + lab] = float(np.median(summer["p"].values[m])) if m.sum() else np.nan
                r["n_" + lab] = int(m.sum())
            r["run1_minus_other"] = r["heat_run1"] - r["heat_other"]
    rows.append(r)

T = pd.DataFrame(rows).set_index("ba")
T.to_csv(f"{OUT}/ba_table.csv")
P = T[T["primary"]]
H = {"H1": sign_test(P["bias_A"], "greater"), "H2": sign_test(P["bias_F"], "greater"),
     "H3": sign_test(P["heat"] if "heat" in P else [], "greater") if "heat" in P else None,
     "H4": sign_test(P["trend"], "two-sided")}
ps = [(k, v["p"]) for k, v in H.items() if v]
order = sorted(ps, key=lambda kv: kv[1])
m, prev = len(order), 0.0
for i, (k, p) in enumerate(order):
    adj = min(1.0, max(prev, (m - i) * p))
    H[k]["p_holm"], prev = adj, adj
    H[k]["supported"] = bool(adj < 0.05) and (k == "H4" or H[k]["neg"] > H[k]["n"] / 2)
sec = {"pooled_A": dl(P["bias_A"], P["se_A"]), "pooled_F": dl(P["bias_F"], P["se_F"]),
       "pooled_trend": dl(P["trend"], P["se_trend"]) if "se_trend" in P else None}
if "se_heat" in P:
    sec["pooled_heat"] = dl(P["heat"], P["se_heat"])
S = T  # secondary sample = all eligible
rob = {"secondary_H1": sign_test(S["bias_A"], "greater"), "secondary_H2": sign_test(S["bias_F"], "greater"),
       "top10_H1": sign_test(P["bias_A10"], "greater"), "top10_H2": sign_test(P["bias_F10"], "greater"),
       "peakhour_H1": sign_test(P["biasE_A"], "greater"), "peakhour_H2": sign_test(P["biasE_F"], "greater"),
       "adjusted_H1": sign_test(P["bias_A_adj"], "greater"), "adjusted_H2": sign_test(P["bias_F_adj"], "greater")}
def votes(col):
    v = P.groupby("region")[col].apply(lambda x: int((x > 0).sum()) - int((x < 0).sum()))
    return np.sign(v).astype(float)


rob["region_H1"] = sign_test(votes("bias_A"), "greater")
rob["region_H2"] = sign_test(votes("bias_F"), "greater")
if "mz_slope" in P:
    rob["mz_above1"] = int((P["mz_slope"] > 1).sum())
    rob["mz_above1_sig"] = int((P["mz_lo"] > 1).sum())
    rob["mz_below1_sig"] = int((P["mz_hi"] < 1).sum())
desc = {"n_primary": len(P), "n_eligible": len(T), "median_bias_all": float(P["bias_all"].median()),
        "median_bias_A": float(P["bias_A"].median()), "median_bias_F": float(P["bias_F"].median()),
        "median_null_bias_A": float(P["null_bias_A"].median()), "median_share_low": float(P["share_low_peakhour"].median()),
        "pooled_share_low_days": float(np.average(P["share_low_peakhour"], weights=P["days"])),
        "below_null": int((P["bias_A"] < P["null_bias_A"]).sum())}
Q = P[P["bias_all"].abs() <= 10]
expl = {"share_pneg_pooled": float(np.average(P["share_pneg"], weights=P["days"])),
        "share_pneg_median": float(P["share_pneg"].median()),
        "p2_H1": sign_test(P["bias_A2"], "greater"), "p2_H2": sign_test(P["bias_F2"], "greater"),
        "rel_F": sign_test(-(P["bias_F"] - P["bias_all"]), "greater"),
        "rel_A": sign_test(P["bias_A"] - P["bias_all"], "greater"),
        "below_null_month": int((P["bias_A"] < P["null_bias_A_month"]).sum()),
        "median_null_month": float(P["null_bias_A_month"].median()),
        "mzr_below1_sig": int((P["mzr_hi"] < 1).sum()), "mzr_above1_sig": int((P["mzr_lo"] > 1).sum()),
        "mzr_median": float(P["mzr_slope"].median()),
        "heat_lag": sign_test(P["heat_lag"], "greater"), "heat_lag_median": float(P["heat_lag"].median()),
        "run1_vs_other": sign_test(P["run1_minus_other"], "greater"),
        "run3_vs_other": sign_test(-(P["heat_run3"] - P["heat_other"]), "greater"),
        "spell_d1_vs_d3": sign_test(P["spell_d1_minus_d3"], "greater"),
        "spell_d1_minus_d3_median": float(P["spell_d1_minus_d3"].median()),
        "n_hot_min": int(P["n_hot"].min()), "n_hot_max": int(P["n_hot"].max()),
        "pooled_A_excl": dl(Q["bias_A"], Q["se_A"]), "pooled_F_excl": dl(Q["bias_F"], Q["se_F"]),
        "pooled_heat_excl": dl(Q["heat"], Q["se_heat"]), "n_excl": int(len(Q)),
        "adj_equal_A": int((P["bias_A"].round(6) == P["bias_A_adj"].round(6)).sum())}
json.dump({"hypotheses": H, "secondary": sec, "robustness": rob, "descriptive": desc, "exploratory": expl, "log": log},
          open(f"{OUT}/results.json", "w"), indent=1, default=float)
pd.concat({b: v for b, v in days.items()}, names=["ba", "date"]).to_parquet(f"{OUT}/days.parquet")
print(json.dumps({"hypotheses": H, "descriptive": desc}, indent=1, default=float))
