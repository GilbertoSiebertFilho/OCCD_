# -*- coding: utf-8 -*-
"""Several combines in one field: paired-cell harmonisation with a block bootstrap, and per-machine scale tickets.

    from engine.clean import machines
    M, applied, warnings = machines.harmonise(frame, settings["machines"], ref_setting="auto")
    cells = machines.paired_cells(frame, "_machine", "A", "B", size_m=30, plot_col="Plot_Id")
    est = machines.ratio_estimate(cells, reps=1000, seed=2026, ci=0.95)

Problem. Two combines on one field read the same grain differently: a yield monitor's level error after a field
calibration is typically 1-3 % (Luck & Fulton 2014; Gauci et al. 2023), more outside the calibrated flow range
(15.8-17.2 % at 3.2 km/h, Gauci et al. 2023). A trial
analysed on two machines' readings therefore mixes a machine effect with the treatment effect, and the DIFM response
curve sees a step wherever the machines meet. Maldaner et al. (2016, ISPA proceedings, not refereed) take the machine
with the largest harvested area as the reference and test three factors on fields of two combines: machine by machine
(mean of all points / mean of all points), track by track (the means of the ONE pair of closest paths) and point by
point (the arithmetic mean of the point ratios on that one path pair); with more combines, the nearest combine is
corrected first, then the one nearest the corrected set. They judge the factors by the drop of the SD / CV and by
variograms, with no weighed reference, and conclude that one factor fails when the difference between the machines
changes over the field. On pseudo-combines with a known factor (one real combine split in two, 2026 fields) a single
path pair puts the factor off by more than 5 % in 43 % of the pairs (SD 9.5 %), and the whole-field means are off by up
to 8-11 % when each machine cut its own block (the ground differs). Chiocco & Wuestefeld (2019) search a +/-10 % gain
on nearest positions across adjacent paths and note that harmonisation fixes consistency, not level. Neither gives a
significance or materiality gate: the gates below are a house method. This module is the v2 rule of Section 4.14 of
the literature review, with the network of v2.5.

Method (the numbers are house conventions unless cited)
  1. Reference = the machine with the most kept points (machines.reference "auto") or the id given.
  2. Pairs. For EVERY pair of machines, the kept points with <= pair_max_overlap (2 %, PAIR_MAX_OVERLAP) of their
     footprint already cut are binned into 30 m and 50 m square cells; a cell is a pair when BOTH machines have >= 5
     such points in it (so the two machines cut neighbouring passes of the same, uncut ground). The overlap rule is
     needed because the pass that follows another carries the overlap below the F8 threshold and its kept records read
     2-3 % low (Trial 19: the 2-5 % band is -2.4 % against the no-overlap band): pairing every kept record of two
     combines that work side by side measures that overlap, not the machines (Trial 19 with alternate passes labelled
     A / B and no yield change: factor 1.029, CI 1.008-1.049, "applied" on every kept record; 1.009 with the rule). The
     2 % edge is the 0-2 % band, which reads within 0.2 % of the no-overlap band (house rule). When a plan with plots
     exists and machines.same_plot_only, the cells are also split by Plot_Id, so a pair always compares the same
     treatment (the rate effect cannot enter the factor). Every cell carries its pass pair (the modal Pass_Id of each
     machine in the cell). The ratio of a pair is exp(mean(log(y_a / y_b))) over its cells (the geometric-mean ratio:
     a multiplicative level error is symmetric in log space), with a CI by a block bootstrap over its PASS PAIRS
     (bootstrap_reps resamples of the pass pairs with replacement, the cells of a pass pair move together; seed fixed):
     neighbouring cells of one pass pair are not independent, so a cell-level test would overstate the precision. A
     pair is LINKED when it has >= min_pairs (30) cells and >= min_pass_pairs (5) pass pairs at BOTH sizes.
  3. The network (machines.network, default true). u_m = log(y_ref / y_m) is the log factor of machine m (u_ref = 0).
     Every linked pair (a, b) observes u_b - u_a = mean log(y_a / y_b), with weight 1 / its bootstrap variance; u is the
     weighted least-squares solution (network_solve), at 30 m and at 50 m, and its CI comes from re-solving the network
     on the bootstrap draws of every pair. A machine that never met the reference gets its factor through its
     neighbours (the "nearest combine" of Maldaner et al. 2016, with every link used at once and no order to choose);
     a machine with no chain of linked pairs to the reference gets no factor. When every linked pair involves the
     reference (two machines always) the solution is the direct estimate, byte for byte the v2.4 one. On three
     pseudo-combines (random pass splits of four single-combine data sets, one pseudo-combine x 1.05): a false factor
     on the unchanged one in 1/40 splits (2/40 with the reference pairs only), the true one applied in 21/40 (18/40),
     error 1.35 % (1.56 %). The paired t-test p and the mean moisture difference against the reference are kept as
     diagnostics ("p_ttest", "moisture_diff", m - ref): a level difference that comes with a moisture difference may be
     a moisture-sensor difference.
  4. The 30 m factor is applied (new column Yld_Harm = y x f) only if: both CIs exclude 1, |f30 / f50 - 1| <= 2 %
     (the factor must not depend on the cell size), min_factor (1 %) < |f - 1| <= max_factor (10 %), and (item 5) one
     factor fits the whole field. Above max_factor nothing is applied unless the field's scale ticket confirms it
     (item 8): a > 10 % step is beyond what a relative factor should repair (Chiocco & Wuestefeld 2019 bound their
     search at +/-10 %). Below min_factor the step is inside the calibration noise.
  5. Spatial check (machines.spatial_check, default true; spatial_check()). Every contact cell of the machine estimates
     its log factor (the partner's log factor + the cell's log ratio); the cells are split in two halves at the median
     of their position along the main axis of the cell centres. One factor fits when the two halves agree within
     SPATIAL_AGREE (5 %) or their difference is not significant (bootstrap CI over the pass pairs of each half includes
     0); each half needs >= 10 cells and >= 3 pass pairs, else the check is not made. This is the failure Maldaner et
     al. (2016) report (the machines' difference changes over the field). On pseudo-combines with a constant factor
     the halves differ by 2.1 % (median, 90th percentile 7.2 %) and 7 % of the splits are flagged; with +5 % / -5 % in
     the two halves, about half are flagged.
  6. Per-machine totals (machines.totals_bu = {machine: wet bu}; settings file or CLI only, the app gives the field's
     ticket alone) make the relative step unnecessary: every machine is
     leveled to its own ticket, L_m = ticket_m / integral_m on the wet basis, Yld_Level = y x L_m, and
     Yld_Harm = y x (L_m / L_ref). The paired-cell estimate is then reported as a validation: agreement =
     (L_m / L_ref) / f_paired - 1, which should be within the paired CI. With only a field total the relative
     harmonisation runs first and L is computed on the harmonised integral (engine/clean/yield_clean.py).

  7. Gates on the estimate itself. A reference id whose records the cascade removed (fewer kept points than min_pairs
     x 5) falls back to the machine with the most kept points, with a warning. The validation of per-machine tickets
     (validate_totals) uses the 30 m paired estimate only where it passes the pair gate (gated()); otherwise it reports
     "no paired estimate: too few pairs" and claims no disagreement (Trial 29 with tickets for combine A and combine B only:
     combine C has 26 cells / 9 pass pairs, its ungated 1.076 is kept as paired_factor_ungated and nothing more).
  8. Ticket closure test (ticket_closure; settings machines.ticket_confirms, default true, and machines.ticket_close_tol,
     default 1 %). The field's scale ticket (settings scale_ticket) is a second, independent measure of the level.
     When a machine's paired factor was NOT applied only because |f - 1| > max_factor (its CIs exclude 1, the 30 m
     and 50 m factors agree and one factor fits the field), the monitor total of the processed set is recomputed with that factor applied: when it
     closes with the ticket within ticket_close_tol while the unharmonised total differs by more than 3 x that, the
     factor is applied with the decision "applied: the paired factor is above max_factor but the grower's weight
     confirms it (harmonised total within x % of the scale)"; otherwise nothing is applied and the decision says why.
     Reference case (tests/test_ticket.py): the 5-combine barley field, 5 GreenStar combines, ticket W lb = V bu
     at 47.99 lb/bu; the monitor total is M bu (-5.2 %); combine E reads 0.7825 against the reference (CI
     0.762-0.803, 396 cells), not applied under the 10 % gate; with it applied the total is V' bu, 0.07 % from
     the ticket -> applied; the level factor goes from 0.9481 to 1.0007. The other machines (CIs including 1) are
     unchanged.

Evidence (tests/test_aoi_sessions_machines.py, Trial 19 SMS export split into pseudo-machines with the design, pairs
on the <= 2 % overlap records: every third pass = machine B): B x 1.08 gives f30 = 0.9105 (CI 0.876-0.937, 40 cells /
8 pass pairs) and the factor is applied; B x 1.15 gives f = 0.855, not applied, with a warning;
B x 1.00 gives 0.983 with a CI including 1; alternate passes A / B x 1.00 give 1.009, not applied; 20 random pass
splits apply a factor once (the review asks for <= 1 % false positives over 200 splits; 20 is what the test suite
affords).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

CELL_SIZES_M = (30, 50)
HARM_AGREE = 0.02                        # the 30 m and 50 m factors must agree within 2 %
MIN_POINTS_PER_CELL = 5

PAIR_MAX_OVERLAP = 0.02                  # pairs are built from kept records with <= 2 % of the footprint already cut
SPATIAL_AGREE = 0.05                     # spatial check: the two halves of the contact cells agree within 5 % ...
SPATIAL_MIN_CELLS = 10                   # ... or it is not tested: each half needs >= 10 cells
SPATIAL_MIN_PASS_PAIRS = 3               # ... and >= 3 pass pairs

TICKET_CLOSE_TOL = 0.01                  # closure test: the harmonised total must be within 1 % of the ticket ...
TICKET_OPEN_MULT = 3                     # ... while the unharmonised total is more than 3 x that away

DEFAULTS = {"harmonise": True, "reference": "auto", "totals_bu": None, "min_pairs": 30, "min_pass_pairs": 5,
            "ci": 0.95, "min_factor": 0.01, "max_factor": 0.10, "same_plot_only": True, "bootstrap_reps": 1000,
            "seed": 2026, "pair_max_overlap": PAIR_MAX_OVERLAP, "ticket_confirms": True,
            "ticket_close_tol": TICKET_CLOSE_TOL, "network": True, "spatial_check": True}
EMPTY_CELLS = ["cx", "cy", "ya", "yb", "ma", "mb", "na", "nb", "pass_a", "pass_b", "log_ratio"]


# ===================================================================================================== pairs
def _mode(s: pd.Series):
    v = s.mode(dropna=True)
    return v.iloc[0] if len(v) else np.nan


def paired_cells(df: pd.DataFrame, group_col: str, a, b, size_m: float, plot_col: str | None = None,
                 min_points: int = MIN_POINTS_PER_CELL, y_col: str = "_yv", m_col: str = "_mv",
                 pass_col: str = "Pass_Id", ovl_col: str | None = "Overlap_f",
                 max_overlap: float | None = None) -> pd.DataFrame:
    """Cells of size_m (m) holding >= min_points points of group `a` AND of group `b` (df columns: _x, _y in metres,
    `group_col`, `y_col` yield, optional `m_col` moisture, `pass_col`; `plot_col` splits the cells by plot). When
    max_overlap is given and `ovl_col` is a column, only the records whose footprint share already cut is <= max_overlap
    enter the cells (the records below the F8 threshold but above it are kept in the map, yet they read 2-3 % low
    and the following pass carries them: pairing them measures the overlap, not the machine). One row per cell: cx,
    cy, [plot], ya, yb, ma, mb, na, nb, pass_a, pass_b, log_ratio = log(ya / yb); empty frame when no cell qualifies."""
    d = df[df[group_col].isin([a, b])]
    d = d[np.isfinite(d[y_col].to_numpy(float)) & (d[y_col].to_numpy(float) > 0)]
    if max_overlap is not None and ovl_col is not None and ovl_col in d:
        d = d[np.nan_to_num(d[ovl_col].to_numpy(float), nan=1.0) <= float(max_overlap)]
    if plot_col is not None and plot_col in d:
        d = d[d[plot_col].astype(str) != ""]
    if len(d) == 0:
        return pd.DataFrame(columns=EMPTY_CELLS)
    keys = {"cx": (d["_x"] // size_m).astype(int), "cy": (d["_y"] // size_m).astype(int)}
    if plot_col is not None and plot_col in d:
        keys["plot"] = d[plot_col].astype(str)
    key_cols = list(keys)
    d = d.assign(**keys)
    agg = {"y": (y_col, "mean"), "n": (y_col, "size"), "pass": (pass_col, _mode)}
    if m_col in d:
        agg["m"] = (m_col, "mean")
    s = d.groupby(key_cols + [group_col], sort=False).agg(**agg).reset_index()
    s = s[s.n >= min_points]
    if len(s) == 0:                       # no cell of either group reaches min_points: the pivot would have no 'y'
        return pd.DataFrame(columns=EMPTY_CELLS)
    w = s.pivot_table(index=key_cols, columns=group_col, values=["y", "n", "pass"] + (["m"] if "m" in s else []),
                      aggfunc="first")
    if a not in w["y"].columns or b not in w["y"].columns:
        return pd.DataFrame(columns=EMPTY_CELLS)
    out = pd.DataFrame({"ya": w["y"][a], "yb": w["y"][b], "na": w["n"][a], "nb": w["n"][b],
                        "pass_a": w["pass"][a], "pass_b": w["pass"][b]})
    if "m" in s:
        out["ma"], out["mb"] = w["m"][a], w["m"][b]
    else:
        out["ma"] = out["mb"] = np.nan
    out = out.dropna(subset=["ya", "yb"]).reset_index()
    out["log_ratio"] = np.log(out.ya / out.yb)
    return out


def ratio_estimate(cells: pd.DataFrame, reps: int = 1000, seed: int = 2026, ci: float = 0.95) -> dict:
    """Geometric-mean ratio a/b over the cells with a block bootstrap over pass pairs. Returns {n_cells, n_pass_pairs,
    factor, ci_lo, ci_hi, p_ttest, moisture_diff (b - a), excludes_one}; factor None when there is no cell."""
    n = int(len(cells))
    if n == 0:
        return {"n_cells": 0, "n_pass_pairs": 0, "factor": None, "ci_lo": None, "ci_hi": None, "p_ttest": None,
                "moisture_diff": None, "excludes_one": False}
    lr = cells.log_ratio.to_numpy(float)
    f = float(np.exp(lr.mean()))
    pp = pd.factorize(cells.pass_a.astype(str) + "|" + cells.pass_b.astype(str))[0]
    K = int(pp.max()) + 1
    sums, counts = np.bincount(pp, weights=lr, minlength=K), np.bincount(pp, minlength=K).astype(float)
    lo = hi = None
    if K >= 2 and reps > 0:
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, K, size=(int(reps), K))
        boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
        q = (1 - ci) / 2
        lo, hi = float(np.exp(np.quantile(boot, q))), float(np.exp(np.quantile(boot, 1 - q)))
    p = float(stats.ttest_rel(cells.yb, cells.ya).pvalue) if n >= 3 else None
    md = cells.mb - cells.ma
    return {"n_cells": n, "n_pass_pairs": K, "factor": f, "ci_lo": lo, "ci_hi": hi,
            "p_ttest": (None if p is None or not np.isfinite(p) else p),
            "moisture_diff": (float(md.mean()) if md.notna().any() else None),
            "excludes_one": bool(lo is not None and (lo > 1 or hi < 1))}


# ===================================================================================================== harmonisation
def _frame(g, alive, y, moi):
    cols = ["_x", "_y", "Pass_Id", "_machine"] + [c for c in ("Plot_Id", "Overlap_f") if c in g]
    kk = g.loc[alive, cols].copy()
    kk["_yv"] = np.asarray(y, float)[np.asarray(alive, bool)]
    if moi is not None:
        kk["_mv"] = np.asarray(moi, float)[np.asarray(alive, bool)]
    return kk


def machine_means(g, alive, y, moi, area_ac, ywet) -> dict:
    """Per machine: n, n_kept, area_ac (swept area of all processed readings), wet_bu (integral of the wet yield over
    that area), mass_per_area_mean (wet_bu / area_ac), moisture_mean (all readings), cleaned_map_mean (mapped yield,
    kept points). The field mean of mass per area is the integral, NOT the mean of the cleaned map."""
    out = {}
    mach = g["_machine"].astype(str).to_numpy()
    alive = np.asarray(alive, bool)
    y = np.asarray(y, float)
    area = np.nan_to_num(np.asarray(area_ac, float))
    wet = np.nan_to_num(np.asarray(ywet, float)) if ywet is not None else None
    for m in sorted(set(mach)):
        sel = mach == m
        a = float(area[sel].sum())
        wb = float((wet[sel] * area[sel]).sum()) if wet is not None else None
        yk = y[sel & alive]
        out[m] = {"n": int(sel.sum()), "n_kept": int((sel & alive).sum()), "area_ac": a, "wet_bu": wb,
                  "mass_per_area_mean": (wb / a if (wb is not None and a > 0) else None),
                  "moisture_mean": (float(np.nanmean(np.asarray(moi, float)[sel])) if moi is not None and sel.any()
                                    else None),
                  "cleaned_map_mean": (float(np.nanmean(yk)) if len(yk) else None)}
    return out


def _link_ok(est: dict, P: dict) -> bool:
    """A pair of machines is linked when its paired cells pass the pair gate (>= min_pairs cells, >= min_pass_pairs
    pass pairs and a bootstrap CI)."""
    return (est.get("factor") is not None and est.get("ci_lo") is not None and est["n_cells"] >= int(P["min_pairs"])
            and est["n_pass_pairs"] >= int(P["min_pass_pairs"]))


def _boot_means(cells: pd.DataFrame, reps: int, seed: int):
    """Bootstrap draws of the mean log ratio of a pair's cells, resampling its pass pairs (the procedure of
    ratio_estimate); None with fewer than 2 pass pairs."""
    if len(cells) == 0 or reps <= 0:
        return None
    lr = cells.log_ratio.to_numpy(float)
    pp = pd.factorize(cells.pass_a.astype(str) + "|" + cells.pass_b.astype(str))[0]
    K = int(pp.max()) + 1
    if K < 2:
        return None
    sums, counts = np.bincount(pp, weights=lr, minlength=K), np.bincount(pp, minlength=K).astype(float)
    idx = np.random.default_rng(seed).integers(0, K, size=(int(reps), K))
    return sums[idx].sum(axis=1) / counts[idx].sum(axis=1)


def network_solve(machines_: list, ref: str, links: dict, draws: dict):
    """The combine network (module docstring, item 3). u_m = log(y_ref / y_m) is the log factor of machine m, u_ref = 0.
    Every linked pair (a, b) with mean log ratio d_ab = log(y_a / y_b) over its cells observes u_b - u_a = d_ab, with
    weight 1 / (bootstrap variance of d_ab); u = the weighted least-squares solution. links: {(a, b): d_ab}; draws:
    {(a, b): bootstrap draws of d_ab}. Returns ({machine: u}, {machine: bootstrap draws of u}, {machine: weight share
    of each pair in u}), for the machines linked to the reference (directly or through other machines)."""
    adj = {m: set() for m in machines_}
    for a, b in links:
        adj[a].add(b)
        adj[b].add(a)
    seen, todo = {ref}, [ref]
    while todo:
        x = todo.pop()
        for z in adj[x] - seen:
            seen.add(z)
            todo.append(z)
    nodes = [m for m in machines_ if m in seen and m != ref]
    obs = [p for p in links if p[0] in seen and p[1] in seen]
    if not nodes:
        return {}, {}, {}
    col = {m: i for i, m in enumerate(nodes)}
    A = np.zeros((len(obs), len(nodes)))
    for r, (a, b) in enumerate(obs):
        if b in col:
            A[r, col[b]] += 1.0
        if a in col:
            A[r, col[a]] -= 1.0
    d = np.array([links[p] for p in obs], float)
    w = np.array([1.0 / max(float(np.var(draws[p], ddof=1)), 1e-12) for p in obs])
    K = np.linalg.solve(A.T @ (A * w[:, None]), (A * w[:, None]).T)        # u = K d
    u = K @ d
    reps = min(len(draws[p]) for p in obs)
    U = np.column_stack([draws[p][:reps] for p in obs]) @ K.T
    share = {m: {f"{a}|{b}": float(abs(K[col[m], r]) / max(np.abs(K[col[m]]).sum(), 1e-12)) for r, (a, b) in
                 enumerate(obs) if abs(K[col[m], r]) > 1e-9} for m in nodes}
    return {m: float(u[col[m]]) for m in nodes}, {m: U[:, col[m]] for m in nodes}, share


def spatial_check(cell_sets: list, size_m: float, reps: int, seed: int) -> dict:
    """The spatial consistency of one machine's factor (module docstring, item 5). cell_sets: [(cells, offset, sign)]
    of the linked pairs of the machine: every cell estimates the machine's log factor as offset + sign x log_ratio
    (the partner's log factor plus the cell's ratio). The cells are split in two halves at the median of their
    position along the main axis of the cell centres; the factor of each half (geometric mean of its cells), their
    difference and its CI by a bootstrap over the pass pairs of each half. Inconsistent when the halves differ by more
    than SPATIAL_AGREE and the CI of the difference excludes 0; not tested with fewer than SPATIAL_MIN_CELLS cells or
    SPATIAL_MIN_PASS_PAIRS pass pairs in a half."""
    parts = []
    for i, (c, off, sgn) in enumerate(cell_sets):
        if c is None or len(c) == 0:
            continue
        parts.append(pd.DataFrame({"x": (c.cx.to_numpy(float) + 0.5) * size_m, "y": (c.cy.to_numpy(float) + 0.5) * size_m,
                                   "e": off + sgn * c.log_ratio.to_numpy(float),
                                   "pp": f"{i}|" + c.pass_a.astype(str) + "|" + c.pass_b.astype(str)}))
    out = {"tested": False, "tolerance": SPATIAL_AGREE, "cell_m": size_m, "consistent": None}
    if not parts:
        return out
    e = pd.concat(parts, ignore_index=True)
    X = e[["x", "y"]].to_numpy(float)
    Xc = X - X.mean(axis=0)
    axis = np.linalg.svd(Xc, full_matrices=False)[2][0] if len(e) > 1 else np.array([1.0, 0.0])
    s = Xc @ axis
    second = s > np.median(s)
    halves, rng = [], np.random.default_rng(seed)
    for sel in (~second, second):
        h = e[sel]
        pp = pd.factorize(h.pp)[0]
        K = int(pp.max()) + 1 if len(h) else 0
        halves.append((h, pp, K))
    out.update(n_cells=[int(len(h)) for h, _, _ in halves], n_pass_pairs=[int(K) for _, _, K in halves],
               axis=[float(axis[0]), float(axis[1])])
    if min(out["n_cells"]) < SPATIAL_MIN_CELLS or min(out["n_pass_pairs"]) < SPATIAL_MIN_PASS_PAIRS:
        return out
    boots, means = [], []
    for h, pp, K in halves:
        v = h.e.to_numpy(float)
        means.append(float(v.mean()))
        sums, cnt = np.bincount(pp, weights=v, minlength=K), np.bincount(pp, minlength=K).astype(float)
        idx = rng.integers(0, K, size=(int(reps), K))
        boots.append(sums[idx].sum(axis=1) / cnt[idx].sum(axis=1))
    diff = means[1] - means[0]
    lo, hi = np.quantile(boots[1] - boots[0], [0.025, 0.975]) if reps > 0 else (np.nan, np.nan)
    excl = bool(np.isfinite(lo) and (lo > 0 or hi < 0))
    pct = float(np.exp(diff) - 1)
    out.update(tested=True, factor_half_1=float(np.exp(means[0])), factor_half_2=float(np.exp(means[1])),
               diff_pct=100 * pct, ci_pct=[100 * float(np.exp(lo) - 1), 100 * float(np.exp(hi) - 1)],
               ci_excludes_0=excl, consistent=not (abs(pct) > SPATIAL_AGREE and excl))
    return out


def harmonise(g, alive, y, moi, Mset: dict, warnings: list | None = None, info: dict | None = None):
    """The harmonisation of the module docstring. g: processed frame with _x, _y (m), Pass_Id, _machine and, when a
    plan exists, Plot_Id; alive: kept mask; y: mapped yield; moi: moisture or None; Mset: the settings["machines"]
    dict; info (optional dict) receives the pairs, the estimate (direct or network) and the machines with no link to
    the reference. Returns (tests, applied, decision, reference): tests = list of per machine per cell size dicts,
    applied = {machine: factor}, decision = {machine: text}."""
    warnings = [] if warnings is None else warnings
    info = {} if info is None else info
    P = {**DEFAULTS, **(Mset or {})}
    machines_ = sorted(g["_machine"].astype(str).unique())
    kept_by = pd.Series(np.asarray(alive, bool)).groupby(g["_machine"].astype(str).values).sum()
    ref = P["reference"]
    if ref in (None, "auto"):
        ref = str(kept_by.idxmax())
    else:
        ref = str(ref)
        if ref not in machines_:
            warnings.append(f"machines.reference {ref!r} is not a value of the machine column ({machines_}): the "
                            "machine with the most kept points is the reference")
            ref = str(kept_by.idxmax())
        elif int(kept_by.get(ref, 0)) < int(P["min_pairs"]) * MIN_POINTS_PER_CELL:
            # a reference whose records the cascade removed (or nearly all of them) can pair with nothing: every other
            # machine would read "too few pairs" without a word on the cause
            best = str(kept_by.idxmax())
            warnings.append(f"machines.reference {ref!r} has {int(kept_by.get(ref, 0)):,} kept points (fewer than "
                            f"{int(P['min_pairs']) * MIN_POINTS_PER_CELL} = min_pairs x {MIN_POINTS_PER_CELL} points per "
                            f"cell): the machine with the most kept points ({best}, {int(kept_by[best]):,}) is the "
                            "reference")
            ref = best
    kk = _frame(g, alive, y, moi)
    plot_col = "Plot_Id" if (P["same_plot_only"] and "Plot_Id" in kk and (kk["Plot_Id"].astype(str) != "").any()) \
        else None
    max_ovl = P.get("pair_max_overlap")
    max_ovl = float(max_ovl) if (max_ovl is not None and "Overlap_f" in kk) else None
    share_ovl = {}
    if max_ovl is not None:
        ov = np.nan_to_num(kk["Overlap_f"].to_numpy(float), nan=1.0) > max_ovl
        share_ovl = pd.Series(ov).groupby(kk["_machine"].astype(str).values).mean().to_dict()
    reps, seed, ci = int(P["bootstrap_reps"]), int(P["seed"]), float(P["ci"])
    # every pair of machines: the paired cells and the ratio at both cell sizes; a pair with the reference is oriented
    # (reference, machine), so its factor is the direct reference / machine estimate
    others = [m for m in machines_ if m != ref]
    pairs = [(ref, m) for m in others] + [(a, b) for i, a in enumerate(others) for b in others[i + 1:]]
    pc = {p: {s: paired_cells(kk, "_machine", p[0], p[1], s, plot_col=plot_col, max_overlap=max_ovl)
              for s in CELL_SIZES_M} for p in pairs}
    pe = {p: {s: ratio_estimate(pc[p][s], reps=reps, seed=seed, ci=ci) for s in CELL_SIZES_M} for p in pairs}
    linked = [p for p in pairs if all(_link_ok(pe[p][s], P) for s in CELL_SIZES_M)]
    # the direct estimate when every link touches the reference (two machines always); else the network
    network = bool(P.get("network", True)) and any(ref not in p for p in linked)
    est, via, sets30 = {m: {} for m in others}, {m: [] for m in others}, {m: [] for m in others}
    if network:
        for s in CELL_SIZES_M:
            links = {p: float(np.log(pe[p][s]["factor"])) for p in linked}
            draws = {p: _boot_means(pc[p][s], reps, seed + 7919 * (k + 1)) for k, p in enumerate(linked)}
            u, U, share = network_solve(machines_, ref, links, draws)
            q = (1 - ci) / 2
            for m, um in u.items():
                mine = [p for p in linked if m in p]
                lo, hi = float(np.exp(np.quantile(U[m], q))), float(np.exp(np.quantile(U[m], 1 - q)))
                d = pe.get((ref, m), {}).get(s) or {}
                est[m][s] = {"n_cells": int(sum(pe[p][s]["n_cells"] for p in mine)),
                             "n_pass_pairs": int(sum(pe[p][s]["n_pass_pairs"] for p in mine)),
                             "factor": float(np.exp(um)), "ci_lo": lo, "ci_hi": hi, "p_ttest": d.get("p_ttest"),
                             "moisture_diff": d.get("moisture_diff"), "excludes_one": bool(lo > 1 or hi < 1),
                             "estimate": "network", "pair_weights": share[m],
                             "direct_factor": d.get("factor") if (ref, m) in linked else None}
                if s == CELL_SIZES_M[0]:
                    via[m] = sorted(p[0] if p[1] == m else p[1] for p in mine)
                    sets30[m] = [(pc[p][s], (0.0 if p[0] == ref else u[p[0]]), 1.0) if p[1] == m else
                                 (pc[p][s], (0.0 if p[1] == ref else u[p[1]]), -1.0) for p in mine]
    for m in others:
        for s in CELL_SIZES_M:
            if s not in est[m]:                      # the direct estimate (or the unlinked machine's own pair)
                est[m][s] = dict(pe[(ref, m)][s], estimate="direct")
        if not sets30[m]:
            sets30[m] = [(pc[(ref, m)][CELL_SIZES_M[0]], 0.0, 1.0)]
            via[m] = [ref] if (ref, m) in linked else []
    info.update(reference=ref, estimate="network" if network else "direct",
                pairs=[{"a": p[0], "b": p[1], "cell_m": s, "n_cells": pe[p][s]["n_cells"],
                        "n_pass_pairs": pe[p][s]["n_pass_pairs"], "factor_a_over_b": pe[p][s]["factor"],
                        "ci_lo": pe[p][s]["ci_lo"], "ci_hi": pe[p][s]["ci_hi"], "linked": p in linked}
                       for p in pairs for s in CELL_SIZES_M],
                unlinked=[m for m in others if est[m][CELL_SIZES_M[0]].get("estimate") == "direct" and network
                          or (not network and (ref, m) not in linked)])
    tests, applied, decision = [], {}, {}
    for m in machines_:
        if m == ref:
            applied[m], decision[m] = 1.0, "reference"
            continue
        e30, e50 = est[m][CELL_SIZES_M[0]], est[m][CELL_SIZES_M[1]]
        for s, e in ((CELL_SIZES_M[0], e30), (CELL_SIZES_M[1], e50)):
            e.update(machine=m, cell_m=s, same_plot_only=plot_col is not None, max_overlap=max_ovl, via=via[m],
                     share_overlapped=(float(share_ovl.get(m, 0.0)) if max_ovl is not None else None),
                     share_overlapped_ref=(float(share_ovl.get(ref, 0.0)) if max_ovl is not None else None))
            tests.append(e)
        if network:
            enough = e30.get("estimate") == "network"
        else:
            enough = all(e["n_cells"] >= P["min_pairs"] and e["n_pass_pairs"] >= P["min_pass_pairs"] for e in (e30, e50))
        if enough and P.get("spatial_check", True):
            e30["spatial"] = spatial_check(sets30[m], CELL_SIZES_M[0], reps, seed)
        f30, f50 = e30["factor"], e50["factor"]
        # gate: why the factor was (not) applied, as a key the ticket closure test can read ("above_max_factor" is the
        # only case it reconsiders: the estimate is significant and consistent, only its size is beyond the gate)
        if not enough:
            applied[m] = 1.0
            if network:
                decision[m] = (f"not applied: no link to the reference {ref} (no chain of neighbouring machines with >= "
                               f"{P['min_pairs']} cells and >= {P['min_pass_pairs']} pass pairs at both cell sizes; "
                               f"{e30['n_cells']} cells / {e30['n_pass_pairs']} pass pairs with {ref} at 30 m)")
                gate = "no_link"
            else:
                decision[m] = (f"not applied: too few pairs ({e30['n_cells']} cells / {e30['n_pass_pairs']} pass pairs "
                               f"at 30 m, {e50['n_cells']} / {e50['n_pass_pairs']} at 50 m; need >= {P['min_pairs']} "
                               f"cells and >= {P['min_pass_pairs']} pass pairs)")
                gate = "too_few_pairs"
            for e in (e30, e50):
                e["gate"] = gate
            continue
        both_sig = e30["excludes_one"] and e50["excludes_one"]
        agree = abs(f30 / f50 - 1) <= HARM_AGREE
        eff = abs(f30 - 1)
        sp = e30.get("spatial") or {}
        if eff > P["max_factor"]:
            applied[m] = 1.0
            # the closure test reconsiders the step only when it is significant and consistent across cell sizes and
            # over the field; otherwise the decision says why a grower's weight cannot confirm it
            unconfirmed = unconfirmed_reason(e30, e50)
            decision[m] = (f"not applied: |factor - 1| = {100 * eff:.1f} % is above machines.max_factor "
                           f"({100 * P['max_factor']:.0f} %)"
                           + (f" and {unconfirmed}, so a grower's weight is not used to confirm it" if unconfirmed else
                              " (a grower's weight for the field can confirm it: the ticket closure test)"))
            warnings.append(f"machine {m}: the paired cells put it {100 * (1 / f30 - 1):+.1f} % against {ref} "
                            f"(factor {f30:.4f}, CI {e30['ci_lo']:.4f}-{e30['ci_hi']:.4f}), more than the "
                            f"{100 * P['max_factor']:.0f} % a relative factor should repair: no harmonisation applied "
                            "unless the field's scale ticket confirms it; check the monitor's calibration")
            gate = "above_max_factor" if not unconfirmed else "above_max_factor_unconfirmed"
        elif not both_sig:
            applied[m] = 1.0
            decision[m] = (f"not applied: the {int(100 * P['ci'])} % bootstrap CI includes 1 at "
                           + (" and ".join(f"{s} m" for s, e in ((CELL_SIZES_M[0], e30), (CELL_SIZES_M[1], e50))
                                           if not e["excludes_one"])))
            gate = "ci_includes_1"
        elif not agree:
            applied[m] = 1.0
            decision[m] = f"not applied: 30 m and 50 m factors disagree ({f30:.4f} vs {f50:.4f}, > {HARM_AGREE:.0%})"
            warnings.append(f"machine {m}: significant but the 30 m and 50 m factors disagree ({f30:.4f} vs {f50:.4f}); "
                            "no harmonisation applied - check the machines' calibration")
            gate = "sizes_disagree"
        elif eff <= P["min_factor"]:
            applied[m] = 1.0
            decision[m] = f"not applied: |factor - 1| = {100 * eff:.2f} % <= machines.min_factor ({100 * P['min_factor']:.0f} %)"
            gate = "below_min_factor"
        elif sp.get("consistent") is False:
            applied[m] = 1.0
            decision[m] = (f"not applied: the factor differs over the field (halves {sp['factor_half_1']:.4f} and "
                           f"{sp['factor_half_2']:.4f}, {sp['diff_pct']:+.1f} %, more than {100 * SPATIAL_AGREE:.0f} % "
                           "and significant): one factor does not fit the whole field")
            warnings.append(f"machine {m}: its difference to the other combines changes over the field (the two halves "
                            f"of its contact cells read {sp['factor_half_1']:.4f} and {sp['factor_half_2']:.4f}): no "
                            "harmonisation applied")
            gate = "spatially_inconsistent"
        else:
            applied[m] = float(f30)
            decision[m] = (f"applied (30 m factor {f30:.4f}, CI {e30['ci_lo']:.4f}-{e30['ci_hi']:.4f}, "
                           f"{e30['n_cells']} cells / {e30['n_pass_pairs']} pass pairs"
                           + (f", network through {', '.join(via[m])}" if e30.get("estimate") == "network" else "")
                           + ")")
            gate = "applied"
        for e in (e30, e50):
            e["gate"] = gate
    return tests, applied, decision, ref


def unconfirmed_reason(e30: dict, e50: dict) -> str | None:
    """Why a paired factor above max_factor is NOT a candidate for the ticket closure test: the CI includes 1 at one
    of the cell sizes, the 30 m and 50 m factors disagree by more than HARM_AGREE, or the factor differs over the
    field (spatial_check). None when it is a candidate (significant at both sizes, consistent)."""
    not_sig = [s for s, e in ((CELL_SIZES_M[0], e30), (CELL_SIZES_M[1], e50)) if not e.get("excludes_one")]
    if not_sig:
        return "the bootstrap CI includes 1 at " + " and ".join(f"{s} m" for s in not_sig)
    f30, f50 = e30.get("factor"), e50.get("factor")
    if f30 and f50 and abs(f30 / f50 - 1) > HARM_AGREE:
        return f"the 30 m and 50 m factors disagree ({f30:.4f} vs {f50:.4f}, > {HARM_AGREE:.0%})"
    sp = e30.get("spatial") or {}
    if sp.get("consistent") is False:
        return (f"the factor differs over the field (halves {sp['factor_half_1']:.4f} and {sp['factor_half_2']:.4f}, "
                f"{sp['diff_pct']:+.1f} %)")
    return None


def ticket_closure(tests: list, applied: dict, decision: dict, ref: str, Mset: dict | None, integrals: dict,
                   ticket_bu: float | None, warnings: list | None = None, notes: list | None = None) -> dict | None:
    """The ticket closure test of the module docstring (item 8). tests / applied / decision / ref: the output of
    harmonise(); integrals: {machine: monitor total in bu of its processed readings, on the ticket's basis};
    ticket_bu: the field's scale ticket in bu on the same basis. Candidates are the machines whose 30 m test carries
    gate == "above_max_factor". The candidates are tried together and, when that does not close, one at a time.
    When the total with the factor(s) applied is within ticket_close_tol of the ticket while the total without them is
    more than TICKET_OPEN_MULT x that away, `applied` and `decision` are updated IN PLACE, the "request per-machine
    weights" warning of the confirmed machine(s) is withdrawn and a note is added. Returns the ticket_test dict
    {ticket_bu, tolerance, candidates, without: {total_bu, diff_pct}, with: {total_bu, diff_pct}, applied, machines,
    rule, verdict}, or None when there is no ticket or no monitor total."""
    warnings = [] if warnings is None else warnings
    notes = [] if notes is None else notes
    P = {**DEFAULTS, **(Mset or {})}
    tol = float(P["ticket_close_tol"])
    if not ticket_bu or ticket_bu <= 0 or not integrals:
        return None
    integ = {str(m): float(v or 0.0) for m, v in integrals.items()}
    f30 = {t["machine"]: t for t in tests if t.get("cell_m") == CELL_SIZES_M[0]}
    f50 = {t["machine"]: t for t in tests if t.get("cell_m") == CELL_SIZES_M[1]}
    cands = sorted(m for m, t in f30.items() if t.get("gate") == "above_max_factor" and t.get("factor"))

    def total(extra):
        return float(sum(integ[m] * float(extra.get(m, applied.get(m, 1.0))) for m in integ))

    without = total({})
    if without <= 0:
        return None
    d0 = without / ticket_bu - 1
    rule = (f"a paired factor above max_factor ({100 * P['max_factor']:.0f} %) is applied when the monitor total with it "
            f"is within {100 * tol:g} % of the grower's weight while the total without it is more than "
            f"{100 * TICKET_OPEN_MULT * tol:g} % away; a factor above max_factor whose CI includes 1 at one cell size "
            f"or whose 30 m / 50 m estimates disagree is not a candidate")
    # the factors above max_factor the weight is not allowed to confirm, with the reason (the same the decision gives)
    rejected = {}
    for m, t in sorted(f30.items()):
        if t.get("gate") == "above_max_factor_unconfirmed" and t.get("factor") and m in integ:
            why = unconfirmed_reason(t, f50.get(m) or {}) or "the estimate is not confirmed at both cell sizes"
            w_m = total({m: float(t["factor"])})
            d_m = w_m / ticket_bu - 1
            rejected[m] = {"factor": float(t["factor"]), "reason": why, "with_total_bu": w_m, "with_diff_pct": 100 * d_m,
                           # the weight sits nearer this machine's level than the reference's when applying the
                           # factor (which moves the other machines towards the reference) opens the gap further
                           "weight_nearer_this_machine": bool(abs(d0) > TICKET_OPEN_MULT * tol and abs(d_m) > abs(d0))}
    res = {"ticket_bu": float(ticket_bu), "tolerance": tol, "candidates": cands, "reference": ref,
           "without": {"total_bu": without, "diff_pct": 100 * d0}, "with": None, "applied": False, "machines": [],
           "rejected": rejected, "rule": rule, "verdict": ""}
    if not cands:
        res["with"] = dict(res["without"])
        if rejected:
            parts = [f"candidate {m} rejected: {r['reason']} (30 m factor {r['factor']:.4f}; with it the monitor total "
                     f"would be {r['with_diff_pct']:+.1f} % from the weight)" for m, r in rejected.items()]
            hint = [m for m, r in rejected.items() if r["weight_nearer_this_machine"]]
            res["verdict"] = ("no paired factor the grower's weight may confirm: " + "; ".join(parts)
                              + f"; the weight is {100 * (ticket_bu / without - 1):+.1f} % from the monitor total"
                              + (f" and sits nearer {', '.join(hint)}'s level than the reference {ref}'s: try "
                                 f"machines.reference = {hint[0]}" if hint else "")
                              + "; check the monitors' calibration")
        else:
            res["verdict"] = "no paired factor above max_factor to test against the grower's weight"
        return res
    trials = [cands] + ([[m] for m in cands] if len(cands) > 1 else [])
    chosen, with_total = None, None
    for sel in trials:
        w = total({m: f30[m]["factor"] for m in sel})
        d = w / ticket_bu - 1
        if with_total is None:
            with_total, d_all = w, d                 # the joint result is what is reported when nothing closes
        if abs(d) <= tol and abs(d0) > TICKET_OPEN_MULT * tol:
            chosen, with_total, d_all = sel, w, d
            break
    res["with"] = {"total_bu": with_total, "diff_pct": 100 * d_all}
    if chosen:
        res["applied"], res["machines"] = True, list(chosen)
        for m in chosen:
            t = f30[m]
            applied[m] = float(t["factor"])
            decision[m] = (f"applied: the paired factor is above max_factor but the grower's weight confirms it "
                           f"(harmonised total within {100 * abs(d_all):.2f} % of the scale); 30 m factor "
                           f"{t['factor']:.4f}, CI {t['ci_lo']:.4f}-{t['ci_hi']:.4f}, {t['n_cells']} cells / "
                           f"{t['n_pass_pairs']} pass pairs")
            warnings[:] = [w_ for w_ in warnings
                           if not (w_.startswith(f"machine {m}:") and "a relative factor should repair" in w_)]
        res["verdict"] = (f"the monitor total is {100 * d0:+.1f} % from the grower's weight without the factor and "
                          f"{100 * d_all:+.2f} % with it: the paired factor of {', '.join(chosen)} is confirmed and "
                          "applied")
        notes.append(f"machines: {res['verdict']} (ticket closure test, tolerance {100 * tol:g} %)")
    else:
        if abs(d0) <= TICKET_OPEN_MULT * tol:
            why = (f"the monitor total already agrees with the grower's weight ({100 * d0:+.1f} %, within "
                   f"{100 * TICKET_OPEN_MULT * tol:g} %), so the weight cannot confirm a {100 * (1 - f30[cands[0]]['factor']):+.0f} % step")
        else:
            why = (f"with the factor the monitor total is {100 * d_all:+.1f} % from the grower's weight (without it "
                   f"{100 * d0:+.1f} %), not within {100 * tol:g} %")
        res["verdict"] = f"not confirmed: {why}; the factor stays unapplied, check the monitor's calibration"
        for m in cands:
            decision[m] += f"; the grower's weight does not confirm it ({why})"
    return res


def gated(test: dict | None, Mset: dict | None = None) -> bool:
    """True when a paired-cell test passes the pair gate (>= min_pairs cells, >= min_pass_pairs pass pairs, a CI):
    only such an estimate is used for a decision or a validation."""
    if not test or test.get("factor") is None or test.get("ci_lo") is None:
        return False
    P = {**DEFAULTS, **(Mset or {})}
    return test["n_cells"] >= int(P["min_pairs"]) and test["n_pass_pairs"] >= int(P["min_pass_pairs"])


def method_text(P: dict) -> str:
    P = {**DEFAULTS, **(P or {})}
    ov = P.get("pair_max_overlap")
    ov_txt = (f" with <= {100 * float(ov):g} % of the footprint already cut" if ov is not None else "")
    return (f"geometric-mean ratio between two machines over paired {CELL_SIZES_M[0]} m and {CELL_SIZES_M[1]} m cells "
            f"with >= {MIN_POINTS_PER_CELL} kept points{ov_txt} of both (same plot when a plan exists), CI by block "
            f"bootstrap over pass pairs ({P['bootstrap_reps']} reps); "
            + ("every pair of machines that harvested side by side (>= "
               f"{P['min_pairs']} cells and >= {P['min_pass_pairs']} pass pairs at both sizes) enters one weighted "
               "least-squares solution of the log factors with the reference at 1, so a machine is linked to the "
               "reference directly or through its neighbours; " if P.get("network", True) else
               f"each machine against the reference (>= {P['min_pairs']} cells and >= {P['min_pass_pairs']} pass pairs "
               "at both sizes); ")
            + f"the 30 m factor is applied only if both {int(100 * P['ci'])} % CIs exclude 1, the two factors agree "
            f"within {HARM_AGREE:.0%} and {100 * P['min_factor']:g} % < |factor - 1| <= {100 * P['max_factor']:g} %"
            + (f", and one factor fits the whole field (the two halves of the machine's contact cells within "
               f"{100 * SPATIAL_AGREE:g} % or not significantly different)" if P.get("spatial_check", True) else "")
            + "; paired t-test p and moisture difference are diagnostics"
            + (f"; a significant, consistent factor above {100 * P['max_factor']:g} % is still applied when the grower's "
               f"weight confirms it (monitor total with the factor within {100 * float(P['ticket_close_tol']):g} % of the "
               f"scale, without it more than {100 * TICKET_OPEN_MULT * float(P['ticket_close_tol']):g} % away)"
               if P.get("ticket_confirms", True) else ""))


# ===================================================================================================== totals
def per_machine_levels(totals: dict, means: dict, ref: str, warnings: list) -> dict | None:
    """L_m = ticket_m / wet integral_m per machine from machines.totals_bu. Machines without a ticket get the
    reference's L (warning). Returns {machine: {ticket_bu, integral_bu, L, relative_to_ref}} or None when the
    reference has no usable integral."""
    out = {}
    tk = {str(k): float(v) for k, v in (totals or {}).items()}
    unknown = sorted(set(tk) - set(means))
    if unknown:
        warnings.append(f"machines.totals_bu names machine(s) {unknown} that are not in the machine column "
                        f"({sorted(means)}): ignored")
    for m, mm in means.items():
        integ = mm.get("wet_bu")
        if m in tk and integ and integ > 0:
            out[m] = {"ticket_bu": tk[m], "integral_bu": integ, "L": tk[m] / integ}
        else:
            out[m] = {"ticket_bu": tk.get(m), "integral_bu": integ, "L": None}
    if out.get(ref, {}).get("L") is None:
        warnings.append(f"no usable scale ticket for the reference machine {ref!r} in machines.totals_bu: per-machine "
                        "leveling not possible")
        return None
    Lref = out[ref]["L"]
    for m, d in out.items():
        if d["L"] is None:
            d["L"] = Lref
            d["note"] = "no ticket for this machine: the reference's L is used"
            warnings.append(f"machine {m}: no entry in machines.totals_bu; leveled with the reference's L ({Lref:.4f})")
        d["relative_to_ref"] = d["L"] / Lref
    return out


def validate_totals(levels: dict, tests: list, ref: str, Mset: dict | None = None) -> dict:
    """Agreement between the per-ticket relative level (L_m / L_ref) and the paired-cell factor at 30 m:
    agreement = (L_m / L_ref) / f_paired - 1 per machine, with whether the ticket ratio falls inside the paired CI.
    Only a GATED paired estimate (gated(): >= min_pairs cells, >= min_pass_pairs pass pairs, a bootstrap CI) is used;
    otherwise paired_factor / agreement / inside_paired_ci are None and 'note' says why (an estimate the method itself
    calls unusable must not read as a disagreement with a correct ticket)."""
    out = {}
    P = {**DEFAULTS, **(Mset or {})}
    for m, d in levels.items():
        if m == ref:
            continue
        t30 = next((t for t in tests if t["machine"] == m and t["cell_m"] == 30), None)
        if not gated(t30, Mset):
            why = ("no paired-cell test" if t30 is None or t30.get("factor") is None else
                   f"too few pairs ({t30['n_cells']} cells / {t30['n_pass_pairs']} pass pairs at 30 m; need >= "
                   f"{int(P['min_pairs'])} and >= {int(P['min_pass_pairs'])})")
            out[m] = {"ticket_ratio": d["relative_to_ref"], "paired_factor": None, "paired_ci": None, "agreement": None,
                      "inside_paired_ci": None, "note": f"no paired estimate: {why}",
                      "paired_factor_ungated": (t30.get("factor") if t30 else None)}
            continue
        agree = d["relative_to_ref"] / t30["factor"] - 1
        inside = t30["ci_lo"] <= d["relative_to_ref"] <= t30["ci_hi"]
        out[m] = {"ticket_ratio": d["relative_to_ref"], "paired_factor": t30["factor"], "paired_ci": [t30["ci_lo"],
                  t30["ci_hi"]], "agreement": float(agree), "inside_paired_ci": bool(inside)}
    return out
