# -*- coding: utf-8 -*-
"""The comparison report of the two cleaning methods (OCCD cascade vs SMS 3-sigma), a PDF in the house style of
engine/report/clean_report.py. Every number is read from the comparison dict (engine/clean/compare.py); nothing is
recomputed here.

    python -m engine.report.compare_report <tag>_methods_comparison.json <out.pdf>
"""
from __future__ import annotations

import datetime
import json
import os

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from engine.report.clean_report import (BODY, BRAND, CAP, GREY, H1, H2, MARGIN, ORG, PAGE_W, RULE, SUB, TEXT_W, BUL,
                                        _e, _image, _masthead, _n, _table)


def _v(x, d=2):
    if x is None:
        return "-"
    if isinstance(x, (int,)) and not isinstance(x, bool):
        return f"{x:,}"
    try:
        return f"{float(x):,.{d}f}"
    except (TypeError, ValueError):
        return _e(str(x))


def make_comparison_report(C: dict, path: str) -> str:
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    story = [_masthead(), Spacer(1, 10), Paragraph("Cleaning methods compared: OCCD cascade and SMS 3-sigma", H1),
             Paragraph(f"{_e(os.path.basename(str(C.get('input') or '')))} &nbsp;&middot;&nbsp; tag {_e(C.get('tag', ''))}"
                       f" &nbsp;&middot;&nbsp; {datetime.date.today().isoformat()}", SUB), Spacer(1, 6)]
    cnt = C["counts"]
    M = C["methods"]
    sa, sb = C["stats"]["occd"], C["stats"]["sms3sigma"]
    story.append(Paragraph("1. Summary", H2))
    story.append(Paragraph(
        f"Both methods cleaned the same {C['n_processed']:,} processed readings ({_e(C['base'])}). OCCD kept "
        f"<b>{_v(sa['n'], 0)}</b> DIFM-ready points, SMS 3-sigma <b>{_v(sb['n'], 0)}</b>; "
        f"<b>{cnt['both']:,}</b> are kept by both, {cnt['occd_only']:,} by OCCD only and {cnt['sms_only']:,} by SMS "
        f"3-sigma only (agreement {C['agreement_pct']:.1f} % of the points kept by either; the two methods take the "
        f"same decision on {C['same_decision_pct']:.1f} % of the readings). The mean of the yield to map is "
        f"{_v(sa['mean'])} bu/ac with OCCD ({_e(M['occd'].get('yield_column') or '')}) and {_v(sb['mean'])} bu/ac with "
        f"SMS 3-sigma ({_e(M['sms3sigma'].get('yield_column') or '')}), "
        f"{(sb['mean'] or 0) - (sa['mean'] or 0):+.2f} bu/ac. {_e(C.get('yield_basis', ''))}", BODY))
    rows = [["Metric", "OCCD", "SMS 3-sigma", "Difference", "%"]]
    for r in C["table"]:
        d = 0 if r["metric"] == "n" else 2
        rows.append([_e(r["label"]), _v(r["occd"], d), _v(r["sms3sigma"], d), _v(r["difference"], d),
                     (f"{r['difference_pct']:+.1f}" if r.get("difference_pct") is not None else "-")])
    t = _table(rows, [2.6 * inch, 1.05 * inch, 1.05 * inch, 1.05 * inch, 0.6 * inch], small=True)
    t.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
    story.append(t)
    for n_ in C.get("notes") or []:
        story.append(Paragraph(_e(n_), BUL, bulletText="•"))

    story.append(Paragraph("2. Where the methods disagree", H2))
    oo = C.get("occd_only_removed_by_sms") or {}
    so = C.get("sms_only_removed_by_occd") or {}
    story.append(Paragraph(
        "Points OCCD keeps but SMS 3-sigma removes, by the SMS step that removed them: "
        + (", ".join(f"{_e(k)} {v:,}" for k, v in sorted(oo.items(), key=lambda kv: -kv[1])) or "none")
        + ". Points SMS 3-sigma keeps but OCCD removes, by the OCCD filter that removed them: "
        + (", ".join(f"{_e(k)} {v:,}" for k, v in sorted(so.items(), key=lambda kv: -kv[1])) or "none")
        + ". The table crosses the step that removed each reading in each method (kept = in the DIFM-ready file; "
          "clip = kept by the cleaning but left out of the DIFM file by the output clip).", BODY))
    ct = C["crosstab"]
    if ct["rows"] and ct["columns"]:
        cols = ct["columns"][:12]
        rows = [["OCCD \\ SMS"] + [_e(c) for c in cols]]
        for r_, vals in zip(ct["rows"], ct["values"]):
            rows.append([_e(r_)] + [(f"{v:,}" if v else "") for v in vals[:12]])
        w0 = 0.9 * inch
        wc = (TEXT_W - w0) / max(len(cols), 1)
        t = _table(rows, [w0] + [wc] * len(cols), small=True)
        t.setStyle(TableStyle([("ALIGN", (1, 0), (-1, -1), "RIGHT")]))
        story.append(t)

    story.append(Paragraph("3. The steps of each method", H2))
    for key, title in (("occd", "OCCD cascade"), ("sms3sigma", "SMS 3-sigma")):
        rows = [["Step", "Removed", "Remaining"]]
        for p in M[key].get("pre_steps") or []:
            rows.append([f"{_e(p.get('step', 'pre-step'))} (pre-step)", _n(p["removed"]), _n(p.get("remaining"))])
        for s in M[key]["steps"]:
            rows.append([f"{_e(s['filter'])} {_e(s['name'])}" + ("" if s["on"] else " (off)"), _n(s["removed"]),
                         _n(s["remaining"])])
        g = M[key].get("grouping")
        story.append(KeepTogether([Paragraph(f"<b>{title}</b>: {M[key]['n_in']:,} in, {M[key]['n_kept']:,} kept ("
                                             f"{M[key]['removed_pct']:.1f} % removed)"
                                             + (f"; 3-sigma groups: {_e(g.get('mode'))} ({g.get('n_groups')})" if g else ""),
                                             BODY),
                                   _table(rows, [3.2 * inch, 1.0 * inch, 1.0 * inch], small=True), Spacer(1, 4)]))

    num = 4
    for key, col, title in (("by_machine", "machine", "By combine"), ("by_session", "session", "By harvest session")):
        T = C.get(key) or []
        if not T:
            continue
        story.append(Paragraph(f"{num}. {title}", H2))
        num += 1
        rows = [[title.split()[-1].capitalize(), "Points OCCD", "Points SMS", "Mean OCCD", "Mean SMS", "Difference"]]
        for r in T:
            rows.append([_e(str(r[col])[:40]), _n(r["n_occd"]), _n(r["n_sms"]), _v(r["mean_occd"]), _v(r["mean_sms"]),
                         _v(r["diff"])])
        story.append(_table(rows, [2.3 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.8 * inch], small=True))
    ps = C.get("plot_summary")
    if ps:
        story.append(Paragraph(f"{num}. By plot of the trial design", H2))
        num += 1
        story.append(Paragraph(
            f"On the {ps['n_plots']} plots with points in both methods, the plot means (of the yield to map) correlate "
            + (f"at r = {ps['r']:.3f} (rank r = {ps['rank_r']:.3f})" if ps.get("r") is not None else "(r not defined: "
               "no spread)") + f"; SMS 3-sigma is {ps['mean_diff']:+.2f} bu/ac from OCCD on average "
            f"(mean |difference| {ps['mean_abs_diff']:.2f}, largest {ps['max_abs_diff']:.2f} in plot "
            f"{_e(ps['plot_max_abs_diff'])}). The per-plot table is in the _methods_by_plot.csv file.", BODY))
    BR = C.get("by_rate") or []
    if BR:
        rows = [["Target rate", "Points OCCD", "Points SMS", "Mean OCCD", "Mean SMS", "Difference"]]
        for r in BR:
            rows.append([_v(r["rate"]), _n(r["n_occd"]), _n(r["n_sms"]), _v(r["mean_occd"]), _v(r["mean_sms"]),
                         _v(r["diff"])])
        story.append(Paragraph("Mean of the yield to map by target rate (the treatments): a method that shifts the "
                               "treatment means differently changes the response DIFM fits.", BODY))
        story.append(_table(rows, [1.4 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 0.9 * inch], small=True))

    figs = (C.get("files") or {}).get("figures") or {}
    caps = {"map": "Where the methods agree: points kept by both (green), by OCCD only (navy), by SMS 3-sigma only "
                   "(orange), removed by both (grey).",
            "hist": (f"Distribution of the yield to map (the column each method tells you to map in DIFM: OCCD "
                     f"{_e(M['occd'].get('yield_column') or '')}, SMS 3-sigma "
                     f"{_e(M['sms3sigma'].get('yield_column') or '')}) on the DIFM-ready points of each method; "
                     "dashed: the means."),
            "steps": "Points removed by each step of each method.",
            "plots": "Plot means of the trial design under each method (dashed: 1:1)."}
    head = [Paragraph(f"{num}. Figures", H2)]
    num += 1
    for key in ("map", "hist", "steps", "plots"):
        p = figs.get(key)
        if p and os.path.exists(p):
            story.append(KeepTogether(head + [_image(p, TEXT_W, 4.2 * inch if key == "map" else 2.6 * inch),
                                              Paragraph(caps[key], CAP)]))
            head = []
    story.extend(head)
    story.append(Paragraph(f"{num}. What to upload", H2))
    story.append(Paragraph(
        "Both DIFM-ready files are complete uploads. The OCCD file is the house standard (measured thresholds, the "
        "export's values untouched); the SMS 3-sigma file reproduces the SMS procedure (Optimize Swath Widths narrows "
        "the overlapped points and scales their yield, then speed, moisture and yield within mean &plusmn; 3 SD). Map "
        f"the yield column {_e(M['occd'].get('yield_column') or '')} of the OCCD file and "
        f"{_e(M['sms3sigma'].get('yield_column') or '')} of the SMS 3-sigma file; in the SMS 3-sigma file the swath "
        "width column already holds the optimised width.", BODY))

    def _foot(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN, 0.66 * inch, PAGE_W - MARGIN, 0.66 * inch)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)
        canvas.drawString(MARGIN, 0.5 * inch, f"{BRAND} · {ORG}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.5 * inch, f"{C.get('tag', '')} · methods compared · page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN,
                            bottomMargin=0.8 * inch, title=f"OCCD methods compared - {C.get('tag', '')}", author=BRAND)
    doc.build(story, onFirstPage=_foot, onLaterPages=_foot)
    return path


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        sys.exit("usage: python -m engine.report.compare_report <methods_comparison.json> <out.pdf>")
    with open(sys.argv[1], encoding="utf-8") as f:
        print(make_comparison_report(json.load(f), sys.argv[2]))
