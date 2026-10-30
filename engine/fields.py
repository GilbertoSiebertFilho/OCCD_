# -*- coding: utf-8 -*-
"""Saved fields: one field.json per work folder, so that a cleaned field is never lost when the app is closed.

    from engine import fields as ef
    ef.list_fields(workspace)               # every saved field, newest first (legacy run folders listed too)
    rec = ef.load_field(workdir)            # the record of one work folder (None without field.json)
    ef.save_field(workdir, rec)             # atomic write (tmp + os.replace)
    ef.rename_field(workdir, "Field A")    # rewrites the name (a legacy folder gets its field.json here)
    ef.delete_field(workspace, workdir)     # removes that one folder (refused outside the workspace)

The app (app/app.py) writes field.json at the end of every successful run (make_record from its state) and reads it
back with "Open" in the sidebar: the record holds what the page needs to come back without running the engine again
(the input roots to detect again, the decoded shapefile, the field of interest copied into <workdir>/aoi/, the exact
settings the engine received, the result key and where the outputs are). Every path is kept RELATIVE to the work
folder when it lies inside it (relpath / abspath below), so a workspace that was moved or copied still opens; paths
outside the work folder (a monitor card read in place) stay absolute.

Record, version 1 (all keys present; None when unknown):
    version, name, created, updated (ISO), app_version,
    input      {kind upload|path|example|legacy, paths (as given), roots (detect roots), candidate_index, label,
                format ("export" or the decoder id), tag, units (ids decoded), decode_options, decoder_kwargs,
                decode_report, aoi_shares}
    decoded_shp  the standard shapefile written by the decoder (raw inputs), else None
    aoi        {path (inside aoi/), name, feature, buffer_m, clip_output, id_col, rate_col, n_polygons, n_plots,
                headland_polygons, area_ac, crs} or None
    crop, settings (= the dict the engine received), scale_ticket (settings["scale_ticket"] or None: the grower's
    weight is optional and its absence is never a warning), result_key,
    outputs    {dir, difm_ready_zip, difm_ready_shp, flagged_zip, cleaning_json, report_pdf, figures []} (relative)
    summary    {n_in, n_kept, pct_removed, yield_mean_bu_ac, difm_column, level_factor, machines [], sessions,
                run_at, duration_s}
A legacy work folder (output*/<tag>_cleaning.json, no field.json) is listed with legacy=True and the folder tag as
its name, synthesised in memory from the cleaning JSON; nothing is written into it until the user renames or re-saves
it. This module is pure Python (no Streamlit) so that it can be unit-tested and used from the CLI.
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re
import shutil
import tempfile

FIELD_FILE = "field.json"
AOI_DIR = "aoi"
SCHEMA_VERSION = 1
SHP_SIBLINGS = (".shp", ".shx", ".dbf", ".prj", ".cpg", ".sbn", ".sbx", ".qix")
_STAMP = re.compile(r"^(\d{8})-(\d{6})_(.*)$")        # the work folder name: <YYYYmmdd-HHMMSS>_<tag>


# ================================================================================================ paths
def _norm(p: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(str(p))))


def relpath(path, workdir: str):
    """`path` relative to the work folder (forward slashes) when it lies inside it, else the absolute path unchanged;
    None stays None. The relative form is what makes a moved workspace open again."""
    if path is None or path == "":
        return None
    p, w = _norm(path), _norm(workdir)
    if p == w:
        return "."
    if p.startswith(w.rstrip("\\/") + os.sep):
        return os.path.relpath(os.path.abspath(str(path)), os.path.abspath(workdir)).replace("\\", "/")
    return os.path.abspath(str(path))


def abspath(rel, workdir: str):
    """The absolute path of a record entry: joined to the work folder when relative. An absolute path that no longer
    exists but whose tail matches a file inside the work folder is re-based too (a legacy record written with
    absolute paths before the workspace moved)."""
    if rel is None or rel == "":
        return None
    rel = str(rel)
    if not os.path.isabs(rel):
        return os.path.normpath(os.path.join(os.path.abspath(workdir), rel))
    if os.path.exists(rel):
        return os.path.normpath(rel)
    parts = rel.replace("\\", "/").split("/")
    for i in range(len(parts) - 1, 0, -1):                # the longest tail that exists under the work folder
        cand = os.path.join(os.path.abspath(workdir), *parts[i:])
        if os.path.exists(cand):
            return os.path.normpath(cand)
    return os.path.normpath(rel)


def field_path(workdir: str) -> str:
    return os.path.join(os.path.abspath(workdir), FIELD_FILE)


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def is_workdir(path: str) -> bool:
    """A work folder of the app: it holds field.json or an output folder with a cleaning JSON."""
    if not os.path.isdir(path):
        return False
    if os.path.exists(os.path.join(path, FIELD_FILE)):
        return True
    return bool(_cleaning_jsons(path))


def _cleaning_jsons(workdir: str) -> list[str]:
    """The cleaning JSONs of a work folder, newest run first (output/, output_2/ ... one folder per run)."""
    out = []
    for d in glob.glob(os.path.join(glob.escape(workdir), "output*")):
        if os.path.isdir(d):
            out += glob.glob(os.path.join(glob.escape(d), "*_cleaning.json"))
    return sorted(out, key=lambda p: os.path.getmtime(p), reverse=True)


# ================================================================================================ read / write
def load_field(workdir: str) -> dict | None:
    """The record of a work folder (None without field.json; a broken file raises ValueError with the reason)."""
    p = field_path(workdir)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError) as e:
        raise ValueError(f"{p}: cannot be read ({e})") from None
    if not isinstance(rec, dict) or "name" not in rec:
        raise ValueError(f"{p}: not a field record")
    rec.setdefault("version", SCHEMA_VERSION)
    rec["workdir"] = os.path.abspath(workdir)
    rec["legacy"] = False
    return rec


def save_field(workdir: str, record: dict) -> str:
    """Write field.json atomically (a temp file in the same folder, then os.replace: a crash never leaves a half
    file). `updated` is set here; `created` when missing. The in-memory keys workdir / legacy are not written."""
    rec = {k: v for k, v in record.items() if k not in ("workdir", "legacy")}
    rec["version"] = SCHEMA_VERSION
    rec.setdefault("created", _now())
    rec["updated"] = _now()
    os.makedirs(workdir, exist_ok=True)
    p = field_path(workdir)
    fd, tmp = tempfile.mkstemp(prefix=".field_", suffix=".tmp", dir=os.path.dirname(p))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1, ensure_ascii=False, default=_json_default)
        os.replace(tmp, p)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    record["updated"] = rec["updated"]
    record.setdefault("created", rec["created"])
    return p


def _json_default(v):
    if hasattr(v, "item"):                                # numpy scalars
        return v.item()
    if hasattr(v, "tolist"):
        return v.tolist()
    if isinstance(v, (set, tuple)):
        return list(v)
    return str(v)


def rename_field(workdir: str, name: str) -> dict:
    """Set the name and rewrite field.json; a legacy folder (no field.json yet) gets its record written here, which is
    the one case where a legacy folder is written to. Returns the record."""
    name = clean_name(name)
    if not name:
        raise ValueError("the field name cannot be empty")
    rec = load_field(workdir) or legacy_record(workdir)
    if rec is None:
        raise ValueError(f"{workdir}: not a work folder of the app (no field.json, no cleaning output)")
    rec["name"] = name
    save_field(workdir, rec)
    rec["legacy"] = False
    return rec


def clean_name(name) -> str:
    """One line, trimmed, at most 80 characters (the name is a label, not a file name)."""
    s = re.sub(r"\s+", " ", str(name or "")).strip()
    return s[:80]


def delete_field(workspace: str, workdir: str) -> None:
    """Remove that one work folder. Refused (ValueError) unless the folder lies inside the workspace and is a work
    folder of the app (field.json or a cleaning output): the workspace itself, its parents or any other folder are
    never touched."""
    ws, wd = _norm(workspace), _norm(workdir)
    if not os.path.isdir(workdir):
        raise ValueError(f"not a folder: {workdir}")
    if wd == ws or not wd.startswith(ws.rstrip("\\/") + os.sep):
        raise ValueError(f"refused: {workdir} is not a folder inside the workspace {workspace}")
    if not is_workdir(workdir):
        raise ValueError(f"refused: {workdir} holds no field.json and no cleaning output")
    shutil.rmtree(workdir)


# ================================================================================================ listing
def folder_tag(workdir: str) -> str:
    """The tag part of a work folder name (<stamp>_<tag> -> tag), the folder name when there is no stamp."""
    base = os.path.basename(os.path.normpath(workdir))
    m = _STAMP.match(base)
    return (m.group(3) or base) if m else base


def folder_stamp(workdir: str) -> str | None:
    """The ISO time of a work folder's stamp (None without one)."""
    m = _STAMP.match(os.path.basename(os.path.normpath(workdir)))
    if not m:
        return None
    try:
        return _dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").isoformat(timespec="seconds")
    except ValueError:
        return None


def legacy_record(workdir: str) -> dict | None:
    """A record synthesised in memory from the latest cleaning JSON of a work folder without field.json (the runs
    made before saved fields existed): legacy=True, name = the folder tag, the settings and outputs of that run.
    None when the folder holds no cleaning JSON. Nothing is written."""
    js = _cleaning_jsons(workdir)
    if not js:
        return None
    try:
        with open(js[0], encoding="utf-8") as f:
            R = json.load(f)
    except (OSError, ValueError):
        return None
    S = R.get("settings") or {}
    files = R.get("files") or {}
    aoi_file = (S.get("aoi") or {}).get("file") or S.get("boundary")
    RA = R.get("aoi") or {}
    aoi = None
    if aoi_file:
        aoi = {"path": relpath(aoi_file, workdir), "name": os.path.basename(str(aoi_file)),
               "feature": (S.get("aoi") or {}).get("feature"), "buffer_m": (S.get("aoi") or {}).get("buffer_m"),
               "clip_output": (S.get("aoi") or {}).get("clip_output"), "id_col": RA.get("id_col"),
               "rate_col": RA.get("rate_col"), "n_polygons": RA.get("n_polygons"), "n_plots": RA.get("n_plots"),
               "headland_polygons": RA.get("headland_polygons"), "area_ac": RA.get("area_ac"), "crs": RA.get("crs")}
    src = R.get("source") or R.get("input_source") or {}
    decoded_shp = src.get("decoded_shp") if isinstance(src, dict) else None
    inp = R.get("input") or files.get("input")
    roots = [relpath(d, workdir) for d in sorted(glob.glob(os.path.join(glob.escape(workdir), "input*")))
             if os.path.isdir(d)]
    rep_root = None
    if decoded_shp:
        rj = (src.get("decode_report") if isinstance(src, dict) else None)
        if rj and os.path.exists(abspath(rj, workdir)):
            try:
                with open(abspath(rj, workdir), encoding="utf-8") as f:
                    rep_root = (json.load(f) or {}).get("input_root")
            except (OSError, ValueError):
                rep_root = None
    if rep_root:
        roots.append(relpath(rep_root, workdir))
    stamp = folder_stamp(workdir) or _dt.datetime.fromtimestamp(os.path.getmtime(js[0])).isoformat(timespec="seconds")
    rec = {"version": SCHEMA_VERSION, "name": folder_tag(workdir), "created": stamp,
           "updated": _dt.datetime.fromtimestamp(os.path.getmtime(js[0])).isoformat(timespec="seconds"),
           "app_version": None,
           "input": {"kind": "legacy", "paths": [inp] if inp else [], "roots": roots, "candidate_index": 0,
                     "label": (src.get("label") if isinstance(src, dict) else None), "format": (
                         src.get("format") if isinstance(src, dict) and src.get("format") else "export"),
                     "tag": R.get("tag") or S.get("tag") or folder_tag(workdir),
                     "units": (src.get("units") if isinstance(src, dict) else None),
                     "decode_options": (src.get("options") if isinstance(src, dict) else None),
                     "decoder_kwargs": (src.get("decoder_kwargs") if isinstance(src, dict) else None),
                     "decode_report": (relpath(src.get("decode_report"), workdir) if isinstance(src, dict) else None),
                     "aoi_shares": None},
           "decoded_shp": relpath(decoded_shp, workdir) if decoded_shp else None,
           "aoi": aoi, "crop": S.get("crop"), "settings": S, "scale_ticket": S.get("scale_ticket"),
           "result_key": None, "outputs": outputs_of(R, workdir), "summary": summary_of(R, run_at=None),
           "workdir": os.path.abspath(workdir), "legacy": True}
    rec["summary"]["difm_column"] = R.get("yield_column_for_difm")
    rec["method"] = R.get("method") or S.get("method") or "occd"
    cm = (R.get("methods") or {}).get("comparison")
    if cm:                                        # a 'both' run: the comparison summary, as the app's autosave writes
        m3 = (R.get("methods") or {}).get("sms3sigma") or {}
        rec["comparison"] = {"agreement_pct": cm.get("agreement_pct"), "counts": cm.get("counts"),
                             "mean_occd": cm.get("mean_occd"), "mean_sms3sigma": cm.get("mean_sms3sigma"),
                             "sms3sigma_n_kept": m3.get("n_kept")}
    return rec


def list_fields(workspace: str) -> list[dict]:
    """Every saved field of the workspace, newest first (by `updated`): the field.json records, plus the legacy work
    folders (a cleaning output, no field.json) synthesised in memory. A folder that is neither is skipped; a broken
    field.json is listed with its error in rec['error'] so that the user can delete it."""
    out = []
    if not os.path.isdir(workspace):
        return out
    for name in os.listdir(workspace):
        wd = os.path.join(workspace, name)
        if not os.path.isdir(wd) or name == "aoi_uploads":
            continue
        try:
            rec = load_field(wd)
        except ValueError as e:
            rec = {"version": SCHEMA_VERSION, "name": folder_tag(wd), "created": folder_stamp(wd), "updated": None,
                   "error": str(e), "input": {}, "aoi": None, "crop": None, "settings": {}, "scale_ticket": None,
                   "outputs": {}, "summary": {}, "workdir": os.path.abspath(wd), "legacy": False}
        if rec is None:
            rec = legacy_record(wd)
        if rec is not None:
            out.append(rec)
    out.sort(key=lambda r: str(r.get("updated") or r.get("created") or ""), reverse=True)
    return out


def field_label(rec: dict, short: bool = False) -> str:
    """'<name> · <dd Mon> · <n_kept:,> kept[ · <crop>][ · (older run)][ · (unreadable)]' for a saved field; `short`
    leaves the kept count out (the sidebar selectbox is about 250 px wide and truncates the full label, so the app
    shows the short one there and the kept count in the caption under the buttons)."""
    s = rec.get("name") or folder_tag(rec.get("workdir") or "")
    when = (rec.get("summary") or {}).get("run_at") or rec.get("updated") or rec.get("created")
    if when:
        try:
            s += " · " + _dt.datetime.fromisoformat(str(when)).strftime("%d %b")
        except ValueError:
            pass
    n = (rec.get("summary") or {}).get("n_kept")
    if n is not None and not short:
        s += f" · {int(n):,} kept"
    if rec.get("crop"):
        s += f" · {rec['crop']}"
    if rec.get("legacy"):
        s += " · (older run)"
    if rec.get("error"):
        s += " · (unreadable)"
    return s


# ================================================================================================ the record
def outputs_of(R: dict, workdir: str) -> dict:
    """The output files of a cleaning result, relative to the work folder."""
    F = R.get("files") or {}
    figs = F.get("figures") or {}
    return {"dir": relpath(F.get("dir"), workdir), "difm_ready_zip": relpath(F.get("difm_ready_zip"), workdir),
            "difm_ready_shp": relpath(F.get("difm_ready_shp"), workdir),
            "flagged_zip": relpath(F.get("flagged_zip"), workdir), "cleaning_json": relpath(F.get("json"), workdir),
            "report_pdf": relpath(F.get("report_pdf"), workdir),
            "figures": [relpath(p, workdir) for p in (figs.values() if isinstance(figs, dict) else figs) if p]}


def level_factor_of(R: dict):
    """The level applied to the columns (factor_final, else the harmonised / plain factor); None without a ticket."""
    L = R.get("level") or {}
    if not isinstance(L, dict) or not L:
        return None
    f = L.get("factor_final")
    if f is None:
        f = L.get("factor_harmonised", L.get("factor"))
    return float(f) if f is not None else None


def machines_of(R: dict) -> list[str]:
    M = R.get("machines") or {}
    for k in ("n_points", "n_kept", "factor_applied", "means"):
        v = M.get(k)
        if isinstance(v, dict) and v:
            return [str(m) for m in v]
    return []


def summary_of(R: dict, run_at: str | None = None, duration_s: float | None = None, difm_column: str | None = None,
               yield_mean_bu_ac: float | None = None) -> dict:
    """The few numbers the saved-fields list and the step-4 metrics need."""
    ses = R.get("sessions") or {}
    n_ses = ses.get("n_sessions")
    if n_ses is None and isinstance(ses.get("table"), list):
        n_ses = len(ses["table"])
    if yield_mean_bu_ac is None:
        fld = ses.get("field") or {}
        v = fld.get("cleaned_map_mean")
        yield_mean_bu_ac = float(v) if isinstance(v, (int, float)) else None
    return {"n_in": R.get("n_in"), "n_kept": R.get("n_kept"),
            "pct_removed": (float(R["removed_pct"]) if R.get("removed_pct") is not None else None),
            "yield_mean_bu_ac": yield_mean_bu_ac, "difm_column": difm_column or R.get("yield_column_for_difm"),
            "level_factor": level_factor_of(R), "machines": machines_of(R), "sessions": n_ses,
            "run_at": run_at, "duration_s": duration_s}


def yield_mean(shp: str | None, col: str | None):
    """The mean of one column of a point shapefile (the DIFM column of the DIFM-ready file), None when it cannot be
    read: this is the 'Mean yield' metric of step 4, so it is the mean of the column the user will map."""
    if not shp or not col or not os.path.exists(shp):
        return None
    try:
        import numpy as np
        import pyogrio
        info = pyogrio.read_info(shp)
        if col not in list(info.get("fields", [])):
            return None
        v = pyogrio.read_dataframe(shp, columns=[col], read_geometry=False)[col].to_numpy(dtype=float, na_value=np.nan)
        v = v[np.isfinite(v)]
        return float(v.mean()) if len(v) else None
    except Exception:
        return None


def copy_aoi(src_path: str, workdir: str) -> str:
    """Copy the field-of-interest file into <workdir>/aoi/ (a shapefile with its siblings) so that the work folder is
    self-contained; returns the copy's absolute path. A path already inside aoi/ is returned as is."""
    src = os.path.abspath(str(src_path))
    dst_dir = os.path.join(os.path.abspath(workdir), AOI_DIR)
    if _norm(os.path.dirname(src)) == _norm(dst_dir):
        return src
    os.makedirs(dst_dir, exist_ok=True)
    stem, ext = os.path.splitext(src)
    files = [src]
    if ext.lower() == ".shp":
        files = [stem + e for e in SHP_SIBLINGS if os.path.exists(stem + e)]
        # the sibling extensions may be upper case on some exports
        d = os.path.dirname(src)
        base = os.path.basename(stem).lower()
        files += [os.path.join(d, f) for f in os.listdir(d)
                  if os.path.splitext(f)[0].lower() == base and os.path.join(d, f) not in files
                  and os.path.splitext(f)[1].lower() in SHP_SIBLINGS]
    for f in files:
        dst = os.path.join(dst_dir, os.path.basename(f))
        if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(f)):
            shutil.copy2(f, dst)
    return os.path.join(dst_dir, os.path.basename(src))


def make_record(workdir: str, name: str, input: dict, settings: dict, result: dict, result_key: str | None,
                app_version: str | None, decoded_shp: str | None = None, aoi: dict | None = None,
                difm_column: str | None = None, run_at: str | None = None, duration_s: float | None = None,
                created: str | None = None) -> dict:
    """The record of a finished run from the app's state. `input` is the app's description of the input (kind, paths,
    roots, candidate_index, label, format, tag, units, decode_options, decoder_kwargs, decode_report, aoi_shares);
    `aoi` the app's field-of-interest dict (path, name, feature, buffer_m, clip_output + the plan summary): its file
    is copied into <workdir>/aoi/ here. Paths inside the work folder are stored relative."""
    inp = dict(input or {})
    inp["roots"] = [relpath(r, workdir) for r in (inp.get("roots") or [])]
    if inp.get("decode_report"):
        inp["decode_report"] = relpath(inp["decode_report"], workdir)
    A = None
    if aoi and aoi.get("path"):
        copy = copy_aoi(aoi["path"], workdir)
        A = {"path": relpath(copy, workdir), "name": aoi.get("name") or os.path.basename(copy),
             "feature": aoi.get("feature"), "buffer_m": (settings.get("aoi") or {}).get("buffer_m"),
             "clip_output": (settings.get("aoi") or {}).get("clip_output"), "id_col": aoi.get("id_col"),
             "rate_col": aoi.get("rate_col"), "n_polygons": aoi.get("n_polygons"), "n_plots": aoi.get("n_plots"),
             "headland_polygons": aoi.get("headland_polygons"), "area_ac": aoi.get("area_ac"), "crs": aoi.get("crs")}
    F = result.get("files") or {}
    col = difm_column or result.get("yield_column_for_difm")
    summary = summary_of(result, run_at=run_at or _now(), duration_s=duration_s, difm_column=col,
                         yield_mean_bu_ac=yield_mean(F.get("difm_ready_shp"), col))
    return {"version": SCHEMA_VERSION, "name": clean_name(name) or inp.get("tag") or folder_tag(workdir),
            "created": created or _now(), "updated": None, "app_version": app_version, "input": inp,
            "decoded_shp": relpath(decoded_shp, workdir) if decoded_shp else None, "aoi": A,
            "crop": settings.get("crop"), "settings": settings, "scale_ticket": settings.get("scale_ticket"),
            "result_key": result_key, "outputs": outputs_of(result, workdir), "summary": summary,
            "workdir": os.path.abspath(workdir), "legacy": False}


# ================================================================================================ reading back
def output_paths(rec: dict, workdir: str | None = None) -> dict:
    """The outputs of a record as absolute paths (re-based on the work folder)."""
    wd = workdir or rec.get("workdir")
    O = rec.get("outputs") or {}
    out = {k: abspath(v, wd) for k, v in O.items() if k != "figures"}
    out["figures"] = [abspath(p, wd) for p in (O.get("figures") or [])]
    return out


def outputs_exist(rec: dict, workdir: str | None = None) -> bool:
    """True when the DIFM-ready zip and the cleaning JSON of the record are still on disk."""
    P = output_paths(rec, workdir)
    return bool(P.get("difm_ready_zip") and os.path.exists(P["difm_ready_zip"])
                and P.get("cleaning_json") and os.path.exists(P["cleaning_json"]))


def load_result(rec: dict, workdir: str | None = None) -> dict | None:
    """The cleaning result R of a saved field, read from its cleaning JSON with every path of R['files'] re-based on
    the work folder (so the downloads and figures of step 4 work after a move). None when the JSON is missing."""
    wd = workdir or rec.get("workdir")
    P = output_paths(rec, wd)
    js = P.get("cleaning_json")
    if not js or not os.path.exists(js):
        return None
    with open(js, encoding="utf-8") as f:
        R = json.load(f)
    F = dict(R.get("files") or {})
    for k, v in list(F.items()):
        if k == "figures" and isinstance(v, dict):
            F[k] = {kk: abspath(vv, wd) for kk, vv in v.items()}
        elif isinstance(v, str) and (os.sep in v or "/" in v):
            F[k] = abspath(v, wd)
    if not F.get("dir") and js:
        F["dir"] = os.path.dirname(js)
    R["files"] = F
    return R
