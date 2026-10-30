# -*- coding: utf-8 -*-
"""Both cleaning methods on the same readings, and what differs between them.

    R = engine.clean.yield_clean.run(shp, out, {"method": "both"})

run_both cleans the export twice from the same processed set (same reading, same field-of-interest pre-step, same
order): the OCCD cascade into out/ (the usual outputs, unchanged) and the SMS 3-sigma sequence into out/sms3sigma/
(<tag>_sms3s_*), then compares them record by record (joined on the record's row in the file) into out/compare/:

  <tag>_methods_comparison.json   every number below (also in R['methods']['comparison'])
  <tag>_methods_comparison.csv    the side-by-side statistics (metric, OCCD, SMS 3-sigma, difference)
  <tag>_methods_by_plot.csv       per plot of a trial design (when the field of interest is one)
  <tag>_methods_points.zip        every processed point with its class (both / OCCD only / SMS only / neither), the
                                  step that removed it in each method and both yields
  fig_compare_map.png, fig_compare_hist.png, fig_compare_steps.png (+ fig_compare_plots.png with plots)
  <tag>_methods_comparison_report.pdf (engine/report/compare_report.py)

What is compared is the DIFM-ready set of each method (the kept points that go to DIFM, after the output clip). The
yield is each method's mapped dry yield: the export's own for OCCD, the yield scaled by Optimize Swath Widths for SMS
(what SMS maps and exports); the area of a point is distance x width (the optimised width for SMS). Every integral of
the processed set is the same in both (mass is conserved by the swath scaling), so the level factor L of a grower's
weight is the same too.
"""
from __future__ import annotations

import copy
import json
import os

import numpy as np
import pandas as pd

from engine.clean import sms3sigma as sms_mod

FT2_PER_AC = 43560.0
CLASSES = ("both", "occd_only", "sms_only", "neither")
CLASS_LABEL = {"both": "kept by both", "occd_only": "kept by OCCD only", "sms_only": "kept by SMS 3-sigma only",
               "neither": "removed by both"}


def _stats(y, area):
    """Statistics of the points with a finite yield; a point without a finite area (a blank Distance or width cell)
    counts, with zero area, as the engine's own area_ac does."""
    y = np.asarray(y, float)
    a = np.asarray(area, float)
    ok = np.isfinite(y)
    y, a = y[ok], a[ok]
    if not len(y):
        return {k: None for k in ("n", "area_ac", "mean", "mean_area_weighted", "median", "sd", "cv_pct", "p5", "p95",
                                  "min", "max", "total_bu")}
    af = np.where(np.isfinite(a), a, 0.0)
    mean = float(y.mean())
    sd = float(y.std(ddof=1)) if len(y) > 1 else 0.0
    return {"n": int(len(y)), "area_ac": float(af.sum()), "mean": mean,
            "mean_area_weighted": float((y * af).sum() / af.sum()) if af.sum() > 0 else None,
            "median": float(np.median(y)), "sd": sd, "cv_pct": (100 * sd / mean if mean else None),
            "p5": float(np.percentile(y, 5)), "p95": float(np.percentile(y, 95)), "min": float(y.min()),
            "max": float(y.max()), "total_bu": float((y * af).sum())}


def _ready_mask(g, R, S):
    keep = g["Keep"].to_numpy() == 1
    if "In_AOI" in g and (S.get("aoi") or {}).get("clip_output") and R.get("aoi") is not None:
        keep = keep & (g["In_AOI"].to_numpy() == 1)
    return keep


def _upload_values(g, C, col):
    """The values of the column the user is told to map in DIFM, per processed record: the scaled yield of the map for
    the export's own yield column (the SMS file holds it scaled; the OCCD one as logged), else the added column."""
    if not col or col == C.get("yield") or col not in g:
        return g["_ymap"].to_numpy(float)
    return pd.to_numeric(g[col], errors="coerce").to_numpy(float)


def _frame(g, R, diag, S, method, upcol=None):
    C = diag["C"]
    dist_ft = (g[C["distance_ft"]].astype(float).to_numpy() if C.get("distance_ft") else
               g[C["speed_mph"]].astype(float).to_numpy() * 1.46667 * g[C["duration_s"]].astype(float).to_numpy())
    if method == "sms3sigma" and "Dist_Opt" in g:
        dist_ft = np.where(np.isfinite(g["Dist_Opt"].to_numpy(float)), g["Dist_Opt"].to_numpy(float), dist_ft)
    if method == "sms3sigma" and "Wdth_Opt" in g:
        w = g["Wdth_Opt"].astype(float).to_numpy()
    elif C.get("width_ft"):
        w = g[C["width_ft"]].astype(float).to_numpy()
    else:
        w = np.full(len(g), float(S["harvester_width_ft"]))
    f = pd.DataFrame({"row": g["_row"].to_numpy(np.int64), "x": g["_x"].to_numpy(float), "y": g["_y"].to_numpy(float),
                      "keep": _ready_mask(g, R, S), "cleaned": g["Keep"].to_numpy() == 1,
                      "rem": g["Rem_By"].astype(str).to_numpy(),
                      "yld": g["_ymap"].to_numpy(float), "up": _upload_values(g, C, upcol),
                      "area": dist_ft * w / FT2_PER_AC,
                      "hdg": g["_hdg"].to_numpy(float), "d_m": dist_ft * 0.3048, "w_m": w * 0.3048,
                      "machine": g["_machine"].astype(str).to_numpy(),
                      "session": g["Session"].astype(str).to_numpy() if "Session" in g else "",
                      "moi": g[C["moisture"]].astype(float).to_numpy() if C.get("moisture") else np.nan,
                      "spd": (g["_spd_s"].to_numpy(float) if (method == "sms3sigma" and "_spd_s" in g)
                              else g[C["speed_mph"]].astype(float).to_numpy())})
    for k in range(4):                  # the strip each reading's header swept, as logged (yield_clean.swept_strips)
        if f"_qx{k}" in g:
            f[f"qx{k}"], f[f"qy{k}"] = g[f"_qx{k}"].to_numpy(float), g[f"_qy{k}"].to_numpy(float)
    if "Plot_Id" in g:
        f["plot_id"] = g["Plot_Id"].astype(str).to_numpy()
    if "Tgt_Rate" in g:
        f["rate"] = pd.to_numeric(g["Tgt_Rate"], errors="coerce").to_numpy(float)
    if method == "sms3sigma":
        f["width_new"] = w
        f["scale"] = g["Swath_Scl"].astype(float).to_numpy() if "Swath_Scl" in g else 1.0
    return f.set_index("row")


def _group_table(A, B, col, min_n=1):
    """Per group (combine, session, plot): points and mean of the uploaded column of each method."""
    rows = []
    keys = sorted(set(A.loc[A.keep, col]) | set(B.loc[B.keep, col]))
    for k in keys:
        if col == "plot_id" and (k == "" or k is None):
            continue
        a = A[A.keep & (A[col] == k)]
        b = B[B.keep & (B[col] == k)]
        ma = float(a.up.mean()) if len(a) >= min_n else None
        mb = float(b.up.mean()) if len(b) >= min_n else None
        rows.append({col: k, "n_occd": int(len(a)), "n_sms": int(len(b)), "mean_occd": ma, "mean_sms": mb,
                     "diff": (mb - ma if ma is not None and mb is not None else None),
                     "diff_pct": (100 * (mb / ma - 1) if ma and mb is not None else None)})
    return rows


def compare(gA, gB, RA, RB, dA, dB, SA, SB, out, tag, log=print, upload_columns=None) -> dict:
    """The comparison of the OCCD (A) and SMS 3-sigma (B) results of the same processed set; writes the files in out
    and returns the comparison dict (paths absolute in ['files']). upload_columns = {"occd": col, "sms3sigma": col}:
    the column each method tells the user to map in DIFM (engine.run.recommended_yield_column); the statistics and the
    per-group means are on those columns, with the mapped dry yield of both side by side as the like-for-like rows."""
    os.makedirs(out, exist_ok=True)
    up = dict(upload_columns or {})
    colA = up.get("occd") or RA.get("yield_column_for_difm") or dA["C"]["yield"]
    colB = up.get("sms3sigma") or RB.get("yield_column_for_difm") or dB["C"]["yield"]
    A, B = _frame(gA, RA, dA, SA, "occd", colA), _frame(gB, RB, dB, SB, "sms3sigma", colB)
    common = A.index.intersection(B.index)
    notes = []
    if len(common) != len(A) or len(common) != len(B):
        notes.append(f"the processed sets differ ({len(A):,} OCCD vs {len(B):,} SMS records): the record comparison "
                     f"uses the {len(common):,} records of both")
    A, B = A.loc[common], B.loc[common]
    ka, kb = A.keep.to_numpy(), B.keep.to_numpy()
    cls = np.where(ka & kb, "both", np.where(ka, "occd_only", np.where(kb, "sms_only", "neither")))
    counts = {c: int((cls == c).sum()) for c in CLASSES}
    union = counts["both"] + counts["occd_only"] + counts["sms_only"]
    sa, sb = _stats(A.up[ka], A.area[ka]), _stats(B.up[kb], B.area[kb])
    da, db = _stats(A.yld[ka], A.area[ka]), _stats(B.yld[kb], B.area[kb])
    for st_, F in ((sa, A[ka]), (sb, B[kb])):
        st_["moisture_mean"] = float(np.nanmean(F.moi)) if len(F) and np.isfinite(F.moi).any() else None
        st_["speed_mean"] = float(np.nanmean(F.spd)) if len(F) else None
    same_col = (colA == colB)
    col_txt = f"{colA}" if same_col else f"OCCD {colA}, SMS {colB}"
    rows = []
    labels = [("n", "DIFM-ready points", sa, sb), ("area_ac", "Area of the DIFM-ready points (ac)", sa, sb),
              ("mean", f"Mean yield to map ({col_txt}), point mean (bu/ac)", sa, sb),
              ("mean_area_weighted", "Mean yield to map, area-weighted", sa, sb),
              ("median", "Median yield to map", sa, sb), ("sd", "SD of the yield to map", sa, sb),
              ("cv_pct", "CV (%)", sa, sb), ("p5", "5th percentile", sa, sb), ("p95", "95th percentile", sa, sb),
              ("min", "Minimum", sa, sb), ("max", "Maximum", sa, sb),
              ("total_bu", "Bushels on the DIFM-ready points (yield to map x area)", sa, sb),
              ("moisture_mean", "Mean moisture (%)", sa, sb), ("speed_mean", "Mean speed (mph)", sa, sb)]
    if not (same_col and colA == dA["C"]["yield"]):
        labels += [("mean", "Like for like: mean of the mapped dry yield (bu/ac)", da, db),
                   ("median", "Like for like: median of the mapped dry yield", da, db),
                   ("sd", "Like for like: SD of the mapped dry yield", da, db)]
    for k, lab, xa, xb in labels:
        a, b = xa.get(k), xb.get(k)
        if a is None and b is None:
            continue
        rows.append({"metric": k if xa is sa else f"dry_{k}", "label": lab, "occd": a, "sms3sigma": b,
                     "difference": (b - a if a is not None and b is not None else None),
                     "difference_pct": (100 * (b / a - 1) if a not in (None, 0) and b is not None else None)})
    # where the methods disagree: the step that removed each point in the other method; a point the cleaning kept
    # but the output clip of the DIFM file left out is 'clip', not a filter
    def _why(F):
        r = F.rem.to_numpy()
        return np.where((r == "") & ~F.keep.to_numpy(), "clip", np.where(r == "", "kept", r))
    ra, rb = _why(A), _why(B)
    ct = pd.crosstab(pd.Series(ra, name="occd"), pd.Series(rb, name="sms3sigma"))
    order_a = ["kept", "clip"] + [r["filter"] for r in RA["cascade"]]
    order_b = ["kept", "clip"] + [r["filter"] for r in RB["cascade"]]
    ct = ct.reindex(index=[k for k in order_a if k in ct.index] + [k for k in ct.index if k not in order_a],
                    columns=[k for k in order_b if k in ct.columns] + [k for k in ct.columns if k not in order_b]
                    ).fillna(0).astype(int)
    occd_only_by = {str(k): int(v) for k, v in pd.Series(rb[cls == "occd_only"]).value_counts().items()}
    sms_only_by = {str(k): int(v) for k, v in pd.Series(ra[cls == "sms_only"]).value_counts().items()}
    by_machine = _group_table(A, B, "machine") if A.machine.nunique() > 1 else []
    by_session = _group_table(A, B, "session") if A.session.nunique() > 1 else []
    plots, plot_summary = [], None
    if "plot_id" in A and (A["plot_id"] != "").any():
        plots = _group_table(A, B, "plot_id")
        both = [p for p in plots if p["mean_occd"] is not None and p["mean_sms"] is not None]
        if len(both) >= 3:
            ma = np.array([p["mean_occd"] for p in both])
            mb = np.array([p["mean_sms"] for p in both])
            d = mb - ma
            ok_r = ma.std() > 0 and mb.std() > 0
            plot_summary = {"n_plots": len(both), "r": float(np.corrcoef(ma, mb)[0, 1]) if ok_r else None,
                            "mean_diff": float(d.mean()), "mean_abs_diff": float(np.abs(d).mean()),
                            "max_abs_diff": float(np.abs(d).max()),
                            "plot_max_abs_diff": both[int(np.argmax(np.abs(d)))]["plot_id"],
                            "rank_r": (float(pd.Series(ma).rank().corr(pd.Series(mb).rank())) if ok_r else None)}
    by_rate = []
    if "rate" in A and np.isfinite(A.rate).any():
        for r_ in sorted(set(A.rate[np.isfinite(A.rate)])):
            a, b = A[ka & (A.rate == r_)], B[kb & (B.rate == r_)]
            by_rate.append({"rate": float(r_), "n_occd": int(len(a)), "n_sms": int(len(b)),
                            "mean_occd": float(a.up.mean()) if len(a) else None,
                            "mean_sms": float(b.up.mean()) if len(b) else None,
                            "diff": (float(b.up.mean() - a.up.mean()) if len(a) and len(b) else None)})
    LA, LB = (RA.get("level") or {}), (RB.get("level") or {})
    cmp_ = {
        "tag": tag, "input": RA.get("input"), "n_read": RA.get("n_read"), "n_processed": int(len(common)),
        "base": "the processed set of both methods (the same reading and field-of-interest pre-step), joined on the "
                "record's row in the file; the classes count the DIFM-ready points of each method",
        "counts": counts, "class_labels": CLASS_LABEL,
        "agreement_pct": (100 * counts["both"] / union if union else None),
        "same_decision_pct": (100 * (counts["both"] + counts["neither"]) / len(common) if len(common) else None),
        "upload_columns": {"occd": colA, "sms3sigma": colB},
        "stats": {"occd": sa, "sms3sigma": sb, "occd_mapped_dry": da, "sms3sigma_mapped_dry": db}, "table": rows,
        "crosstab": {"rows": list(ct.index), "columns": list(ct.columns), "values": ct.values.tolist()},
        "occd_only_removed_by_sms": occd_only_by, "sms_only_removed_by_occd": sms_only_by,
        "by_machine": by_machine, "by_session": by_session, "by_plot": plots, "plot_summary": plot_summary,
        "by_rate": by_rate,
        "methods": {
            "occd": {"n_in": RA["n_in"], "n_kept": RA["n_kept"], "removed_pct": RA["removed_pct"],
                     "n_difm_ready": RA.get("n_difm_ready"), "yield_column": colA,
                     "steps": [{k: c[k] for k in ("filter", "name", "removed", "remaining", "on")} for c in RA["cascade"]],
                     "pre_steps": RA.get("pre_steps") or [], "level_factor": LA.get("factor_final", LA.get("factor"))},
            "sms3sigma": {"n_in": RB["n_in"], "n_kept": RB["n_kept"], "removed_pct": RB["removed_pct"],
                          "n_difm_ready": RB.get("n_difm_ready"), "yield_column": colB,
                          "steps": [{k: c[k] for k in ("filter", "name", "removed", "remaining", "on")}
                                    for c in RB["cascade"]],
                          "pre_steps": RB.get("pre_steps") or [], "grouping": (RB.get("sms3sigma") or {}).get("grouping"),
                          "level_factor": LB.get("factor_final", LB.get("factor"))}},
        "notes": notes,
        "yield_basis": (f"The yield of each method is the column it tells you to map in DIFM ({col_txt}; in the SMS file "
                        "the export's dry yield is scaled by Optimize Swath Widths); the like-for-like rows compare the "
                        "mapped dry yield of both. Area = distance x width (the optimised width for SMS). 'clip' = kept "
                        "by the cleaning but left out of the DIFM file by the output clip."),
    }
    # ---- files
    files = {"dir": out}
    pd.DataFrame(rows).to_csv(os.path.join(out, f"{tag}_methods_comparison.csv"), index=False)
    files["csv"] = os.path.join(out, f"{tag}_methods_comparison.csv")
    if plots:
        pd.DataFrame(plots).to_csv(os.path.join(out, f"{tag}_methods_by_plot.csv"), index=False)
        files["plots_csv"] = os.path.join(out, f"{tag}_methods_by_plot.csv")
    files["points_zip"] = _write_points(A, B, cls, dA, out, tag)
    log("  comparison figures ...")
    files["figures"] = figures(A, B, cls, cmp_, dA, out, tag)
    cmp_["files"] = files
    files["json"] = os.path.join(out, f"{tag}_methods_comparison.json")
    files["report_pdf"] = os.path.join(out, f"{tag}_methods_comparison_report.pdf")
    try:
        from engine.report.compare_report import make_comparison_report
        make_comparison_report(cmp_, files["report_pdf"])
    except Exception as e:                       # recorded, never silent: the comparison numbers are still written
        cmp_.setdefault("warnings", []).append(f"the comparison report could not be built ({e})")
        files["report_pdf"] = None
    with open(files["json"], "w", encoding="utf-8") as f:
        json.dump(cmp_, f, indent=1, default=_json_default)
    return cmp_


def _json_default(v):
    if hasattr(v, "item"):
        return v.item()
    if isinstance(v, float) and not np.isfinite(v):
        return None
    return str(v)


def _write_points(A, B, cls, dA, out, tag):
    """Every processed point (WGS 84) with its class, the step that removed it in each method and both yields."""
    import geopandas as gpd
    from pyproj import Transformer
    tr = Transformer.from_crs(dA["utm"], "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(A.x.to_numpy(), A.y.to_numpy())
    df = pd.DataFrame({"Row": A.index.to_numpy(np.int64), "Class": cls, "Rem_OC": A.rem.to_numpy(),
                       "Rem_S3": B.rem.to_numpy(), "Yld_OC": A.up.to_numpy(), "Yld_S3": B.up.to_numpy(),
                       "Dry_OC": A.yld.to_numpy(), "Dry_S3": B.yld.to_numpy(),
                       "Wdth_S3": B["width_new"].to_numpy() if "width_new" in B else np.nan})
    ok = np.isfinite(lon) & np.isfinite(lat)
    gdf = gpd.GeoDataFrame(df[ok], geometry=gpd.points_from_xy(np.asarray(lon)[ok], np.asarray(lat)[ok]),
                           crs="EPSG:4326")
    stem = os.path.join(out, f"{tag}_methods_points")
    gdf.to_file(stem + ".shp", encoding="UTF-8")
    import zipfile
    zp = stem + ".zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for e in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
            if os.path.exists(stem + e):
                z.write(stem + e, os.path.basename(stem + e))
    return zp


def figures(A, B, cls, cmp_, dA, out, tag):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from engine.clean import yield_clean as yc
    yc._style(plt)
    files = {}
    from matplotlib.patches import Patch
    x_, y_ = A.x.to_numpy() - np.nanmin(A.x), A.y.to_numpy() - np.nanmin(A.y)
    col = {"both": yc.GREEN, "occd_only": yc.NAVY, "sms_only": yc.ORANGE, "neither": yc.GRID}
    # ---- agreement map: each reading as the strip its header swept (logged geometry), coloured by its class
    if "qx0" in A:
        quads = np.stack([np.c_[A[f"qx{k}"].to_numpy(float), A[f"qy{k}"].to_numpy(float)] for k in range(4)], axis=1)
        quads = quads - np.array([np.nanmin(A.x), np.nanmin(A.y)])
    else:
        quads = yc.swath_quads(x_, y_, A.hdg.to_numpy(), A.d_m.to_numpy(), A.w_m.to_numpy())
    fig, ax = plt.subplots(figsize=(10, 8))
    handles = []
    for z, c in enumerate(("neither", "both", "occd_only", "sms_only")):
        m = (cls == c).to_numpy() if hasattr(cls, "to_numpy") else np.asarray(cls == c)
        yc._strips(ax, quads[m], x_[m], y_[m], color=col[c], zorder=1 + z, s=(0.8 if c in ("both", "neither") else 2.2))
        handles.append(Patch(facecolor=col[c], label=f"{CLASS_LABEL[c]} ({int(m.sum()):,})"))
    yc._extent(ax, x_, y_)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xlabel("Easting from field corner (m)")
    ax.set_ylabel("Northing from field corner (m)")
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    ax.set_title(f"{tag}: where OCCD and SMS 3-sigma agree (DIFM-ready readings as the strips they swept; agreement "
                 f"{cmp_['agreement_pct']:.1f} %)", loc="left")
    files["map"] = os.path.join(out, "fig_compare_map.png")
    fig.savefig(files["map"], bbox_inches="tight")
    plt.close(fig)
    # ---- yield distributions
    ka, kb = A.keep.to_numpy(), B.keep.to_numpy()
    va, vb = A.up.to_numpy()[ka], B.up.to_numpy()[kb]
    va, vb = va[np.isfinite(va)], vb[np.isfinite(vb)]
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw={"width_ratios": [1.6, 1]})
    if len(va) and len(vb):
        lo = float(min(np.percentile(va, 0.2), np.percentile(vb, 0.2)))
        hi = float(max(np.percentile(va, 99.8), np.percentile(vb, 99.8)))
        bins = np.linspace(lo, hi, 70)
        axs[0].hist(va, bins=bins, histtype="step", lw=1.8, color=yc.NAVY, label=f"OCCD ({len(va):,})")
        axs[0].hist(vb, bins=bins, histtype="step", lw=1.8, color=yc.ORANGE, label=f"SMS 3-sigma ({len(vb):,})")
        axs[0].axvline(np.mean(va), color=yc.NAVY, ls="--", lw=1)
        axs[0].axvline(np.mean(vb), color=yc.ORANGE, ls="--", lw=1)
        axs[0].legend(frameon=False)
        uc = cmp_.get("upload_columns") or {}
        axs[0].set_xlabel(f"Yield to map (bu/ac) of the DIFM-ready points: OCCD {uc.get('occd')}, "
                          f"SMS 3-sigma {uc.get('sms3sigma')}")
        axs[0].set_ylabel("Points")
        axs[0].set_title("Yield distribution of each method (dashed: the means)", loc="left")
        axs[1].boxplot([va, vb], tick_labels=["OCCD", "SMS 3-sigma"], showfliers=False, widths=0.5)
        axs[1].set_ylabel("Yield to map (bu/ac)")
        axs[1].set_title("5-95 % whiskers", loc="left")
    files["hist"] = os.path.join(out, "fig_compare_hist.png")
    fig.savefig(files["hist"], bbox_inches="tight")
    plt.close(fig)
    # ---- steps side by side
    M = cmp_["methods"]
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6))
    for ax, key, title, colr in ((axs[0], "occd", "OCCD cascade", yc.NAVY), (axs[1], "sms3sigma", "SMS 3-sigma", yc.ORANGE)):
        stp = [dict(filter=p.get("step", "pre"), name="pre-step", removed=p["removed"], on=True)
               for p in M[key]["pre_steps"]] + M[key]["steps"]
        yy = np.arange(len(stp))[::-1]
        ax.barh(yy, [s["removed"] for s in stp], color=[colr if s["on"] else yc.GRID for s in stp], height=0.65)

        def short(s):
            f = str(s["filter"])
            if s["name"] == "pre-step":
                return f"{f} pre-step"
            if f in yc.SHORT:
                return f"{f}  {yc.SHORT[f]}"
            info = sms_mod.STEP_INFO.get(f[:2])
            if info:
                return f"{f}  {info['short']}" + (f" (pass {sms_mod.PASS_LETTERS.index(f[2]) + 1})" if len(f) > 2 else "")
            return f"{f}  {s['name']}"[:28]
        ax.set_yticks(yy, [short(s) for s in stp], fontsize=8)
        xm = max([s["removed"] for s in stp] + [1])
        for yi, s in zip(yy, stp):
            ax.text(s["removed"] + xm * 0.01, yi, f"{s['removed']:,}" if s["on"] else "off", va="center", fontsize=8,
                    color=yc.INK2)
        ax.set_xlim(0, xm * 1.3)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("Points removed")
        ax.set_title(f"{title}: {M[key]['n_kept']:,} kept ({M[key]['removed_pct']:.1f} % removed)", loc="left")
    files["steps"] = os.path.join(out, "fig_compare_steps.png")
    fig.savefig(files["steps"], bbox_inches="tight")
    plt.close(fig)
    # ---- plot means
    both = [p for p in cmp_.get("by_plot") or [] if p["mean_occd"] is not None and p["mean_sms"] is not None]
    if len(both) >= 3:
        ma = np.array([p["mean_occd"] for p in both])
        mb = np.array([p["mean_sms"] for p in both])
        fig, ax = plt.subplots(figsize=(6, 5.6))
        ax.scatter(ma, mb, s=18, color=yc.NAVY, zorder=3)
        lo, hi = float(min(ma.min(), mb.min())), float(max(ma.max(), mb.max()))
        ax.plot([lo, hi], [lo, hi], color=yc.MUTED, ls="--", lw=1)
        ps = cmp_["plot_summary"]
        ax.set_xlabel("Plot mean, OCCD (bu/ac)")
        ax.set_ylabel("Plot mean, SMS 3-sigma (bu/ac)")
        rtxt = f"r = {ps['r']:.3f}" if ps.get("r") is not None else "r = n/a"
        ax.set_title(f"Plot means: {rtxt}, mean difference {ps['mean_diff']:+.2f} bu/ac", loc="left")
        files["plots"] = os.path.join(out, "fig_compare_plots.png")
        fig.savefig(files["plots"], bbox_inches="tight")
        plt.close(fig)
    return files


def _rel(p, base):
    try:
        return os.path.relpath(p, base) if p else None
    except ValueError:
        return p


def run_both(input_shp, out_dir, settings=None, log=print, source=None):
    """The OCCD cascade into out_dir, the SMS 3-sigma sequence into out_dir/sms3sigma and their comparison into
    out_dir/compare. Returns the OCCD result with R['method'] = 'both' and R['methods'] = {sms3sigma: the summary and
    files of the SMS run, comparison: the comparison summary and files} (paths relative to out_dir, also absolute in
    'files_abs'); the cleaning JSON of the OCCD run is rewritten with them."""
    from engine.clean import yield_clean as yc
    base = copy.deepcopy(settings) if settings else {}
    sA, sB = dict(base, method="occd"), dict(base, method="sms3sigma")
    out = os.path.abspath(str(out_dir))
    log("== 1/3 OCCD cascade ==")
    RA, gA, dA, _ = yc._run_single(input_shp, out, sA, log=log, source=source)
    log("== 2/3 SMS 3-sigma ==")
    RB, gB, dB, _ = yc._run_single(input_shp, os.path.join(out, "sms3sigma"), sB, log=log, source=source)
    log("== 3/3 comparison ==")
    from engine.run import recommended_yield_column           # the column each method tells the user to map
    cols = {"occd": recommended_yield_column(RA)[0], "sms3sigma": recommended_yield_column(RB)[0]}
    CMP = compare(gA, gB, RA, RB, dA, dB, RA["settings"], RB["settings"], os.path.join(out, "compare"), RA["tag"],
                  log=log, upload_columns=cols)
    FB = RB["files"]
    path_keys = {"dir", "input", "flagged_shp", "flagged_zip", "difm_ready_shp", "difm_ready_zip", "json", "report_pdf"}
    sms_files = {k: (_rel(v, out) if k in path_keys else v) for k, v in FB.items()
                 if k not in ("figures",) and not isinstance(v, dict)}
    sms_files["figures"] = {k: _rel(v, out) for k, v in (FB.get("figures") or {}).items()}
    cmp_files = {k: _rel(v, out) for k, v in CMP["files"].items() if isinstance(v, str) and k != "dir"}
    cmp_files["dir"] = _rel(CMP["files"]["dir"], out)
    cmp_files["figures"] = {k: _rel(v, out) for k, v in (CMP["files"].get("figures") or {}).items()}
    RA["method"] = "both"
    RA["settings"] = dict(RA["settings"], method="both")
    RA["methods"] = {
        "sms3sigma": {"n_in": RB["n_in"], "n_kept": RB["n_kept"], "removed_pct": RB["removed_pct"],
                      "n_difm_ready": RB.get("n_difm_ready"), "yield_column_for_difm": RB.get("yield_column_for_difm"),
                      "tag": RB.get("tag"), "files": sms_files, "warnings": RB.get("warnings") or []},
        "comparison": {"counts": CMP["counts"], "agreement_pct": CMP["agreement_pct"],
                       "same_decision_pct": CMP["same_decision_pct"],
                       "mean_occd": CMP["stats"]["occd"]["mean"], "mean_sms3sigma": CMP["stats"]["sms3sigma"]["mean"],
                       "upload_columns": CMP.get("upload_columns"),
                       "plot_summary": CMP.get("plot_summary"), "files": cmp_files},
        "base_dir": out}
    a, b = CMP["stats"]["occd"]["mean"], CMP["stats"]["sms3sigma"]["mean"]
    log(f"comparison: agreement {CMP['agreement_pct']:.1f} % of the kept points; mean OCCD {a:.2f} vs SMS 3-sigma "
        f"{b:.2f} bu/ac ({b - a:+.2f})")
    with open(RA["files"]["json"], "w", encoding="utf-8") as f:
        json.dump(RA, f, indent=1, default=_json_default)
    return RA


def load_methods(R: dict, base_dir: str | None = None) -> tuple:
    """(R_sms3sigma, comparison) of a 'both' result read back from their JSON files (paths re-based on the OCCD
    output folder, so a moved work folder still opens); (None, None) when they are missing."""
    M = R.get("methods") or {}
    base = base_dir or (R.get("files") or {}).get("dir") or M.get("base_dir")
    out = []
    for key in ("sms3sigma", "comparison"):
        js = ((M.get(key) or {}).get("files") or {}).get("json")
        p = os.path.join(base, js) if js and base and not os.path.isabs(js) else js
        if not p or not os.path.exists(p):
            out.append(None)
            continue
        with open(p, encoding="utf-8") as f:
            D = json.load(f)
        files = dict(D.get("files") or {})
        for k, v in list(files.items()):
            if k == "figures" and isinstance(v, dict):
                files[k] = {kk: _rebase(vv, p, base, key) for kk, vv in v.items()}
            elif isinstance(v, str) and (os.sep in v or "/" in v):
                files[k] = _rebase(v, p, base, key)
        files["dir"] = os.path.dirname(p)
        D["files"] = files
        out.append(D)
    return tuple(out)


def _rebase(v, json_path, base, key):
    """A path written by the run, re-based on where its JSON is now: same file name in the JSON's folder."""
    if v and os.path.exists(v):
        return v
    cand = os.path.join(os.path.dirname(json_path), os.path.basename(str(v)))
    return cand if os.path.exists(cand) else v
