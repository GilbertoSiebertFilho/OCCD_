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
curve sees a step wherever the machines meet. Maldaner et al. (2016) take the machine with the largest harvested area
as the reference and apply one factor per machine from adjacent passes or nearest-point pairs; Chiocco & Wuestefeld
(2019) search a +/-10 % gain on nearest positions across adjacent paths and note that harmonisation fixes consistency,
not level. Neither gives a significance or materiality gate: the gates below are a house method. This module is the
v2 rule of Section 4.14 of the literature review.

Method (the v2 rule; the numbers are house conventions unless cited)
  1. Reference = the machine with the most kept points (machines.reference "auto") or the id given.
  2. Pairs. The kept points with <= pair_max_overlap (2 %, PAIR_MAX_OVERLAP) of their footprint already cut are
     binned into 30 m and 50 m square cells; a cell is a pair when BOTH machines have >= 5 such points in it (so the
     two machines cut neighbouring passes of the same, uncut ground). The overlap rule is needed because the pass that
     follows another carries the overlap below the F8 threshold and its kept records read 2-3 % low (Trial 19: the
     2-5 % band is -2.4 % against the no-overlap band): pairing every kept record of two combines that work side by
     side measures that overlap, not the machines (Trial 19 with alternate passes labelled A / B and no yield change:
     factor 1.029, CI 1.008-1.049, "applied" on every kept record; 1.009 with the rule). The 2 % edge is the 0-2 %
     band, which reads within 0.2 % of the no-overlap band (house rule). When a plan with plots
     exists and machines.same_plot_only, the cells are also split by Plot_Id, so a pair always compares the same
     treatment (the rate effect cannot enter the factor). Every cell carries its pass pair (the modal Pass_Id of each
     machine in the cell). A machine needs >= min_pairs (30) cells at BOTH sizes and >= min_pass_pairs (5) distinct
     pass pairs: fewer, and no factor is estimated.
  3. Estimate f_m = exp(mean(log(y_ref / y_m))) over the cells (the geometric-mean ratio: a multiplicative level
     error is symmetric in log space), separately at 30 m and 50 m. CI by a block bootstrap over PASS PAIRS
     (bootstrap_reps resamples of the pass pairs with replacement, the cells of a pass pair move together; seed
     fixed): neighbouring cells of one pass pair are not independent, so a cell-level test would overstate the
     precision. The old paired t-test p over cells is kept as a
     diagnostic ("p_ttest"), as is the mean moisture difference on the same pairs ("moisture_diff", m - ref): a
     level difference that comes with a moisture difference may be a moisture-sensor difference.
  4. The 30 m factor is applied (new column Yld_Harm = y x f) only if: both CIs exclude 1, |f30 / f50 - 1| <= 2 %
     (the factor must not depend on the cell size), and min_factor (1 %) < |f - 1| <= max_factor (10 %). Above
     max_factor nothing is applied and the result warns "request per-machine weights": a > 10 % step is beyond what a
     relative factor should repair (Chiocco & Wuestefeld 2019 bound their search at +/-10 %) and needs the machine's
     own weighed total. Below min_factor the step is inside the calibration noise.
  5. Per-machine totals (machines.totals_bu = {machine: wet bu}) make the relative step unnecessary: every machine is
     leveled to its own ticket, L_m = ticket_m / integral_m on the wet basis, Yld_Level = y x L_m, and
     Yld_Harm = y x (L_m / L_ref). The paired-cell estimate is then reported as a validation: agreement =
     (L_m / L_ref) / f_paired - 1, which should be within the paired CI. With only a field total the relative
     harmonisation runs first and L is computed on the harmonised integral (engine/clean/yield_clean.py).

  6. Gates on the estimate itself. A reference id whose records the cascade removed (fewer kept points than min_pairs
     x 5) falls back to the machine with the most kept points, with a warning. The validation of per-machine tickets
     (validate_totals) uses the 30 m paired estimate only where it passes the pair gate (gated()); otherwise it reports
     "no paired estimate: too few pairs" and claims no disagreement (Trial 29 with tickets for combine A and combine B only:
     combine C has 26 cells / 9 pass pairs, its ungated 1.076 is kept as paired_factor_ungated and nothing more).
  7. Ticket closure test (ticket_closure; settings machines.ticket_confirms, default true, and machines.ticket_close_tol,
     default 1 %). The field's scale ticket (settings scale_ticket) is a second, independent measure of the level.
     When a machine's paired factor was NOT applied only because |f - 1| > max_factor (its CIs exclude 1 and the 30 m
     and 50 m factors agree), the monitor total of the processed set is recomputed with that factor applied: when it
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
8 pass pairs) and the factor is applied; B x 1.15 gives f = 0.855, not applied, with the per-machine-weights warning;
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

TICKET_CLOSE_TOL = 0.01                  # closure test: the harmonised total must be within 1 % of the ticket ...
TICKET_OPEN_MULT = 3                     # ... while the unharmonised total is more than 3 x that away

DEFAULTS = {"harmonise": True, "reference": "auto", "totals_bu": None, "min_pairs": 30, "min_pass_pairs": 5,
            "ci": 0.95, "min_factor": 0.01, "max_factor": 0.10, "same_plot_only": True, "bootstrap_reps": 1000,
            "seed": 2026, "pair_max_overlap": PAIR_MAX_OVERLAP, "ticket_confirms": True,
            "ticket_close_tol": TICKET_CLOSE_TOL}
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


def harmonise(g, alive, y, moi, Mset: dict, warnings: list | None = None):
    """The paired-cell harmonisation of the module docstring. g: processed frame with _x, _y (m), Pass_Id, _machine
    and, when a plan exists, Plot_Id; alive: kept mask; y: mapped yield; moi: moisture or None; Mset: the
    settings["machines"] dict. Returns (tests, applied, decision, reference): tests = list of per machine per cell
    size dicts, applied = {machine: factor}, decision = {machine: text}."""
    warnings = [] if warnings is None else warnings
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
    tests, applied, decision = [], {}, {}
    for m in machines_:
        if m == ref:
            applied[m], decision[m] = 1.0, "reference"
            continue
        est = {}
        for size in CELL_SIZES_M:
            cells = paired_cells(kk, "_machine", ref, m, size, plot_col=plot_col, max_overlap=max_ovl)
            e = ratio_estimate(cells, reps=int(P["bootstrap_reps"]), seed=int(P["seed"]), ci=float(P["ci"]))
            e.update(machine=m, cell_m=size, same_plot_only=plot_col is not None, max_overlap=max_ovl,
                     share_overlapped=(float(share_ovl.get(m, 0.0)) if max_ovl is not None else None),
                     share_overlapped_ref=(float(share_ovl.get(ref, 0.0)) if max_ovl is not None else None))
            tests.append(e)
            est[size] = e
        e30, e50 = est[30], est[50]
        enough = all(e["n_cells"] >= P["min_pairs"] and e["n_pass_pairs"] >= P["min_pass_pairs"] for e in est.values())
        f30, f50 = e30["factor"], e50["factor"]
        # gate: why the factor was (not) applied, as a key the ticket closure test can read ("above_max_factor" is the
        # only case it reconsiders: the estimate is significant and consistent, only its size is beyond the gate)
        if not enough:
            applied[m] = 1.0
            decision[m] = (f"not applied: too few pairs ({e30['n_cells']} cells / {e30['n_pass_pairs']} pass pairs at "
                           f"30 m, {e50['n_cells']} / {e50['n_pass_pairs']} at 50 m; need >= {P['min_pairs']} cells "
                           f"and >= {P['min_pass_pairs']} pass pairs)")
            gate = "too_few_pairs"
            for e in est.values():
                e["gate"] = gate
            continue
        both_sig = e30["excludes_one"] and e50["excludes_one"]
        agree = abs(f30 / f50 - 1) <= HARM_AGREE
        eff = abs(f30 - 1)
        if eff > P["max_factor"]:
            applied[m] = 1.0
            # the closure test reconsiders the step only when it is significant and consistent across cell sizes;
            # otherwise the decision says why a grower's weight cannot confirm it (the ticket test repeats the reason)
            unconfirmed = unconfirmed_reason(e30, e50)
            decision[m] = (f"not applied: |factor - 1| = {100 * eff:.1f} % is above machines.max_factor "
                           f"({100 * P['max_factor']:.0f} %)"
                           + (f" and {unconfirmed}, so a grower's weight is not used to confirm it" if unconfirmed else
                              " (a grower's weight for the field can confirm it: the ticket closure test)")
                           + "; request per-machine weights")
            warnings.append(f"machine {m}: the paired cells put it {100 * (1 / f30 - 1):+.1f} % against {ref} "
                            f"(factor {f30:.4f}, CI {e30['ci_lo']:.4f}-{e30['ci_hi']:.4f}), more than the "
                            f"{100 * P['max_factor']:.0f} % a relative factor should repair: no harmonisation applied; "
                            "request per-machine weights (scale tickets or cart loads per combine) and give them as "
                            "machines.totals_bu")
            gate = "above_max_factor" if not unconfirmed else "above_max_factor_unconfirmed"
        elif not both_sig:
            applied[m] = 1.0
            decision[m] = (f"not applied: the {int(100 * P['ci'])} % bootstrap CI includes 1 at "
                           + (" and ".join(f"{s} m" for s in CELL_SIZES_M if not est[s]["excludes_one"])))
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
        else:
            applied[m] = float(f30)
            decision[m] = (f"applied (30 m factor {f30:.4f}, CI {e30['ci_lo']:.4f}-{e30['ci_hi']:.4f}, "
                           f"{e30['n_cells']} cells / {e30['n_pass_pairs']} pass pairs)")
            gate = "applied"
        for e in est.values():
            e["gate"] = gate
    return tests, applied, decision, ref


def unconfirmed_reason(e30: dict, e50: dict) -> str | None:
    """Why a paired factor above max_factor is NOT a candidate for the ticket closure test: the CI includes 1 at one
    of the cell sizes, or the 30 m and 50 m factors disagree by more than HARM_AGREE. None when it is a candidate
    (significant at both sizes and consistent)."""
    not_sig = [s for s, e in ((CELL_SIZES_M[0], e30), (CELL_SIZES_M[1], e50)) if not e.get("excludes_one")]
    if not_sig:
        return "the bootstrap CI includes 1 at " + " and ".join(f"{s} m" for s in not_sig)
    f30, f50 = e30.get("factor"), e50.get("factor")
    if f30 and f50 and abs(f30 / f50 - 1) > HARM_AGREE:
        return f"the 30 m and 50 m factors disagree ({f30:.4f} vs {f50:.4f}, > {HARM_AGREE:.0%})"
    return None


def ticket_closure(tests: list, applied: dict, decision: dict, ref: str, Mset: dict | None, integrals: dict,
                   ticket_bu: float | None, warnings: list | None = None, notes: list | None = None) -> dict | None:
    """The ticket closure test of the module docstring (item 7). tests / applied / decision / ref: the output of
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
                              + "; request per-machine weights")
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
                           if not (w_.startswith(f"machine {m}:") and "request per-machine weights" in w_)]
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
        res["verdict"] = f"not confirmed: {why}; the factor stays unapplied, request per-machine weights"
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
    return (f"geometric-mean ratio reference / machine over paired {CELL_SIZES_M[0]} m and {CELL_SIZES_M[1]} m cells "
            f"with >= {MIN_POINTS_PER_CELL} kept points{ov_txt} of both machines (same plot when a plan exists), CI by block "
            f"bootstrap over pass pairs ({P['bootstrap_reps']} reps); the 30 m factor is applied only if >= "
            f"{P['min_pairs']} cells and >= {P['min_pass_pairs']} pass pairs at both sizes, both {int(100 * P['ci'])} % CIs "
            f"exclude 1, the two factors agree within {HARM_AGREE:.0%} and {100 * P['min_factor']:g} % < |factor - 1| "
            f"<= {100 * P['max_factor']:g} %; paired t-test p and moisture difference are diagnostics"
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
