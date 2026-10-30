# -*- coding: utf-8 -*-
"""OCCD — Olds College Cleaning Data: the Streamlit front end of the yield data cleaning for the DIFM platform.

    python -m streamlit run app/app.py          (or double-click run_app.bat)

Four steps on one page: 1 input (upload, or a file / folder on this computer) and the optional field of interest
(a boundary or trial-design polygon file), 2 decode (raw monitor data) or check (point export), 3 cleaning settings
(the method: the OCCD cascade, the SMS 3-sigma sequence, or both and a comparison), 4 run and download the DIFM-ready
shapefile(s). All the work is done by engine/run.py (detect, decode, clean); this file
only builds the page. Each opened input gets its own work folder workspace/<YYYYmmdd-HHMMSS>_<tag>/ with input/,
decoded/ and output/ (set YIELD_APP_WORKSPACE to move it).

Field of interest. The grower's raw data often holds several fields and the monitor's field names are unreliable, so
when a field of interest is loaded the units of a raw dataset are pre-selected by the share of their readings inside
the field + 50 m (>= 20 %; engine.run.units_inside_aoi), the cleaning drops the records outside the field + 50 m before
the cascade and clips the DIFM file to the field, and a trial design adds Plot_Id / Tgt_Rate to the outputs
(engine/clean/aoi.py through settings["aoi"]). Under every filter and section the page shows the works that support
it (engine/clean/references.py: cite(step); the "References" popover lists the full citations with their DOI).

Saved fields. A finished run is saved as <workdir>/field.json (engine/fields.py: the input roots, the decoded file,
the field of interest copied into <workdir>/aoi/, the exact settings, the result key and the outputs), so a cleaned
field is never lost when the app is closed. The sidebar lists the saved fields (newest first): Open restores the whole
screen without running the engine again (restore_field), Rename rewrites the record, Delete removes that one folder
after a confirmation. "Start over" (header, right) clears the screen and deletes nothing on disk; it asks first only
when the open input has unsaved work. The brand (name, version, palette, logos, page icon, the page's small CSS
and the map colours) is app/brand.py; the theme itself is .streamlit/config.toml.
"""
import base64
import copy
import dataclasses
import datetime as dt
import hashlib
import importlib
import json
import os
import re
import sys
import threading
import time

import numpy as np
import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _drop_stale_engine() -> None:
    """Streamlit re-executes this page from its file on every run but keeps the modules the page imported, and its
    file watcher only drops a changed module for the session that saw the change (and only for files under app/ or
    PYTHONPATH). A page opened after an update of engine/ therefore ran with the old engine and failed on a changed
    signature ("compat_settings() got an unexpected keyword argument") until the process was restarted. This compares
    the engine's source files (time and size of every .py, engine.source_stamp()) with the ones the package was
    imported from (engine.SOURCE_STAMP) and drops the whole package when a file was added, removed or changed, so that
    the imports below read the new code. A file whose time went BACK counts too: a restore of a backup (Explorer,
    robocopy and xcopy keep the backup's times) did not reload the engine while only newer times counted. An engine
    without SOURCE_STAMP was imported by an older app.py: stale. .streamlit/config.toml is still read once
    at start: a theme change needs the app started again."""
    eng = sys.modules.get("engine")
    if eng is None:                                      # not imported yet (first run of the process)
        return
    stamp, now = getattr(eng, "SOURCE_STAMP", None), getattr(eng, "source_stamp", None)
    try:
        stale = stamp is None or now is None or now() != stamp
    except OSError:                                      # pragma: no cover
        stale = False
    if stale:
        for name in [n for n in sys.modules if n == "engine" or n.startswith("engine.")]:
            sys.modules.pop(name, None)


@st.cache_resource(show_spinner=False)                  # no element before set_page_config
def _engine_lock():
    """One lock per process around the engine check, its drop and the imports below: two sessions rerunning at once
    after an update could otherwise pop the package the other was importing (KeyError: 'engine')."""
    return threading.RLock()


with _engine_lock():
    _drop_stale_engine()
    from engine import fields as ef  # noqa: E402
    from engine import run as er  # noqa: E402
    from engine.clean import yield_clean as yc  # noqa: E402
    from engine.formats import common, detect  # noqa: E402

    try:                                                 # the literature module (another builder's): guarded
        from engine.clean import references as rf
    except ImportError:                                  # pragma: no cover - fallback to FILTER_INFO['source']
        rf = None
try:
    import pydeck as pdk
except ImportError:                                      # pragma: no cover
    pdk = None

# ------------------------------------------------------------------------------------------------ brand
# app/brand.py: the name, version, palette, logo paths, page icon, the page's small CSS (inject) and the pydeck map
# colours. Streamlit puts app/ on sys.path when it runs the page; AppTest and a start from another folder may not.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
import brand  # noqa: E402

# the same staleness as the engine's (_drop_stale_engine): a brand.py whose file differs from the one the process read
# (time or size, newer or older) is read again, so that an update's version and palette show without a restart (a
# brand without SOURCE_STAMP is older)
try:
    _bst = os.stat(brand.__file__)
    if (_bst.st_mtime_ns, _bst.st_size) != getattr(brand, "SOURCE_STAMP", None):
        brand = importlib.reload(brand)
except OSError:                                          # pragma: no cover
    pass

# absolute: a relative YIELD_APP_WORKSPACE (a batch file's "ws") must compare with the absolute work folders
WORKSPACE = os.path.abspath(os.environ.get("YIELD_APP_WORKSPACE") or os.path.join(ROOT, "workspace"))
T19_DIR = os.path.join(ROOT, "examples", "trial19_sms")
EXAMPLES = [
    ("Trial 19 – SMS export (Harvest trial 19.zip)", os.path.join(T19_DIR, "Harvest trial 19.zip")),
]
AOI_EXAMPLES = [
    ("Trial 19 boundary", os.path.join(T19_DIR, "boundary.geojson")),
    ("Trial 19 trial design", os.path.join(T19_DIR, "trial-design-seed-2026.geojson")),
]
# the attribute of a boundary file that names the field (engine/clean/aoi.py NAME_ALIASES): the default field name
AOI_NAME_COLS = ("name", "field", "field_name", "fieldname", "label", "title", "descriptio", "description")
AOI_TYPES = ["zip", "geojson", "json", "gpkg", "kml", "kmz", "shp", "shx", "dbf", "prj", "cpg"]
AOI_KEYS = ("n_polygons", "n_plots", "headland_polygons", "area_ac", "id_col", "rate_col", "rates", "crs", "warnings",
            "is_plan", "needs_choice", "fields", "feature", "n_in_file")
UI_GROUPS = [("Sensor & record", ["F0", "F1", "F2", "F3", "F4"]), ("Pass structure", ["F5", "F6", "F7", "F5b"]),
             ("Overlap", ["F8"]), ("Yield outliers", ["F9", "F10", "F11"])]
SECTION_TABS = ["Corrections", "Field of interest", "Sessions & moisture", "Combines"]
PARAM_LABEL = {"min_pct": "Min %", "max_pct": "Max %", "min_mph": "Min mph", "max_mph": "Max mph",
               "max_change_per_s": "Max change per s (0.20 = 20 %)", "max_rel_error": "Max error (0.50 = 50 %)",
               "min_points": "Min points", "max_deg_per_s": "Max deg/s", "drop_start": "Drop at start",
               "drop_end": "Drop at end", "auto_tolerance_pct": "Auto tolerance %", "min_lbac": "Min wet mass lb/ac",
               "max_lbac": "Max wet mass lb/ac", "k_sd": "k (SD)", "half_window": "Half window (points)",
               "max_rel_dev": "Max deviation (0.30 = 30 %)",
               "fallback_threshold": "Fallback when auto cannot decide (0.10 = 10 %)",
               "min_threshold": "Floor of the auto threshold (0.05 = 5 %)",
               "local_radius_m": "Min control radius (m; 1.5 header widths if larger)",
               "edge_tol_m": "Same edge distance within (m)",
               "min_controls": "Min controls per record", "footprint": "Overlap footprint",
               "reference": "Dose-response reference", "y_offset": "Place a narrowed header by its Y_Offset"}
# the F8 overlap-model switches (filters.F8): choices, drawn as a select box (a check box for y_offset)
F8_CHOICES = {"footprint": list(yc.F8_FOOTPRINTS), "reference": list(yc.F8_REFERENCES), "y_offset": [True, False]}
F8_CHOICE_LABEL = {"footprint": {"swept": "swept strip (v2.4)", "chord": "chord rectangle (v2.3)"},
                   "reference": {"local": "local edge-matched controls (v2.4)", "field": "whole no-overlap band (v2.3)"}}
LAG_STAGE_LABEL = {"output": "after the cascade, output positions only (default)",
                   "before_f7": "after F6, before F7 and F8 (option, failed its test)"}
LAG_AXIS_LABEL = {"dominant": "the direction the field was harvested in (v2.4)",
                  "ew_first": "east-west first (v2.3)"}
COL_LABEL ={"yield": "Dry yield (bu/ac)", "yield_wet": "Wet yield (bu/ac)", "moisture": "Moisture (%)",
             "speed_mph": "Speed (mph)", "distance_ft": "Distance (ft)", "width_ft": "Swath width (ft)",
             "heading": "Heading (deg)", "duration_s": "Duration (s)", "wet_mass_lbac": "Wet mass (lb/ac)",
             "dataset": "Dataset / task", "order": "Record id", "time": "Time", "machine": "Combine id"}
REQUIRED = {"yield", "speed_mph", "heading"}
NOT_USED = "(not used)"
FROM_MONITOR = "(from the monitor)"
AUTO = "auto"
CROP_UNKNOWN = "(not set: small-cereal defaults)"
CORR_KEYS = ["lag_mode", "lag_records", "lag_auto", "lag_stage", "lag_axis", "harmonise", "ticket", "ticket_unit",
             "ticket_basis", "ticket_moisture", "ticket_confirms", "aoi_buffer", "aoi_clip", "std_m", "shrink_mode", "add_sym",
             "ref_machine", "same_plot", "max_factor", "crop_clean"]
TICKET_UNITS = list(getattr(er, "TICKET_UNITS", ("lb", "kg", "bu", "t")))
TICKET_UNIT_LABEL = {"lb": "lb", "kg": "kg", "bu": "bu", "t": "t (metric)"}
# the engine's machines settings know the ticket closure test (machines.ticket_confirms) in a v2 ticket engine
ENGINE_TICKET_CONFIRMS = "ticket_confirms" in (yc.DEFAULT_SETTINGS.get("machines") or {})
# the processing tree of the sidebar: the filters in execution order, grouped; the switches own the on/off state
# (keys f_<id>_on, lag_auto, harmonise, add_sym) that the settings of step 3 read
TREE_GROUPS = [("Sensor & record", ["F0", "F1", "F2", "F3", "F4"]), ("Pass structure", ["F5", "F6", "F7"]),
               ("Overlap", ["F8"]), ("Yield outliers", ["F9", "F10", "F11"]), ("Short runs", ["F5b"])]
TREE_OFF_NOTE = "off — switch it on in the processing tree"
# the step-3 tab that holds each group of the tree (a group heading of the tree opens that tab)
TREE_TAB = {"Sensor & record": "Sensor & record", "Pass structure": "Pass structure", "Overlap": "Overlap",
            "Yield outliers": "Yield outliers", "Short runs": "Pass structure", "Corrections": "Corrections",
            "Combines": "Combines", "Sessions & moisture": "Sessions & moisture", "SMS 3-sigma": "SMS 3-sigma"}
# F1 moisture window per crop (house conventions; the engine's F1_CROP_RANGES when it has them)
F1_CROP_RANGES = getattr(yc, "F1_CROP_RANGES", None) or {
    "barley": (8, 20), "wheat": (8, 20), "durum": (8, 20), "oats": (8, 20), "rye": (8, 20), "canola": (4, 16),
    "flax": (4, 16), "peas": (8, 24), "lentils": (8, 22), "corn": (10, 33), "soybeans": (8, 25)}
F1_DEFAULT_RANGE = (8, 20)
PRESELECT = getattr(er, "AOI_PRESELECT_SHARE", 0.20)
HIDE = getattr(er, "AOI_HIDE_SHARE", 0.01)
BUFFER_M = getattr(er, "AOI_BUFFER_M", 50.0)
# the app cuts the records at the boundary itself before the cleaning (the preview keeps every raw reading): the 50 m
# buffer of the engine / CLI took in the edge passes of the neighbouring fields (Trial 25: two canola tasks of the
# fields east and south in the cascade, its F10 limits and the sessions); a buffer stays an option in step 3
AOI_CUT_M = 0.0
# cleaning methods (engine settings["method"]): the OCCD cascade, the SMS 3-sigma sequence (engine/clean/sms3sigma.py),
# or both on the same readings and a comparison (engine/clean/compare.py)
METHODS = ["occd", "sms3sigma", "both"]
METHOD_LABEL = {"occd": "OCCD cascade", "sms3sigma": "SMS 3-sigma", "both": "Both, and compare"}
SMS_TAB = "SMS 3-sigma"
SMS_GROUPS = ["auto", "task", "machine", "field"]
SMS_GROUP_LABEL = {"auto": "Auto (as in SMS)", "task": "Per task", "machine": "Per combine", "field": "Whole field"}
SMS_D = dict((yc.DEFAULT_SETTINGS.get("sms3sigma") or {}))
SMS_NOT_USED = "Not used by the SMS 3-sigma method (see the SMS 3-sigma tab)."

st.set_page_config(page_title=brand.NAME, page_icon=brand.page_icon(), layout="wide")
if os.path.exists(brand.LOGO_H):                         # the horizontal logo in the sidebar, the shield when collapsed
    st.logo(brand.LOGO_H, icon_image=brand.LOGO_SHIELD if os.path.exists(brand.LOGO_SHIELD) else None, size="large")
brand.inject()                                           # the page's small CSS, once per run, after set_page_config

# ------------------------------------------------------------------------------------------------ session state
ss = st.session_state
# data keys (not widgets). field_saved = the work folder whose field.json matches this screen's last run (None when
# nothing was saved yet); field_fresh = that record still matches the settings on the page (set in step 4);
# field_request = ("open" | "delete", workdir) from the sidebar, processed at the top of the page before any widget.
SS_DEFAULTS = {"workdir": None, "cands": None, "open_log": [], "open_error": None, "open_exc": None,
               "open_request": None, "units": {}, "decoded": None, "result": None, "result_shp": None,
               "result_key": None, "aoi": None, "aoi_request": None, "aoi_error": None, "aoi_exc": None,
               "aoi_shares": {}, "aoi_preselect": None, "input_source": None, "field_saved": None,
               "field_record": None, "field_fresh": False, "field_request": None, "field_notice": None,
               "field_name_auto": None, "restored_units": None, "run_started": None}
for k, v in SS_DEFAULTS.items():
    ss.setdefault(k, v)


# ------------------------------------------------------------------------------------------------ helpers
def key_of(s: str) -> str:
    return hashlib.md5(str(s).encode("utf-8")).hexdigest()[:8]


@st.cache_data(max_entries=16, show_spinner=False)
def shp_info(path: str, mtime: float) -> dict:
    import pyogrio
    i = pyogrio.read_info(path)
    return {"fields": list(i["fields"]), "n": int(i["features"]), "crs": str(i.get("crs"))}


@st.cache_data(max_entries=8, show_spinner="Reading points for the map ...")
def shp_preview(path: str, mtime: float, ycol) -> pd.DataFrame:
    p = er.preview_points(path, ycol)
    p["color"] = er.colour_by_yield(p["yield"].values)
    return p


@st.cache_data(max_entries=8, show_spinner="Reading the strips for the map ...")
def swath_preview(path: str, mtime: float, ycol, width_ft=None, y_offset=True) -> pd.DataFrame:
    """The readings as the strips they swept (engine.run.preview_swaths; width_ft = the harvester width of the
    settings for a file without a width column) + a colour per yield. A preview problem never takes the page down:
    it falls back to the points."""
    try:
        p = er.preview_swaths(path, ycol, width_ft=width_ft, y_offset=y_offset)
    except Exception:                                    # pragma: no cover - the engine's own refusal comes at Run
        p = er.preview_points(path, ycol)
    p["color"] = er.colour_by_yield(p["yield"].values)
    return p


def strip_count_text(n_drawn: int, n_file: int) -> str:
    """'N readings', plus 'of M (a random sample)' only when preview_swaths sampled (M above its cap), else the
    readings without a position that are not drawn."""
    if n_file > er.PREVIEW_N_MAX:
        return f"{n_drawn:,} readings of {n_file:,} (a random sample)"
    if n_drawn < n_file:
        return f"{n_drawn:,} readings ({n_file - n_drawn:,} of {n_file:,} without a position, not drawn)"
    return f"{n_drawn:,} readings"


@st.cache_data(max_entries=8, show_spinner=False)
def machines_of(path: str, mtime: float, mcol, ycol) -> list:
    return er.machine_summary(path, mcol, ycol)


@st.cache_data(max_entries=8, show_spinner=False)
def crop_of_export(path: str, mtime: float):
    return er.export_crop_guess(path)


@st.cache_data(max_entries=8, show_spinner=False)
def tw_of_file(path: str, mtime: float):
    """The file's own test weight (median Yld_Mass_W / Yld_Vol_We, lb/bu; None without the columns): converts the
    grower's weight to bushels for the caption of step 3 (the engine makes the same conversion)."""
    return er.file_test_weight(path)


def cut_text(buffer_m) -> str:
    """'the field + 50 m' / 'the field' (records cut at the boundary itself) for the result captions."""
    b = _float(buffer_m)
    return "the field" + (f" + {b:g} m" if b else "")


def f9_in_bu(p: dict, has_mass: bool, tw_given, tw_file, crop_key) -> str:
    """The F9 window (wet mass, lb/ac) as wet yield in bu/ac, for the caption under F9 (Trial 25: 20-200 typed as bu/ac
    removed every point). With a wet-mass column the file's own Yld_Mass_W / Yld_Vol_We links mass and yield (else the
    test weight given, else the crop table); without one F9 is the wet yield x the test weight given (engine), so that
    one is used."""
    if has_mass:
        tw, src = ((tw_file, "the file's own Yld_Mass_W / Yld_Vol_We") if tw_file else
                   (tw_given, "the test weight given") if tw_given else
                   (common.CROPS[crop_key][0], f"crop table: {crop_key}") if crop_key in common.CROPS else (None, None))
    else:
        tw, src = (tw_given, "the test weight given") if tw_given else (None, None)
    if not tw:
        return ("In bu/ac: give the test weight (Column mapping) to see the wet yield this window stands for." if has_mass
                else "No wet-mass column: F9 needs the test weight (Column mapping); without it F9 is switched off.")
    lo, hi = float(p["min_lbac"]), float(p["max_lbac"])
    return (f"= {lo / tw:,.1f}–{hi / tw:,.1f} bu/ac of wet yield at {tw:.2f} lb/bu ({src}). For a wet-yield window "
            f"of A–B bu/ac, enter A × {tw:.2f} and B × {tw:.2f} lb/ac.")


@st.cache_data(show_spinner=False)
def moisture_median(path: str, mtime: float, col: str):
    """Median of the export's moisture column (None when it cannot be read): the 'set the crop' check of step 3."""
    try:
        import pyogrio
        v = pd.to_numeric(pyogrio.read_dataframe(path, columns=[col], read_geometry=False)[col], errors="coerce")
        v = v[(v > 0) & np.isfinite(v)]
        return float(v.median()) if len(v) else None
    except Exception:
        return None


def mtime(p: str) -> float:
    return os.path.getmtime(p) if os.path.exists(p) else 0.0


@st.cache_data(max_entries=16, show_spinner=False)
def yield_mean_of(path, mtime: float, col):
    """The mean of the DIFM column over the kept points (the 'Mean yield' metric of step 4)."""
    return ef.yield_mean(path, col)


def show_warnings(ws, title="Warnings", limit=12):
    ws = [str(w) for w in (ws or [])]
    if ws:
        more = f"\n- ... and {len(ws) - limit} more (see the report)" if len(ws) > limit else ""
        st.warning(f"**{title}**\n" + "\n".join(f"- {w}" for w in ws[:limit]) + more, icon=":material/warning:")


def file_download(label, path, mime, primary=False, icon=":material/download:", where="results"):
    """A download button whose data is read only when clicked; `where` keeps the keys unique when the same file is
    offered in two steps."""
    if path and os.path.exists(path):
        st.download_button(label, data=lambda p=path: open(p, "rb").read(), file_name=os.path.basename(path),
                           mime=mime, type="primary" if primary else "secondary", icon=icon, on_click="ignore",
                           key=f"dl_{where}_{key_of(path)}")


def request_open(source):
    ss.open_request = source


def request_aoi(source):
    ss.aoi_request = source


def upload_key(name: str) -> str:
    """The key of a file uploader: an uploader cannot be set through the session state, so Start over remounts the
    two uploaders with a new key (upload_nonce) and the browser forgets the files it was showing."""
    return f"{name}_{ss.get('upload_nonce', 0)}"


def request_aoi_from_widgets():
    """The 'Load field' button (a callback, so that the request is processed at the top of the block in the same run):
    the uploaded files first, else the typed path."""
    ups = ss.get(upload_key("aoi_uploads"))
    if ups:
        ss.aoi_request = ("upload", list(ups))
    elif (ss.get("aoi_path") or "").strip():
        ss.aoi_request = ("path", ss.aoi_path)
    else:
        st.toast("Upload a polygon file or type a path first", icon=":material/info:")


def clear_aoi():
    ss.aoi, ss.aoi_error, ss.aoi_exc, ss.aoi_preselect = None, None, None, None


# A widget that stays on the page across a rerun must be ASSIGNED its new value, never deleted: Streamlit sends a value
# to the browser only for a key the script set (set_value); a deleted key leaves the browser's old value in place and
# the next interaction sends it back, so the server falls back to the stale value one rerun later. The tree switches,
# the two path boxes and the saved-fields selectbox are always on the page; the step-3 inputs are when an input is
# open. AppTest rebuilds the widgets from the server's state and cannot see the difference, so the browser is the
# only check of this rule.
def reset_tree_switches():
    for fid, d0 in yc.DEFAULT_SETTINGS["filters"].items():
        ss[f"f_{fid}_on"] = bool(d0["on"])
    ss.lag_auto = ss.harmonise = ss.add_sym = True


def reset_settings():
    """'Reset to house standard' (a callback, so it runs before the widgets are drawn): every step-3 input and tree
    switch back to its default. The defaults of the inputs whose default depends on the file (crop and its F1 window,
    column mapping, output name) were recorded while step 3 was drawn (ss.step3_defaults); the per-machine totals
    editor cannot be set through the session state and is remounted with a new key (mt_nonce)."""
    for k, v in (ss.get("step3_defaults") or {}).items():
        ss[k] = copy.deepcopy(v)
    reset_tree_switches()
    ss.mt_nonce = ss.get("mt_nonce", 0) + 1


# ------------------------------------------------------------------------------------------------ start over / fields
def start_over():
    """Clear the screen: every session key (data and widgets, so the tree goes back to the house standard) and the
    defaults again. Nothing on disk is touched: the saved fields stay. Used inline (before the widgets are drawn) and
    as a button callback; dialog_done tells a dialog body to rerun the whole page. The widgets that stay on the page
    (tree switches, path boxes, the saved-fields selectbox) are assigned their default, not deleted (see above); the
    step-3 inputs leave the page with the input and may be deleted; the uploaders and the totals editor are remounted
    with a new key."""
    keep = {"upload_nonce": ss.get("upload_nonce", 0) + 1, "mt_nonce": ss.get("mt_nonce", 0) + 1,
            "saved_field": ss.get("saved_field")}
    for k in list(ss.keys()):
        del ss[k]
    for k, v in SS_DEFAULTS.items():
        ss[k] = copy.deepcopy(v)
    reset_tree_switches()
    ss.local_path = ss.aoi_path = ""
    ss.upload_nonce, ss.mt_nonce = keep["upload_nonce"], keep["mt_nonce"]
    if keep["saved_field"] is not None:                   # the sidebar keeps its selection (validated when drawn)
        ss.saved_field = keep["saved_field"]
    ss.dialog_done = True


def is_dirty() -> bool:
    """An input is open and its state is not saved: opened / decoded / settings changed without a completed run, or
    the settings changed after the last save (field_fresh is set in step 4 on every run of the page)."""
    return ss.cands is not None and not bool(ss.get("field_fresh"))


OCCD_ONLY_KEYS = ("filters", "lag_correction", "lag_stage", "lag_axis", "harmonise_machines")
OCCD_ONLY_MACHINES = ("harmonise", "reference", "min_pairs", "min_pass_pairs", "ci", "min_factor", "max_factor",
                      "same_plot_only", "bootstrap_reps", "seed", "pair_max_overlap", "ticket_confirms",
                      "ticket_close_tol")


def run_key_settings(settings: dict) -> dict:
    """The part of the merged settings the chosen method uses: the OCCD cascade ignores the SMS 3-sigma options (and
    its key is then exactly the one of v2.2), the SMS 3-sigma method ignores the filters, the flow delay and the
    combine harmonisation; 'both' uses everything."""
    S = copy.deepcopy(settings or {})
    m = S.get("method", "occd")
    if m == "occd":
        S.pop("method", None)
        S.pop("sms3sigma", None)
    elif m == "sms3sigma":
        for k in OCCD_ONLY_KEYS:
            S.pop(k, None)
        for k in OCCD_ONLY_MACHINES:
            (S.get("machines") or {}).pop(k, None)
    return S


def run_key_of(shp: str, settings: dict, aoi_path: str | None) -> str:
    """What identifies a run: the file, the merged settings the method uses and the field of interest (the result is
    'previous run' when the key of the page no longer matches the key stored with the result)."""
    return json.dumps({"shp": shp, "settings": run_key_settings(settings), "aoi": aoi_path}, sort_keys=True,
                      default=str)


PRE_V24_NOTE = ("This field was cleaned before v2.4 (OCCD {version}), with the v2.3 overlap model. Run cleaning cleans it "
                "with the v2.4 model, the settings on the screen. To repeat the v2.3 cleaning instead, set step 3's "
                "(v2.3) options of F8 and of the flow-delay scan, F8's Y_Offset off and its floor 0 (F8 switched off in "
                "the tree: switch it on to change them, then off again; README: 'The overlap model of v2.4').")


def cleaned_before_v24(rec: dict, R: dict | None, S: dict) -> bool:
    """A saved field cleaned before v2.4, with the v2.3 overlap model. Its result's settings (R['settings'], the merged
    settings every run writes) hold no lag_axis, a key every v2.4 run writes; without the cleaning JSON the record
    tells (a legacy folder, or an app_version below 2.4; not the record's settings: a 2.4.0 record has no lag_axis
    there either). False for an SMS 3-sigma result: it has no overlap filter, and v2.4 cleans it the same."""
    if R is not None:
        RS = R.get("settings") if isinstance(R.get("settings"), dict) else {}
        return (RS.get("method") or S.get("method") or "occd") != "sms3sigma" and "lag_axis" not in RS
    if (S.get("method") or "occd") == "sms3sigma":
        return False
    v = [int(x) for x in re.findall(r"\d+", str(rec.get("app_version") or ""))[:2]]
    return (rec.get("input") or {}).get("kind") == "legacy" or not v or v < [2, 4]


def v23_settings(S: dict) -> dict:
    """The saved settings of a field cleaned before v2.4 with the LEGACY_V23 value of every v2.4 key they lack: what
    produced its result. Its run key then differs from the v2.4 defaults the page shows and the result is 'previous
    run' (before, the v2.4 defaults filled the gaps and an old result passed for a current one); the (v2.3) choices of
    step 3 give the same key again. lag_axis only with the flow-delay correction on: off, the axis changes no number
    (only the scan's figure) and its widget is disabled."""
    S = copy.deepcopy(S)
    F = S.get("filters") if isinstance(S.get("filters"), dict) else {}
    S["filters"] = F
    F["F8"] = F8 = F.get("F8") if isinstance(F.get("F8"), dict) else {}
    for k, v in yc.LEGACY_V23["filters"]["F8"].items():
        F8.setdefault(k, v)
    S.setdefault("lag_stage", yc.LEGACY_V23["lag_stage"])
    if S.get("lag_correction", "auto") != "none":
        S.setdefault("lag_axis", yc.LEGACY_V23["lag_axis"])
    return S


def aoi_field_name(aoi) -> str | None:
    """The field's name from the field-of-interest file: the chosen feature's name (several boundaries in one file)
    or a single-valued name-like attribute; None when the file names nothing (the Trial 19 boundary)."""
    if not aoi:
        return None
    f = aoi.get("feature")
    for x in aoi.get("fields") or []:
        if f and x.get("index") == f and str(x.get("name") or "").strip():
            return str(x["name"]).strip()
    gdf = (aoi.get("plan") or {}).get("gdf")
    if gdf is None:
        return None
    try:
        for c in gdf.columns:
            if str(c).lower() in AOI_NAME_COLS:
                vals = {str(v).strip() for v in gdf[c].dropna() if str(v).strip() and str(v).strip().lower() != "nan"}
                if len(vals) == 1:
                    return vals.pop()
    except Exception:
        return None
    return None


def default_field_name(aoi, tag) -> str:
    return aoi_field_name(aoi) or ef.clean_name(tag) or "field"


def seed_field_name(aoi, tag):
    """The 'Field name' box of step 4 follows the default (the field of interest's name, else the output name) until
    the user types a name of their own (field_name_auto None); must run before the widget is drawn."""
    d = default_field_name(aoi, tag)
    if "field_name" not in ss:
        ss.field_name, ss.field_name_auto = d, d
    elif ss.field_name_auto is not None and ss.field_name in ("", ss.field_name_auto) and d != ss.field_name_auto:
        ss.field_name, ss.field_name_auto = d, d
    elif not ss.field_name and ss.get("field_saved") == ss.workdir and ss.get("field_record"):
        ss.field_name = ss.field_record["name"]           # an emptied box shows the saved name again (never renamed to nothing)


def field_name_changed():
    """The user typed a field name: it is kept as is, and a saved field is renamed on disk at once. An emptied box
    renames nothing: the saved name comes back into the box."""
    ss.field_name_auto = None
    name = ef.clean_name(ss.get("field_name"))
    saved = ss.workdir and ss.get("field_saved") == ss.workdir
    if not name:
        if saved and ss.get("field_record"):
            ss.field_name = ss.field_record["name"]
            st.toast(f"The field name cannot be empty: {ss.field_name} is kept", icon=":material/info:")
        return
    if saved:
        try:
            ss.field_record = ef.rename_field(ss.workdir, name)
            sync_saved_field(ss.workdir)
            st.toast(f"Renamed: {name}", icon=":material/edit:")
        except (ValueError, OSError) as e:
            st.toast(f"Rename failed: {e}", icon=":material/error:")


def request_field(action: str, workdir: str):
    """A sidebar / dialog button (callback): the request is processed at the top of the next run, before any widget,
    so that the restored state reaches every widget."""
    ss.field_request = (action, workdir)
    ss.dialog_done = True


def close_dialog():
    ss.dialog_done = True


def sync_saved_field(wd: str):
    """After a rename (a callback): the sidebar selectbox keeps `wd` selected under its new label (assigned, so the
    label goes to the browser with set_value). Known limit: the browser's select shows the new label only at the next
    interaction (its search input is not refreshed by that run); the toast and the header caption name it at once."""
    ss.saved_field = wd


def current_field_name() -> str | None:
    """The name shown under 'Start over': the saved field's name, else the pending name of the open input."""
    if ss.workdir and ss.get("field_saved") == ss.workdir and ss.get("field_record"):
        return ss.field_record.get("name")
    if ss.cands is not None:
        return ss.get("field_name") or None
    return None


def _num(v, like, default=None):
    """A session value typed like the widget's default (an int number_input refuses a float); `default` when the
    saved value is not a number (a hand-edited record), so that one bad parameter only falls back to the default."""
    try:
        return int(round(float(v))) if isinstance(like, int) and not isinstance(like, bool) else float(v)
    except (TypeError, ValueError):
        return default


def _float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def step3_guesses(D, shp: str):
    """The crop and the standard moisture that step 3 proposes: from the decoder (its options, else the crop its
    calibration used), else from the export's product column."""
    crop_guess, std_m_guess = None, None
    if D:
        rep = D["report"]
        crop_guess = (rep.get("options") or {}).get("crop")
        cal = rep.get("calibration") or {}
        units_cal = cal.get("units")
        if isinstance(units_cal, list) and units_cal and isinstance(units_cal[0], dict):
            # a crop only when every unit names the same one (canola + an unnamed 'crop 47' is not canola)
            used = {str(u.get("crop_used")).strip().lower() if u.get("crop_used") else None for u in units_cal}
            crop_guess = crop_guess or (used.pop() if len(used) == 1 else None)
            sms = {float(u["std_moisture_pct"]) for u in units_cal if u.get("std_moisture_pct") is not None}
            std_m_guess = sms.pop() if len(sms) == 1 else None
        if (rep.get("options") or {}).get("std_moisture_pct") is not None:
            std_m_guess = float(rep["options"]["std_moisture_pct"])
    else:
        crop_guess = crop_of_export(shp, mtime(shp))
    return crop_guess, std_m_guess


def default_tag(cand, D) -> str:
    """The default output name: the decoder's tag for a raw input, else the export's candidate tag."""
    return ((D or {}).get("tag") or "") if cand["kind"] == "raw" else (er.candidate_tag(cand) or "")


def step3_defaults(shp: str, det: dict, fields: list, crop_guess, tag: str) -> dict:
    """Every step-3 input key with its house default for this file: the filters' thresholds, the F8 mode, the crop
    and its F1 window, the column mapping as detected, the corrections, the field-of-interest buffer, the moisture
    basis and the combines. 'Reset to house standard' assigns them (reset_settings) and Open starts from them before
    the saved settings are laid over (apply_settings_to_widgets): every key is assigned, so a value left in the
    browser from the previous input cannot come back."""
    SK = key_of(shp)
    crop_key = crop_guess if crop_guess in common.CROPS else None
    lo, hi = F1_CROP_RANGES.get(crop_key, F1_DEFAULT_RANGE)
    W = {}
    for fid, d0 in yc.DEFAULT_SETTINGS["filters"].items():
        for name, v0 in d0.items():
            if name not in ("on", "threshold"):
                W[f"f_{fid}_{name}"] = v0
    W.update({"f_F1_min_pct": float(lo), "f_F1_max_pct": float(hi), "f_F1_crop": crop_key,
              "f_F8_mode": "auto", "f_F8_pct": 10.0,
              f"crop_clean_{SK}": crop_key or CROP_UNKNOWN, f"hw_{SK}": None, f"twf9_{SK}": None,
              f"tag_{SK}": tag or "",
              "lag_mode": "auto", "lag_records": 0, "lag_stage": yc.DEFAULT_SETTINGS["lag_stage"],
              "lag_axis": yc.DEFAULT_SETTINGS["lag_axis"],
              "ticket": None, "ticket_unit": "lb", "ticket_basis": "dry", "ticket_moisture": None,
              "aoi_buffer": float(AOI_CUT_M), "aoi_clip": True, "std_m": None, "shrink_mode": "auto",
              "ref_machine": AUTO, "same_plot": True, "max_factor": 10.0})
    if ENGINE_TICKET_CONFIRMS:
        W["ticket_confirms"] = True
    W.update(sms_widget_defaults())
    for k in yc.COLUMN_KEYS:
        W[f"col_{k}_{SK}"] = det[k] if det[k] in fields else NOT_USED
    return W


def sms_widget_defaults() -> dict:
    """The house defaults of the method selector and the SMS 3-sigma inputs of step 3."""
    return {"clean_method": "occd", "s3_group": SMS_D.get("group_by", "auto"), "s3_k": float(SMS_D.get("k_sd", 3.0)),
            "s3_drop": float(SMS_D.get("sd_drop_pct", 25.0)), "s3_passes": int(SMS_D.get("max_yield_passes", 5)),
            "s3_clip": True, "s3_swath": True, "s3_scale": True, "s3_speed": True, "s3_moist": True, "s3_yield": True,
            "s3_minyield": float(SMS_D.get("min_yield") or 0.0)}


def apply_settings_to_widgets(S: dict, shp: str, rec: dict, D, cand):
    """Write the saved settings into the widget keys of step 3 (and the tree switches) before the widgets are drawn,
    so that the page shows what the saved run used and recomputes the same settings (the result is then not
    'previous run'). Every step-3 key is assigned, the house default where the record says nothing (a key left alone
    would keep the browser's value from the input that was on the screen before). A saved value of the wrong type
    falls back to the default. The per-machine totals of the data editor cannot be set through the session state."""
    SK = key_of(shp)
    info = shp_info(shp, mtime(shp))
    fields = list(info["fields"])
    det = yc.detect_columns(fields)
    W = step3_defaults(shp, det, fields, step3_guesses(D, shp)[0], default_tag(cand, D))
    crop_key = S.get("crop") if S.get("crop") in common.CROPS else None
    lo, hi = F1_CROP_RANGES.get(crop_key, F1_DEFAULT_RANGE)
    # the F1 window of the saved crop; f_F1_crop marks it so that the crop seed of step 3 does not overwrite it
    W.update({"f_F1_min_pct": float(lo), "f_F1_max_pct": float(hi), "f_F1_crop": crop_key,
              f"crop_clean_{SK}": crop_key or CROP_UNKNOWN})
    F = S.get("filters") if isinstance(S.get("filters"), dict) else {}
    for fid, d0 in yc.DEFAULT_SETTINGS["filters"].items():
        p = F.get(fid) if isinstance(F.get(fid), dict) else {}
        W[f"f_{fid}_on"] = bool(p.get("on", d0["on"]))
        for name, v0 in d0.items():
            if name in ("on", "threshold") or p.get(name) is None:
                continue
            k = f"f_{fid}_{name}"
            if name in F8_CHOICES:                      # the F8 overlap-model switches: a choice, not a number
                if p[name] in F8_CHOICES[name]:
                    W[k] = p[name]
                continue
            W[k] = _num(p[name], float(v0) if fid == "F1" else v0, W.get(k))
        if fid == "F8":
            th = p.get("threshold", "auto")
            if th not in ("auto", None) and _float(th) is not None:
                W["f_F8_mode"], W["f_F8_pct"] = "manual", _float(th) * 100.0
    for k, v in (S.get("cols") or {}).items() if isinstance(S.get("cols"), dict) else []:
        W[f"col_{k}_{SK}"] = v if (v and v in fields) else NOT_USED
    W[f"hw_{SK}"] = _float(S.get("harvester_width_ft"))
    W[f"twf9_{SK}"] = _float(S.get("test_weight_lb_bu"))
    lag = S.get("lag_correction", "auto")
    W["lag_auto"] = lag != "none"
    if S.get("lag_stage") in yc.LAG_STAGES:
        W["lag_stage"] = S["lag_stage"]
    if S.get("lag_axis") in yc.LAG_AXES:
        W["lag_axis"] = S["lag_axis"]
    if isinstance(lag, (int, float)) and not isinstance(lag, bool):
        W["lag_mode"], W["lag_records"] = "fixed", int(lag)
    T = S.get("scale_ticket") if isinstance(S.get("scale_ticket"), dict) else None
    if T and _float(T.get("value")):
        W["ticket"] = _float(T["value"])
        W["ticket_unit"] = T.get("unit") if T.get("unit") in TICKET_UNITS else "lb"
        W["ticket_basis"] = T.get("basis") if T.get("basis") in ("wet", "dry") else "wet"
        W["ticket_moisture"] = _float(T.get("moisture_pct"))
    elif _float(S.get("scale_ticket_bu")):                # a legacy record
        W["ticket"], W["ticket_unit"] = _float(S["scale_ticket_bu"]), "bu"
        W["ticket_basis"] = S.get("scale_ticket_basis") if S.get("scale_ticket_basis") in ("wet", "dry") else "wet"
    if S.get("tag"):
        W[f"tag_{SK}"] = str(S["tag"])
    M = S.get("moisture") if isinstance(S.get("moisture"), dict) else {}
    W["std_m"] = _float(M.get("standard_pct"))
    if M.get("shrink") in ("auto", "one_sided", "symmetric"):
        W["shrink_mode"] = M["shrink"]
    W["add_sym"] = bool(M.get("add_symmetric_column", True))
    MC = S.get("machines") if isinstance(S.get("machines"), dict) else {}
    W["harmonise"] = bool(MC.get("harmonise", S.get("harmonise_machines", True)))
    ref = MC.get("reference") or AUTO
    machines = [str(m) for m in ((rec.get("summary") or {}).get("machines") or [])]
    W["ref_machine"] = ref if (ref == AUTO or str(ref) in machines) else AUTO
    W["same_plot"] = bool(MC.get("same_plot_only", True))
    if _float(MC.get("max_factor")) is not None:
        W["max_factor"] = _float(MC["max_factor"]) * 100.0
    if ENGINE_TICKET_CONFIRMS and "ticket_confirms" in MC:
        W["ticket_confirms"] = bool(MC["ticket_confirms"])
    A = S.get("aoi") if isinstance(S.get("aoi"), dict) else {}
    if _float(A.get("buffer_m")) is not None:
        W["aoi_buffer"] = _float(A["buffer_m"])
    if A.get("clip_output") is not None:
        W["aoi_clip"] = bool(A["clip_output"])
    m = str(S.get("method") or "occd")
    W["clean_method"] = m if m in METHODS else "occd"
    P3 = S.get("sms3sigma") if isinstance(S.get("sms3sigma"), dict) else {}
    if P3.get("group_by") in SMS_GROUPS:
        W["s3_group"] = P3["group_by"]
    for k, wk in (("k_sd", "s3_k"), ("sd_drop_pct", "s3_drop")):
        if _float(P3.get(k)) is not None:
            W[wk] = _float(P3[k])
    if _float(P3.get("max_yield_passes")) is not None:
        W["s3_passes"] = int(round(_float(P3["max_yield_passes"])))
    for k, wk in (("clip", "s3_clip"), ("swath", "s3_swath"), ("scale_per_area", "s3_scale"), ("speed", "s3_speed"),
                  ("moisture", "s3_moist"), ("yield", "s3_yield")):
        if k in P3:
            W[wk] = bool(P3[k])
    if "min_yield" in P3:
        W["s3_minyield"] = _float(P3["min_yield"], 0.0) or 0.0
    for k, v in W.items():
        ss[k] = v


def restore_field(workdir: str):
    """Open a saved field: the screen comes back as it was at the end of its run WITHOUT running the engine. The
    input is detected again from its roots (header reads only), the decoded file and the field of interest are read
    from the work folder, the settings go to the widget keys, the result comes from the cleaning JSON and the result
    key is recomputed from the saved settings so that the result is not 'previous run'. Missing pieces are said once
    (field_notice) and the page offers to run again. A result cleaned before v2.4 (with the v2.3 overlap model) is
    'previous run': the page shows the v2.4 defaults, which would clean it differently (cleaned_before_v24,
    v23_settings); with missing outputs or field of interest the notice says so too."""
    try:
        rec = ef.load_field(workdir) or ef.legacy_record(workdir)
    except ValueError as e:
        ss.field_notice = ("error", str(e))
        return
    if rec is None:
        ss.field_notice = ("error", f"No saved field in {workdir}")
        return
    try:
        _restore_field(rec, workdir)
    except Exception as e:                                # a record of the wrong shape must not take the page down
        start_over()
        ss.field_notice = ("error", f"This field could not be opened ({type(e).__name__}): {e}")
    ss.saved_field = workdir                              # the sidebar shows the field that is on the screen


def _restore_field(rec: dict, workdir: str):
    start_over()
    ss.workdir = workdir
    log = ss.open_log.append
    log(f"reopening the saved field '{rec['name']}' from {workdir}")
    inp = rec.get("input") or {}
    roots = [ef.abspath(r, workdir) for r in (inp.get("roots") or [])]
    roots = [r for r in roots if r and os.path.isdir(r)]
    if not roots:
        ss.open_error = ("The input of this field is not where it was (roots: "
                         + ", ".join(str(r) for r in (inp.get("roots") or [])) + "). Open the data again.")
        ss.field_saved, ss.field_record, ss.field_name, ss.field_name_auto = workdir, rec, rec["name"], None
        return
    cands = detect.detect(roots)
    cands.roots = list(roots)
    for x in cands:
        log("found: " + x["label"])
    for n in cands.notes:
        log("note: " + n)
    ss.cands = cands
    ss.input_source = {"kind": inp.get("kind") or "path", "paths": list(inp.get("paths") or []), "roots": list(roots)}
    ss.field_saved, ss.field_record, ss.field_name, ss.field_name_auto = workdir, rec, rec["name"], None
    if not cands:
        ss.open_error = cands.message or "Nothing recognised in the input of this field."
        return
    idx = int(inp.get("candidate_index") or 0)
    if inp.get("label"):
        idx = next((i for i, c in enumerate(cands) if c["label"] == inp["label"]), idx)
    idx = min(max(idx, 0), len(cands) - 1)
    if len(cands) > 1:
        ss.cand_idx = idx
    cand = cands[idx]
    CK = key_of(cand.get("path") or cand["probe"].root)
    shp = None
    if cand["kind"] == "raw":
        dshp = ef.abspath(rec.get("decoded_shp"), workdir)
        rj = ef.abspath(inp.get("decode_report"), workdir)
        if dshp and os.path.exists(dshp) and rj and os.path.exists(rj):
            with open(rj, encoding="utf-8") as f:
                rep_ = json.load(f)
            D = {"shp": dshp, "zip": os.path.splitext(dshp)[0] + ".zip", "report": rep_, "report_json": rj,
                 "tag": inp.get("tag") or os.path.basename(dshp).replace("_decoded.shp", ""),
                 "n": int(inp.get("n_readings") or rep_.get("n_readings") or 0), "cand": CK,
                 "unit_ids": list(inp.get("units") or [])}
            D["source"] = er.decode_source(D)
            ss.decoded, shp = D, dshp
            opts = inp.get("decode_options") or rep_.get("options") or {}
            ss[f"crop_{CK}"] = opts.get("crop") if opts.get("crop") in common.CROPS else FROM_MONITOR
            if opts.get("test_weight_lb_bu") is not None:
                ss[f"tw_{CK}"] = float(opts["test_weight_lb_bu"])
            if opts.get("std_moisture_pct") is not None:
                ss[f"sm_{CK}"] = float(opts["std_moisture_pct"])
            if opts.get("shrink") in ("one_sided", "symmetric"):
                ss[f"shrink_{cand['decoder']}_{CK}"] = opts["shrink"]
            kw = inp.get("decoder_kwargs") or rep_.get("decoder_kwargs") or {}
            if kw.get("calibration") in ("task", "latest"):
                ss[f"cal_{CK}"] = kw["calibration"]
            if kw.get("flow_delay_s") is not None:
                ss[f"fd_{CK}"] = float(kw["flow_delay_s"])
            if kw.get("moisture_delay_s") is not None:
                ss[f"md_{CK}"] = float(kw["moisture_delay_s"])
            if inp.get("units"):
                ss.restored_units = list(inp["units"])
        else:
            ss.field_notice = ("info", "The decoded data of this field is not in its folder any more: decode it "
                                       "again in step 2, then run the cleaning.")
    else:
        shp = cand["path"]
    A = rec.get("aoi") if isinstance(rec.get("aoi"), dict) else {}
    aoi_missing = None
    if A.get("path"):
        ap = ef.abspath(A["path"], workdir)
        if ap and os.path.exists(ap):
            do_load_aoi(("path", ap))
            if ss.aoi is not None and A.get("feature") is not None:
                ss[f"aoi_feature_{ss.aoi['key']}"] = int(A["feature"])
            if ss.aoi is not None and inp.get("aoi_shares") and cand["kind"] == "raw":
                ss.aoi_shares[(cand["probe"].root, ss.aoi["key"])] = dict(inp["aoi_shares"])
        else:
            aoi_missing = ap
    if shp is None:
        return
    S = copy.deepcopy(rec.get("settings") if isinstance(rec.get("settings"), dict) else {})
    apply_settings_to_widgets(S, shp, rec, ss.decoded if cand["kind"] == "raw" else None, cand)
    outputs = ef.outputs_exist(rec, workdir)
    if aoi_missing or not outputs:
        # no current result: the page offers to run again; a field cleaned before v2.4 is said to be one, because that
        # run would use the v2.4 model the widgets show, not the one that cleaned it
        try:
            R0 = ef.load_result(rec, workdir)
        except (OSError, ValueError):
            R0 = None
        note = (" " + PRE_V24_NOTE.format(version=rec.get("app_version") or "older")
                if cleaned_before_v24(rec, R0, S) else "")
        if aoi_missing:
            # the saved result was clipped and tagged with a field of interest that is gone: like missing outputs,
            # the result is not shown as current (the page's settings would no longer match it)
            ss.field_notice = ("info", f"The field of interest of this field is missing ({aoi_missing}): load it again "
                                       "in step 1 and run the cleaning (the settings are restored)." + note)
        else:
            ss.field_notice = ("info", "The outputs of this field are no longer in its folder: run the cleaning again "
                                       "to rebuild them (the settings are restored)." + note)
        return
    R = ef.load_result(rec, workdir)
    if R is None:
        return
    ss.result, ss.result_shp = R, shp
    aoi_path = ss.aoi["path"] if ss.aoi is not None else None
    if aoi_path and isinstance(S.get("aoi"), dict):
        S["aoi"]["file"] = aoi_path                       # the copy in <workdir>/aoi/ is what the page now uses
    elif not aoi_path:
        S.pop("aoi", None)
    if cleaned_before_v24(rec, R, S):
        S = v23_settings(S)
        ss.field_notice = ("info", PRE_V24_NOTE.format(version=rec.get("app_version") or "older")
                           + " Its result counts as the previous run: step 4 hides it while the settings on the "
                             "screen differ from the ones that cleaned it.")
    try:
        merged = yc.merge_settings(er.compat_settings(S, shp=shp)[0])
        ss.result_key = run_key_of(shp, merged, aoi_path)
    except ValueError:
        ss.result_key = None
    ss.field_fresh = True


def autosave_field(R: dict, shp: str, run_key: str, S: dict, aoi, cand, cand_idx: int, duration_s: float | None):
    """Write <workdir>/field.json at the end of a successful run and say so with a toast."""
    inp = dict(ss.input_source or {"kind": "path", "paths": [], "roots": []})
    inp.update({"candidate_index": int(cand_idx), "label": cand["label"],
                "format": "export" if cand["kind"] == "export" else cand["decoder"], "tag": S.get("tag")})
    D = ss.decoded if (cand["kind"] == "raw" and ss.decoded) else None
    if D:
        rep_ = D.get("report") or {}
        inp.update({"units": list(D.get("unit_ids") or []), "decode_options": rep_.get("options"),
                    "decoder_kwargs": rep_.get("decoder_kwargs"), "decode_report": D.get("report_json"),
                    "n_readings": D.get("n"),
                    "aoi_shares": (ss.aoi_shares.get((cand["probe"].root, aoi["key"])) if aoi else None)})
    A = None
    if aoi:
        A = {"path": aoi["path"], "name": aoi.get("name"), "feature": aoi.get("feature"),
             **{k: aoi.get(k) for k in ("id_col", "rate_col", "n_polygons", "n_plots", "headland_polygons",
                                         "area_ac", "crs")}}
    prev = ss.get("field_record") if ss.get("field_saved") == ss.workdir else None
    # the box's name, else the name the field already has (an emptied box renames nothing), else the default
    name = ef.clean_name(ss.get("field_name")) or (prev or {}).get("name") or default_field_name(aoi, S.get("tag"))
    rec = ef.make_record(ss.workdir, name, inp, S, R, run_key, brand.VERSION,
                         decoded_shp=D["shp"] if D else None, aoi=A, difm_column=er.recommended_yield_column(R)[0],
                         run_at=dt.datetime.now().isoformat(timespec="seconds"), duration_s=duration_s,
                         created=(prev or {}).get("created"))
    rec["method"] = R.get("method") or "occd"
    cm = (R.get("methods") or {}).get("comparison")
    if cm:                                                # 'both': the SMS 3-sigma run and the comparison in a line
        m3 = (R.get("methods") or {}).get("sms3sigma") or {}
        rec["comparison"] = {"agreement_pct": cm.get("agreement_pct"), "counts": cm.get("counts"),
                             "mean_occd": cm.get("mean_occd"), "mean_sms3sigma": cm.get("mean_sms3sigma"),
                             "sms3sigma_n_kept": m3.get("n_kept")}
    ef.save_field(ss.workdir, rec)
    ss.field_saved, ss.field_record, ss.field_fresh = ss.workdir, rec, True
    ss.saved_field = ss.workdir                           # the sidebar selects the field just saved (assigned, see above)
    st.toast(f"Saved: {rec['name']}", icon=":material/save:")


def delete_dialog(rec: dict):
    """The confirmation of Delete (sidebar). The buttons work through callbacks (request_field / close_dialog) and
    the body reruns the page once a callback ran: a dialog is a fragment, so an inline button would rerun only the
    dialog, and AppTest sees the callbacks too."""
    wd = rec["workdir"]
    try:
        rel = os.path.relpath(wd, WORKSPACE) if os.path.commonpath([wd, WORKSPACE]) == os.path.normpath(WORKSPACE) else wd
    except ValueError:                                     # different drives
        rel = wd

    @st.dialog(f"Delete {rec['name']}?")
    def _d():
        st.write(f"This removes the folder workspace/{rel} with its input, decoded data and outputs. This cannot be "
                 "undone.")
        with st.container(horizontal=True):
            st.button("Delete", type="primary", icon=":material/delete:", key="field_delete_go",
                      on_click=request_field, args=("delete", wd))
            st.button("Cancel", key="field_delete_cancel", on_click=close_dialog)
        if ss.get("dialog_done"):
            st.rerun()
    _d()


@st.dialog("Start over?")
def start_over_dialog():
    st.write("The screen is cleared; saved fields are kept.")
    with st.container(horizontal=True):
        st.button("Start over", type="primary", icon=":material/restart_alt:", key="start_over_go", on_click=start_over)
        st.button("Cancel", key="start_over_cancel", on_click=close_dialog)
    if ss.get("dialog_done"):
        st.rerun()


def process_field_request():
    """The sidebar's Open / Delete, run at the top of the page before any widget is drawn."""
    ss.pop("dialog_done", None)
    req, ss.field_request = ss.get("field_request"), None
    if not req:
        return
    action, wd = req
    if action == "open":
        with st.spinner("Opening the saved field ..."):
            restore_field(wd)
    elif action == "delete":
        try:                                               # an unreadable field.json is listed exactly so it can be deleted
            name = (ef.load_field(wd) or ef.legacy_record(wd) or {}).get("name") or ef.folder_tag(wd)
        except ValueError:
            name = ef.folder_tag(wd)
        try:
            ef.delete_field(WORKSPACE, wd)
            if ss.workdir and os.path.normcase(os.path.abspath(ss.workdir)) == os.path.normcase(os.path.abspath(wd)):
                start_over()
            ss.field_notice = ("toast", f"Deleted: {name}")
        except (ValueError, OSError) as e:
            ss.field_notice = ("error", f"Delete failed: {e}")
        # the selectbox: a deleted field is no longer an option, saved_fields_block then selects the newest
    ss.pop("dialog_done", None)


def show_field_notice():
    """One message about the saved fields (a toast, an info or an error), shown once."""
    n, ss.field_notice = ss.get("field_notice"), None
    if not n:
        return
    kind, text = n
    if kind == "toast":
        st.toast(text, icon=":material/delete:")
    elif kind == "error":
        st.error(text, icon=":material/error:")
    else:
        st.info(text, icon=":material/info:")


HEADER = {"field": None}          # the placeholder under "Start over", filled at the end of the page (after a save)


def header():
    """The page header: the horizontal logo, the name with its tagline, and Start over with the current field (a
    placeholder: the name is written by header_field() at the end of the page, so that a run saved in this very run
    shows as saved)."""
    # the first column holds the 190 px logo down to a 1366 px screen with the sidebar open (about 205 px at a 970 px
    # content width); below that the image shrinks with its column
    h1, h2, h3 = st.columns([1.5, 3.6, 1.6], vertical_alignment="center")
    with h1:
        if os.path.exists(brand.LOGO_H):
            st.image(brand.LOGO_H, width=190)
    with h2:
        st.title(brand.NAME, anchor=False)
        st.caption(brand.TAGLINE)
    with h3:
        if st.button("Start over", icon=":material/restart_alt:", key="start_over",
                     help="Clears the screen: input, field of interest, settings and result. Saved fields are kept."):
            if is_dirty():
                start_over_dialog()
            else:
                start_over()
                st.rerun()
        HEADER["field"] = st.empty()
    brand.rule()                                          # the thin light rule under the header


def header_field():
    """The caption under 'Start over': the current field's name, and whether it is saved."""
    name = current_field_name()
    if name and HEADER["field"] is not None:
        saved = ss.workdir and ss.get("field_saved") == ss.workdir
        HEADER["field"].caption(f"Field: {name}" + ("" if saved else " · not saved yet"))


def saved_fields_block():
    """The 'Saved fields' block at the top of the sidebar: the list (newest first), Open / Rename / Delete."""
    try:
        recs = ef.list_fields(WORKSPACE)
    except Exception as e:                                 # a broken folder must not take the sidebar down
        st.caption(f"Saved fields could not be listed: {e}")
        return
    if not recs:
        st.caption("No saved fields yet: a field is saved when its cleaning finishes.")
        return
    st.subheader("Saved fields", anchor=False)
    by = {r["workdir"]: r for r in recs}
    # the choice is gone (deleted, or nothing chosen yet): the newest, assigned, not popped. The browser holds the
    # selected option as its label, so a save, an open and a rename assign the key too (autosave_field,
    # restore_field, field_name_changed, do_rename): the current label then reaches the browser with set_value
    if ss.get("saved_field") not in by:
        ss.saved_field = next(iter(by))
    # the short label (name · date · crop · markers) fits the sidebar; the kept count is in the caption below
    wd = st.selectbox("Saved fields", list(by), key="saved_field",
                      format_func=lambda w: ef.field_label(by[w], short=True), label_visibility="collapsed")
    rec = by[wd]
    # a horizontal container, not columns: the buttons keep their width and wrap to a second line in a narrow sidebar
    with st.container(horizontal=True, gap="small"):
        st.button("Open", icon=":material/folder_open:", key="field_open", on_click=request_field, args=("open", wd),
                  help="Restores the screen of this field without running the cleaning again")
        with st.popover("Rename", icon=":material/edit:"):
            st.text_input("Field name", value=rec["name"], key=f"rename_{key_of(wd)}")
            st.button("Save", icon=":material/save:", key=f"rename_save_{key_of(wd)}", on_click=do_rename, args=(wd,))
        if st.button("Delete", icon=":material/delete:", key="field_delete"):
            delete_dialog(rec)
    sm = rec.get("summary") or {}
    if rec.get("error"):
        st.caption(f"Unreadable record: {rec['error']}")
    elif sm.get("n_in") is not None:
        m_ = rec.get("method") or (rec.get("settings") or {}).get("method") or "occd"
        cmp_ = rec.get("comparison") or {}
        kept = (f"{int(sm.get('n_kept') or 0):,} kept (OCCD) · {int(cmp_.get('sms3sigma_n_kept') or 0):,} kept (SMS "
                "3-sigma)" if m_ == "both" and cmp_ else f"{int(sm.get('n_kept') or 0):,} kept"
                + (" (SMS 3-sigma)" if m_ == "sms3sigma" else ""))
        st.caption(f"{int(sm['n_in']):,} readings → {kept} · "
                   f"{ef.folder_tag(rec['workdir'])}" + (" · older run (no field.json)" if rec.get("legacy") else ""))


def do_rename(wd: str):
    name = ef.clean_name(ss.get(f"rename_{key_of(wd)}"))
    if not name:
        st.toast("The field name cannot be empty", icon=":material/error:")
        return
    try:
        rec = ef.rename_field(wd, name)
    except (ValueError, OSError) as e:
        st.toast(f"Rename failed: {e}", icon=":material/error:")
        return
    if ss.workdir and os.path.normcase(os.path.abspath(ss.workdir)) == os.path.normcase(os.path.abspath(wd)):
        ss.field_record = rec
        if ss.get("field_saved") == ss.workdir:
            ss.field_name, ss.field_name_auto = name, None
    sync_saved_field(wd)
    st.toast(f"Renamed: {name}", icon=":material/edit:")


def goto_tab(label: str):
    """A group heading of the tree: opens that tab of step 3 (st.tabs is re-created with this default; the nonce makes
    the same heading work twice in a row)."""
    ss.step3_tab, ss.step3_nonce = label, ss.get("step3_nonce", 0) + 1


def tree_heading(gname: str):
    """A bold group heading of the tree that opens the matching step-3 tab."""
    st.button(f"**{gname}**", type="tertiary", on_click=goto_tab, args=(TREE_TAB[gname],),
              key=f"tree_grp_{key_of(gname)}", help=f"Opens the '{TREE_TAB[gname]}' tab of step 3")


def filter_on(fid: str) -> bool:
    """The on/off state of a filter: owned by its switch in the processing tree (sidebar), read here before the switch
    is drawn in this run (the sidebar is drawn last, so that it can show the counts of the run)."""
    return bool(ss.get(f"f_{fid}_on", yc.DEFAULT_SETTINGS["filters"][fid]["on"]))


def filter_params(fid: str) -> dict:
    """The current thresholds of a filter from the step-3 inputs (session state), the house defaults when the inputs
    are not on the page yet."""
    d0 = yc.DEFAULT_SETTINGS["filters"][fid]
    p = {k: ss.get(f"f_{fid}_{k}", v) for k, v in d0.items() if k not in ("on", "threshold")}
    if fid == "F8":
        p["threshold"] = "auto" if ss.get("f_F8_mode", "auto") == "auto" else float(ss.get("f_F8_pct", 10.0)) / 100.0
    return p


def short_rule(fid: str, p: dict) -> str:
    """The filter's name with its thresholds in a few words, for the switch labels of the processing tree
    (e.g. 'Speed 1.5–6.5 mph'); the engine's describe_filter gives the full sentence used in step 3."""
    name = yc.FILTER_INFO[fid]["name"]
    q = {**yc.DEFAULT_SETTINGS["filters"][fid], **{k: v for k, v in p.items() if v is not None}}

    def g(k, scale=1.0):
        return f"{float(q[k]) * scale:g}"
    try:
        if fid == "F1":
            return f"Moisture {g('min_pct')}–{g('max_pct')} %"
        if fid == "F2":
            return f"Speed {g('min_mph')}–{g('max_mph')} mph"
        if fid == "F3":
            return f"Speed change > {g('max_change_per_s', 100)} %/s"
        if fid == "F4":
            return f"GNSS step > {g('max_rel_error', 100)} %"
        if fid in ("F5", "F5b"):
            return f"{name} < {int(q['min_points'])} pts"
        if fid == "F6":
            return f"Heading > {g('max_deg_per_s')} °/s"
        if fid == "F7":
            return f"Pass ends {int(q['drop_start'])}+{int(q['drop_end'])} pts"
        if fid == "F8":
            return "Overlap auto" if q["threshold"] == "auto" else f"Overlap > {100 * float(q['threshold']):g} %"
        if fid == "F9":
            return f"Wet mass {float(q['min_lbac']):,.0f}–{float(q['max_lbac']):,.0f} lb/ac"
        if fid == "F10":
            return f"Mean ± {g('k_sd')} SD"
        if fid == "F11":
            return f"Local median > {g('max_rel_dev', 100)} %"
    except (KeyError, ValueError, TypeError):
        pass
    return name


# what the processing tree shows; filled while the page is built, drawn by render_tree() at the end (or before a stop)
TREE = {"input": None, "aoi": None, "result": None, "stale": False, "result3": None}
# the engine switches a filter off itself when its column is missing ("no moisture column: F1 (moisture) switched off")
ENGINE_OFF = "switched off"


def tree_row(label: str, note: str, anchor: str | None = None, key: str | None = None, value: bool = True,
             help: str | None = None):
    """One line of the tree: a switch (or a caption when key is None) whose label carries the step and, after a run,
    its note (" — removed 72"), with the link to its block in step 3 in a narrow column at the right. The note is in
    the label on purpose: the sidebar is narrow, and a long label wraps inside its switch, whereas a second element on
    the row lands on a line of its own (a horizontal container wraps; a link inside the label is not an option, a
    click on it flips the switch). st.columns keeps the link on the line at any sidebar width; the columns stack only
    under 640 px of viewport (a phone). The switches keep their value in the session while they are not drawn
    (persist_state): an uncaught error in the main area ends the run before the sidebar is reached, and without it
    every switch would silently come back at the house default on the next run."""
    text = label + (f" — {note}" if note else "")
    c1, c2 = st.columns([8, 1], vertical_alignment="center", gap=None)
    with c1:
        if key is None:
            st.caption(text)
        else:
            st.toggle(text, value=value, key=key, help=help, persist_state="session")
    if anchor:
        # the link's title is its tooltip and accessible description: the arrow alone says nothing to a screen reader
        title = re.sub(r"^:material/[a-z_]+:\s*", "", label).replace('"', "'")
        c2.caption(f'[↗](#{anchor} "{title}: open in step 3")', text_alignment="right")


def run_notes(R, stale: bool) -> dict:
    """The per-step notes of the tree from a cleaning result: 'removed 2,028' / '0 rec' / 'off' per filter, the
    flow-delay records, the harmonisation and level factors, the symmetric column. Italic when the result is stale."""
    notes = {}
    if not R:
        return notes

    def it(s):
        return f"*{s}*" if stale else s
    warns = [str(w) for w in (R.get("warnings") or [])]
    for c in R.get("cascade") or []:
        fid = c["filter"]
        why = next((w.split(":", 1)[0] for w in warns if f"{fid} (" in w and ENGINE_OFF in w), None)
        if c.get("on"):
            notes[fid] = it(f"removed {int(c.get('removed') or 0):,}" if c.get("removed") else "0 rec")
        elif why:
            # the switch was on but the engine could not run the filter (no moisture / wet-mass column): say why
            notes[fid] = it(f"not run: {why}")
        else:
            notes[fid] = it("off")
    lag = R.get("lag") or {}
    n_lag = lag.get("applied_records")
    notes["lag"] = it(f"{int(n_lag)} rec" if n_lag else "not applied")
    RM = R.get("machines") or {}
    fa = {m: f for m, f in (RM.get("factor_applied") or {}).items() if f is not None and abs(float(f) - 1) > 1e-9}
    notes["harmonise"] = it(" ".join(f"x {float(f):.2f}" for f in fa.values()) if fa else "not applied")
    RL_ = R.get("level") or {}
    lev = RL_.get("factor_final")                         # the level applied to the columns (after a confirmed factor)
    if lev is None:
        lev = RL_.get("factor_harmonised", RL_.get("factor"))
    notes["level"] = it(f"x {float(lev):.4f}" if lev is not None else "not applied")
    rec = ((R.get("sessions") or {}).get("recommendation") or {})
    rec = rec if isinstance(rec, dict) else {}
    added = "Yld_Dry_Sy" in (R.get("difm_ready_added_columns") or [])
    notes["add_sym"] = it(("added" if added else "not added") + (" · recommended" if rec.get("map_column") else ""))
    return notes


def sms_tree_rows(R3, stale: bool):
    """The SMS 3-sigma steps in the processing tree (captions: the method has no switches there; its options are in
    the SMS 3-sigma tab of step 3), with the removed counts of the last run."""
    rows = {r["filter"]: r for r in ((R3 or {}).get("cascade") or [])}
    names = [("S0", "Import check (SMS minimum yield)"), ("S1", "Clip to the field"), ("S2", "Optimize swath widths"),
             ("S3", "Speed mean ± k SD"), ("S4", "Moisture mean ± k SD"), ("S5", "Dry yield mean ± k SD")]
    for sid, lab in names:
        if sid == "S5":
            ps = [r for f, r in rows.items() if f.startswith("S5")]
            if ps and not any(r.get("on") for r in ps):
                note = "off"
            else:
                note = (", ".join(f"pass {i + 1}: {int(r['removed']):,}" for i, r in enumerate(ps)) if ps else "")
        else:
            r = rows.get(sid)
            if r is None:
                note = ""
            elif not r.get("on"):
                note = "skipped" if str(r.get("criterion", "")).endswith("(skipped)") else "off"
            else:
                note = (f"removed {int(r['removed']):,}"
                        + (f", {int(r['narrowed']):,} narrowed" if r.get("narrowed") else ""))
        tree_row(f"{sid} · {lab}", (f"*{note}*" if (stale and note) else note), anchor="sms3sigma")


def render_tree():
    """The sidebar: the processing tree (input, field of interest, cleaning switches, output) in execution order, and
    the workspace / version captions at the bottom. Drawn at the end of the page so that the counts of the run and the
    stale state (settings changed since the run) are known."""
    R, stale = TREE["result"], TREE["stale"]
    method = ss.get("clean_method") if ss.get("clean_method") in METHODS else "occd"   # the row groups to draw
    res_m = (R or {}).get("method") or "occd"                                            # what the shown result is
    R3 = TREE.get("result3") if res_m == "both" else (R if res_m == "sms3sigma" else None)
    if R and res_m == "both" and R3 is None:              # a stale 'both' run: step 4 did not load its SMS result
        R3 = methods_of(R)[0]
    notes = run_notes(R if res_m != "sms3sigma" else None, stale)
    with st.sidebar:
        saved_fields_block()
        st.divider()
        st.subheader("Processing tree", anchor=False)
        st.caption("Switch on the filters to use; counts appear after a run.")
        with st.expander("1 · Input", icon=":material/upload_file:"):
            st.caption(TREE["input"] or "nothing opened")
        with st.expander("2 · Field of interest", icon=":material/map:"):
            st.caption(TREE["aoi"] or "none")
            st.caption("[go to field of interest](#field-of-interest)")
        with st.expander("3 · Cleaning", expanded=True, icon=":material/tune:"):
            if R:
                head = f"kept {R['n_kept']:,} of {R['n_in']:,} ({100 - R['removed_pct']:.1f} %)"
                if res_m == "both":
                    n3 = (R3 or {}).get("n_kept", ((R.get("methods") or {}).get("sms3sigma") or {}).get("n_kept"))
                    head = (f"OCCD kept {R['n_kept']:,}" + (f" · SMS 3-sigma kept {int(n3):,}" if n3 is not None
                                                            else "") + f" of {R['n_in']:,}")
                elif res_m == "sms3sigma":
                    head += " (SMS 3-sigma)"
                st.caption(head + (" — previous run, settings changed" if stale else ""))
            else:
                st.caption("no run yet")
            if method != "occd":
                tree_heading(SMS_TAB)
                with st.container(gap=None):
                    sms_tree_rows(R3, stale)
                if method == "both":
                    st.caption("OCCD cascade")
            for gname, fids in (TREE_GROUPS if method != "sms3sigma" else []):
                tree_heading(gname)
                with st.container(gap=None):
                    for fid in fids:
                        d0 = yc.DEFAULT_SETTINGS["filters"][fid]
                        tree_row(f"{fid} · {short_rule(fid, filter_params(fid))}", notes.get(fid, ""),
                                 anchor=fid.lower(), key=f"f_{fid}_on", value=d0["on"])
            tree_heading("Corrections")
            with st.container(gap=None):
                # the label follows the step-3 controls through the session state, whether or not they are on the
                # page and whether or not the switch is on; the engine shifts the positions by minus the records
                # entered, so the label carries the same sign as the note after the run ("-3 rec")
                if ss.get("lag_mode", "auto") == "fixed":
                    lag_lab = f"Flow-delay correction (fixed: {-int(ss.get('lag_records') or 0)} rec)"
                else:
                    lag_lab = "Flow-delay correction (auto)"
                if method == "sms3sigma":                   # not part of the SMS sequence: no switch, a caption
                    tree_row("Flow-delay correction", "not used by SMS 3-sigma", anchor="flow-delay")
                else:
                    tree_row(lag_lab, notes.get("lag", "") if ss.get("lag_auto", True) else ("off" if R else ""),
                             anchor="flow-delay", key="lag_auto",
                             help="Auto shifts only when the flow-delay scan proves a delay (opposite-direction "
                                  "neighbours on the passes of the direction the field was harvested in, kept records "
                                  "after the cascade). By default the shift moves the output positions only: F7 and F8 "
                                  "judge every yield at its logged position.")
                t = float(ss.get("ticket") or 0) or None
                t_lab = er.ticket_label({"value": t, "unit": ss.get("ticket_unit") or "lb"}) if t else ""
                # the grower's weight is optional: without one the row says "not given", nothing more
                tree_row((":material/check_box: Level with scale ticket" + (f" ({t_lab})" if t else "")) if t else
                         ":material/check_box_outline_blank: Level with scale ticket",
                         notes.get("level", "") if t else "not given", anchor="scale-ticket",
                         help="The grower's weight for the field, when there is one: the map is leveled to it "
                              "(Yld_Level / Yld_Lvl_Sy).")
            tree_heading("Combines")
            with st.container(gap=None):
                if method == "sms3sigma":
                    tree_row("Harmonise combines", "not used by SMS 3-sigma", anchor="combines")
                else:
                    tree_row("Harmonise combines", notes.get("harmonise", "") if ss.get("harmonise", True) else
                             ("off" if R else ""), anchor="combines", key="harmonise",
                             help="Only acts when a combine id column has more than one value and the difference is "
                                  "proven.")
            tree_heading("Sessions & moisture")
            with st.container(gap=None):
                tree_row("Symmetric dry yield column (Yld_Dry_Sy)", notes.get("add_sym", "") if ss.get("add_sym", True)
                         else ("off" if R else ""), anchor="moisture-basis", key="add_sym")
        with st.expander("4 · Output", icon=":material/cloud_upload:"):
            if R and not stale:
                name = os.path.basename((R.get("files") or {}).get("difm_ready_zip") or "")
                st.caption(f"DIFM zip ready: {name} · {R['n_kept']:,} kept points")
                if method == "both" and R3:
                    n3 = os.path.basename((R3.get("files") or {}).get("difm_ready_zip") or "")
                    st.caption(f"SMS 3-sigma zip ready: {n3} · {R3['n_kept']:,} kept points")
            elif R:
                st.caption("previous run hidden: the settings changed, run the cleaning again")
            else:
                st.caption("not run yet")
        st.divider()
        st.caption(brand.footer_caption())
        st.caption(f"Workspace `{WORKSPACE}`")
        if ss.workdir:
            st.caption(f"This run `{ss.workdir}`")


def finish_page():
    """The end of every run: the header's field caption and the sidebar (both drawn last, so that they know the run)."""
    header_field()
    render_tree()


def stop_with_tree():
    """st.stop() with the end of the page drawn first."""
    finish_page()
    st.stop()


def do_open(source):
    """source: ('upload', [UploadedFile]) or ('path', str). Makes the work folder and detects the content."""
    for k in ("cands", "decoded", "result", "result_shp", "result_key", "open_error", "open_exc", "field_saved",
              "field_record", "input_source", "restored_units"):
        ss[k] = None
    ss.open_log = []
    ss.field_fresh = False
    ss.cand_idx = 0                                       # assigned, not popped: the datasets box may stay on the page
    ss.pop("field_name", None)                            # the field name is seeded again for the new input (assigned
    ss.field_name_auto = None                             # by seed_field_name before the box is drawn)
    kind, val = source
    log = ss.open_log.append
    try:
        if kind == "upload":
            name = os.path.splitext(val[0].name)[0]
            ss.workdir = er.new_workdir(WORKSPACE, name)
            up = os.path.join(ss.workdir, "uploads")
            os.makedirs(up, exist_ok=True)
            for f in val:
                with open(os.path.join(up, os.path.basename(f.name)), "wb") as fh:
                    fh.write(f.getbuffer())
            paths = [up]
            given = [f.name for f in val]
        else:
            p = val.strip().strip('"')
            if not p or not os.path.exists(p):
                raise ValueError(f"not found on this computer: {p or '(empty)'}")
            ss.workdir = er.new_workdir(WORKSPACE, os.path.splitext(os.path.basename(p.rstrip('\\/')))[0])
            paths = [p]
            given = [p]
            if any(os.path.normcase(os.path.abspath(p)) == os.path.normcase(os.path.abspath(e)) for _, e in EXAMPLES):
                kind = "example"
        ss.cands = er.open_input(paths, ss.workdir, log=log)
        ss.input_source = {"kind": kind, "paths": given, "roots": list(getattr(ss.cands, "roots", []) or [])}
    except ValueError as e:
        ss.open_error = str(e)
    except Exception as e:                      # shown with its traceback, never swallowed; the page stays usable
        ss.open_error = f"Opening failed ({type(e).__name__}): {e}"
        ss.open_exc = e


def do_load_aoi(source):
    """source: ('upload', [UploadedFile]) or ('path', str). Reads the boundary / plan file (engine.run.read_plan) and
    keeps its summary and geometry in ss.aoi; the uploaded files go to WORKSPACE/aoi_uploads/<stamp>/ (an upload can
    happen before any input is opened, so it does not depend on the work folder)."""
    import datetime as dt
    clear_aoi()
    kind, val = source
    try:
        if kind == "upload":
            d = os.path.join(WORKSPACE, "aoi_uploads", dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            os.makedirs(d, exist_ok=True)
            for f in val:
                with open(os.path.join(d, os.path.basename(f.name)), "wb") as fh:
                    fh.write(f.getbuffer())
            for f in val:
                if f.name.lower().endswith(".zip"):
                    detect.extract_zip(os.path.join(d, f.name), os.path.join(d, "unzipped"),
                                       {"members": 0, "bytes": 0, "zips": 0}, log=lambda m: None)
            path = er.find_boundary(d)
            if not path:
                raise ValueError("no polygon layer in the upload: a field of interest is a boundary or a trial design "
                                 "(.geojson, .gpkg, .kml / .kmz or a zipped shapefile)")
            name = val[0].name
        else:
            path = val.strip().strip('"')
            if not path or not os.path.exists(path):
                raise ValueError(f"not found on this computer: {path or '(empty)'}")
            name = os.path.basename(path)
        plan = er.read_plan(path)
        ss.aoi = {"path": os.path.abspath(path), "name": name, "key": key_of(f"{os.path.abspath(path)}|{mtime(path)}"),
                  "plan": plan, **{k: plan.get(k) for k in AOI_KEYS}}
    except ValueError as e:
        ss.aoi_error = str(e)
    except Exception as e:                      # shown, never swallowed
        ss.aoi_error = f"Reading the field of interest failed ({type(e).__name__}): {e}"
        ss.aoi_exc = e


def aoi_rings_wgs84(aoi) -> list:
    """[[[lon, lat], ...], ...]: the exterior rings of the plan's polygons, the union last (for the map outline)."""
    gdf = aoi["plan"]["gdf"]
    g = gdf.geometry if (gdf.crs is None or gdf.crs.equals("EPSG:4326")) else gdf.geometry.to_crs("EPSG:4326")
    rings = []
    for geom in list(g.values) + [er.plan_union_wgs84(aoi["plan"])]:
        if geom is None or geom.is_empty:
            continue
        for p in (geom.geoms if geom.geom_type == "MultiPolygon" else [geom]):
            xs, ys = p.exterior.coords.xy
            rings.append([[float(x), float(y)] for x, y in zip(xs, ys)])
    return rings


def _rgb(colors, alpha=200) -> list:
    return [[int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), alpha] for c in colors]


def _outline_layers(aoi) -> tuple:
    """(pydeck layers, lon, lat) of the field of interest outline: the plots in navy, the field in light blue."""
    if aoi is None:
        return [], np.zeros(0), np.zeros(0)
    rings = aoi_rings_wgs84(aoi)
    n_plot = max(len(rings) - 1, 0)
    paths = [{"path": r, "kind": "plot" if i < n_plot else "field"} for i, r in enumerate(rings)]
    aoi_rgb = list(brand.map_colors["aoi"])[:3]                                      # the field outline: light blue
    plot_rgb = [int(brand.NAVY[1:3], 16), int(brand.NAVY[3:5], 16), int(brand.NAVY[5:7], 16)]   # the plots: navy
    layers = [
        pdk.Layer("PathLayer", data=[p for p in paths if p["kind"] == "plot"], get_path="path",
                  get_color=plot_rgb + [140], width_min_pixels=1, pickable=False),
        pdk.Layer("PathLayer", data=[p for p in paths if p["kind"] == "field"], get_path="path",
                  get_color=aoi_rgb + [235], width_min_pixels=3, pickable=False),
    ]
    lon = np.concatenate([np.array([p[0] for p in r]) for r in rings]) if rings else np.zeros(0)
    lat = np.concatenate([np.array([p[1] for p in r]) for r in rings]) if rings else np.zeros(0)
    return layers, lon, lat


if pdk is not None:
    class _CompactDeck(pdk.Deck):
        """pydeck writes its spec with indent=2 and st.pydeck_chart sends that string to the browser as it is: 80,000
        strips make 38 MB. Compact separators keep every strip and cut the payload to about a third."""

        def to_json(self):
            from pydeck.bindings.json_tools import default_serialize
            return json.dumps(self, sort_keys=True, default=default_serialize, separators=(",", ":"))


# satellite basemap under every map: Esri World Imagery as a one-source MapLibre style, sent as a data URL (pydeck
# passes map_style to the browser as a string; no API key, the attribution shows on the map). Offline, the layers
# draw on a blank background.
SATELLITE_STYLE = {
    "version": 8,
    "sources": {"satellite": {
        "type": "raster", "tileSize": 256, "maxzoom": 19,
        "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        "attribution": "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community"}},
    "layers": [{"id": "satellite", "type": "raster", "source": "satellite"}]}
SATELLITE_STYLE_URL = "data:application/json;base64," + base64.b64encode(json.dumps(SATELLITE_STYLE).encode()).decode()


def _deck(layers, lon, lat, height, width=900):
    # the zoom that fits the whole extent in the map's box with a 10 % margin (web mercator: 512 px per 360 deg of
    # longitude at zoom 0, latitude stretched by 1 / cos(lat)); the page width is not known here, so the map is
    # assumed at least `width` px wide
    lo0, lo1, la0, la1 = float(lon.min()), float(lon.max()), float(lat.min()), float(lat.max())
    coslat = np.cos(np.radians((la0 + la1) / 2))
    z_w = np.log2(0.9 * width * 360.0 / (512.0 * max(lo1 - lo0, 1e-6)))
    z_h = np.log2(0.9 * height * 360.0 * coslat / (512.0 * max(la1 - la0, 1e-6)))
    zoom = float(np.clip(min(z_w, z_h), 9, 17))
    view = pdk.ViewState(latitude=(la0 + la1) / 2, longitude=(lo0 + lo1) / 2, zoom=zoom)
    st.pydeck_chart(_CompactDeck(layers=layers, initial_view_state=view, map_style=SATELLITE_STYLE_URL), height=height)


def points_map(pv: pd.DataFrame, aoi=None, height=380):
    """The point preview coloured by yield over the satellite image; with a field of interest its outline is drawn
    over the points. Falls back to st.map (no satellite, no outline) without pydeck."""
    if pdk is None or pv.empty:
        st.map(pv, latitude="lat", longitude="lon", color="color", size=2, height=height)
        return
    pts = pv[["lon", "lat"]].copy()
    pts["rgb"] = _rgb(pv["color"])
    out_layers, olon, olat = _outline_layers(aoi)
    layers = [pdk.Layer("ScatterplotLayer", data=pts, get_position=["lon", "lat"], get_fill_color="rgb",
                        get_radius=2, radius_min_pixels=1.5, radius_max_pixels=6, pickable=False)] + out_layers
    _deck(layers, np.concatenate([pts.lon.values, olon]), np.concatenate([pts.lat.values, olat]), height)


def swath_map(pv: pd.DataFrame, aoi=None, height=380):
    """The readings as the strips their header swept since the previous reading (engine.run.preview_swaths; an SMS
    3-sigma output as SMS's own rectangles with the optimised width and distance), coloured by yield; readings
    without a strip as points; the field of interest outlined. Points only without pydeck or without the geometry
    columns (swath_preview without a `polygon` column)."""
    if pdk is None or pv.empty or "polygon" not in pv:
        points_map(pv, aoi, height)
        return
    rgb = _rgb(pv["color"], 215)
    has = pv["polygon"].notna().to_numpy()
    polys = pd.DataFrame({"polygon": pv["polygon"][has].tolist(), "rgb": [r for r, h in zip(rgb, has) if h]})
    layers = [pdk.Layer("PolygonLayer", data=polys, get_polygon="polygon", get_fill_color="rgb", filled=True,
                        stroked=False, extruded=False, pickable=False)]
    if (~has).any():
        pts = pd.DataFrame({"lon": pv["lon"].values[~has], "lat": pv["lat"].values[~has],
                            "rgb": [r for r, h in zip(rgb, has) if not h]})
        layers.append(pdk.Layer("ScatterplotLayer", data=pts, get_position=["lon", "lat"], get_fill_color="rgb",
                                get_radius=2, radius_min_pixels=1.5, radius_max_pixels=6, pickable=False))
    out_layers, olon, olat = _outline_layers(aoi)
    _deck(layers + out_layers, np.concatenate([pv["lon"].values, olon]), np.concatenate([pv["lat"].values, olat]),
          height)


# ------------------------------------------------------------------------------------------------ references
def cite_line(step: str, fallback: str = "") -> str:
    """One line of sources for a step (engine.clean.references.cite without the notes; FILTER_INFO['source'] or
    `fallback` when the module is missing or does not know the step)."""
    if rf is not None and step in getattr(rf, "SOURCES", {}):
        try:
            return rf.cite(step, notes=False)
        except Exception:                        # a broken reference table must not break the page
            pass
    if step in yc.FILTER_INFO:
        return str(yc.FILTER_INFO[step].get("source") or fallback)
    return fallback


def ref_markdown(key: str, note: str | None = None, supports: str | None = None) -> str:
    """'- **Short** (supports: note) - Authors (year). *Title*. Venue. [doi](url)' for one work."""
    r = (rf.REFERENCES.get(key) if rf is not None else None) or {}
    short = r.get("short") or key
    head = f"- **{short}**" + (f" ({supports}: {note})" if note else "")
    if not r:
        return head
    body = f" — {r.get('authors', '')} ({r.get('year', '')}). *{r.get('title', '')}*. {r.get('venue', '')}"
    if r.get("volume"):
        body += f", {r['volume']}" + (f"({r['issue']})" if r.get("issue") else "")
    if r.get("pages"):
        body += f", {r['pages']}"
    body = body.rstrip(".") + "."
    if r.get("url"):
        body += f" [{r.get('doi') or 'DOI'}]({r['url']})"
    return head + body


def sources_footer(step: str, fallback: str = "", prefix: str = "Sources: "):
    """The one-line sources caption of a filter / section and, when the references module knows the step, a small
    popover with the full citations (clickable DOI links) and what each work supports."""
    line = cite_line(step, fallback)
    if not line:
        return
    entries = rf.SOURCES.get(step) if rf is not None else None
    if not entries:
        st.caption(prefix + line)
        return
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.caption(prefix + line)
        with st.popover("References", icon=":material/menu_book:", help="Full citations of the works behind this step"):
            name = getattr(rf, "STEP_NAMES", {}).get(step, step)
            st.markdown(f"**{name}**")
            st.markdown("\n".join(ref_markdown(e["key"], e.get("note"), e.get("supports")) for e in entries))
            house = getattr(rf, "HOUSE_RULES", {}).get(step)
            if house:
                st.caption(house)


def references_expander(steps: list):
    """The works cited by the enabled steps, in full, at the end of step 3."""
    with st.expander("References (works cited by the enabled steps)", icon=":material/menu_book:"):
        if rf is None:
            st.caption("The references module (engine/clean/references.py) is not available: the one-line sources of "
                       "each filter come from the engine's FILTER_INFO.")
            return
        keys = rf.used_keys([s for s in steps if s in rf.SOURCES])
        st.caption(f"{len(keys)} works, all from docs/literature/references_verified.csv; numbers labelled 'house rule' "
                   "or 'house method' are conventions of this app, not values given by a paper.")
        st.markdown("\n".join(ref_markdown(k) for k in keys))


# ------------------------------------------------------------------------------------------------ header
# The sidebar is the saved fields + the processing tree, drawn by render_tree() at the end of the page
# (stop_with_tree() before a stop). The saved-field requests come first: they write widget keys.
process_field_request()
header()
show_field_notice()

# ------------------------------------------------------------------------------------------------ 1 input
with st.container(border=True):
    st.subheader(":material/upload_file: 1 · Input")
    ups = st.file_uploader("Upload files", accept_multiple_files=True, key=upload_key("uploads"),
                           help="A zip, the .shp + .shx + .dbf + .prj (+ .cpg) of a point export, or raw monitor "
                                "files (a zipped .cn1 card folder, John Deere JD-Data zips, GreenStar 3 .fdd/.fdl).")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.text_input("or a file or folder on this computer", key="local_path",
                      placeholder=r"C:\...\CARD19.cn1   (big cards open faster this way: nothing is copied)")
        if st.button("Open", type="primary", icon=":material/folder_open:"):
            if ups:
                request_open(("upload", ups))
            elif (ss.get("local_path") or "").strip():
                request_open(("path", ss.local_path))
            else:
                st.toast("Upload files or type a path first", icon=":material/info:")
    if ss.open_request:
        req, ss.open_request = ss.open_request, None     # cleared first: a failure must not repeat on every rerun
        with st.spinner("Unpacking and recognising the input ..."):
            do_open(req)
    if ss.open_error:
        st.error(ss.open_error, icon=":material/error:")
        if ss.open_exc is not None:
            st.exception(ss.open_exc)
    cands = ss.cands
    cand = None
    if cands is not None:
        if not cands:
            st.error(cands.message, icon=":material/help:")
        else:
            if len(cands) > 1:
                idx = st.selectbox("Several datasets were found: which one?", range(len(cands)),
                                   format_func=lambda i: cands[i]["label"], key="cand_idx")
            else:
                idx = 0
            cand = cands[idx]
            icon = ":material/memory:" if cand["kind"] == "raw" else ":material/scatter_plot:"
            st.success(cand["label"], icon=icon)
            if cand["kind"] == "raw":
                show_warnings(cand["probe"].warnings, "Notes from the format check")
        with st.expander("Details of the unpacking"):
            st.text("\n".join(ss.open_log + [f"note: {n}" for n in cands.notes]) or "nothing to report")

    # ---- field of interest (optional): a boundary or a trial design
    with st.container(border=True, key="aoi_block"):    # the key is the CSS hook of the smaller nested heading (brand)
        if ss.aoi_request:                           # set by a callback (example / Load button) before this run
            req, ss.aoi_request = ss.aoi_request, None
            with st.spinner("Reading the field of interest ..."):
                do_load_aoi(req)
        st.subheader("Field of interest (optional)", anchor="field-of-interest")
        st.caption("A boundary or trial-design polygon file. The raw data of a grower often holds more than one field: "
                   f"with a field of interest the units are chosen by their readings inside it (+ {BUFFER_M:g} m), "
                   "the records outside it are dropped before the cleaning, the DIFM file is clipped to it and a trial "
                   "design adds Plot_Id / Tgt_Rate to the outputs.")
        aoi_ups = st.file_uploader("Upload a boundary or trial design", accept_multiple_files=True, type=AOI_TYPES,
                                   key=upload_key("aoi_uploads"),
                                   help="A zipped shapefile, .geojson, .gpkg, .kml / .kmz, or the .shp + .shx + .dbf + "
                                        ".prj files. Any coordinate system.")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input("or a file on this computer", key="aoi_path",
                          placeholder=r"C:\...\trial-design-seed-2026.geojson")
            st.button("Load field", icon=":material/crop_free:", key="aoi_load", on_click=request_aoi_from_widgets)
            if ss.aoi is not None:
                st.button("Clear field", icon=":material/close:", key="aoi_clear", on_click=clear_aoi)
        if ss.aoi_error:
            st.error(ss.aoi_error, icon=":material/error:")
            if ss.aoi_exc is not None:
                st.exception(ss.aoi_exc)
        aoi = ss.aoi
        aoi_pending = False
        if aoi is not None and aoi.get("needs_choice"):
            # several field boundaries in one file: the user picks the field; the cleaning never unions fields
            flds = aoi.get("fields") or []
            by_idx = {f["index"]: f for f in flds}
            k = st.selectbox(f"{aoi['name']} holds {len(flds)} field boundaries (not a trial plan): which one is the "
                             "field of interest?", [None] + [f["index"] for f in flds], key=f"aoi_feature_{aoi['key']}",
                             format_func=lambda i: "choose a field ..." if i is None else
                             f"{i}: {by_idx[i]['name'] or 'polygon ' + str(i)} ({by_idx[i]['area_ac']:,.1f} ac)")
            if k is None:
                aoi_pending = True
                st.warning("Choose the field of interest: the cleaning does not run on several fields at once (a "
                           "field drawn in several parts should be one MultiPolygon feature).", icon=":material/warning:")
            else:
                try:
                    plan_k = er.read_plan(aoi["path"], feature=int(k))
                    aoi = {**aoi, "plan": plan_k, "key": key_of(f"{aoi['path']}|{mtime(aoi['path'])}|{k}"),
                           **{kk: plan_k.get(kk) for kk in AOI_KEYS}}
                except ValueError as e:
                    st.error(str(e), icon=":material/error:")
                    aoi_pending = True
        if aoi is not None:
            kind = ("trial design" if aoi["n_plots"] else
                    f"{aoi.get('n_in_file') or aoi['n_polygons']} field boundaries" if aoi.get("needs_choice") else
                    f"boundary, polygon {aoi['feature']} of {aoi.get('n_in_file')}" if aoi.get("feature") else "boundary")
            st.success(f"Field of interest: {aoi['name']} ({kind}, {aoi.get('crs') or 'no CRS'})", icon=":material/map:")
            with st.container(horizontal=True):
                st.metric("Polygons", f"{aoi['n_polygons']:,}", border=True)
                st.metric("Plots", f"{aoi['n_plots']:,}", border=True)
                st.metric("Headland polygons", f"{aoi['headland_polygons']:,}", border=True)
                st.metric("Area", f"{aoi['area_ac']:,.1f} ac", border=True)
            if aoi["n_plots"]:
                rates = ", ".join(f"{r:g}" for r in (aoi.get("rates") or []))
                st.caption(f"Plot id column: **{aoi.get('id_col') or 'row index 1..n'}** · rate column: "
                           f"**{aoi.get('rate_col') or 'none found'}**" + (f" · rates found: {rates}" if rates else ""))
            show_warnings(aoi.get("warnings"), "Notes on the field file")
        if aoi is not None:
            TREE["aoi"] = f"{aoi['name']}: {aoi['n_plots']:,} plots / {aoi['area_ac']:,.1f} ac"

    # ---- example inputs (for testing): the paths of EXAMPLES / AOI_EXAMPLES that exist on this computer
    ex_in = [(lab, p) for lab, p in EXAMPLES if os.path.exists(p)]
    ex_aoi = [(lab, p) for lab, p in AOI_EXAMPLES if os.path.exists(p)]
    if ex_in or ex_aoi:
        with st.expander("Example inputs (for testing)", icon=":material/science:"):
            with st.container(horizontal=True):
                for lab, p in ex_in:
                    st.button(lab, on_click=request_open, args=(("path", p),), icon=":material/dataset:",
                              key=f"ex_{key_of(p)}")
                for lab, p in ex_aoi:
                    st.button(lab, on_click=request_aoi, args=(("path", p),), icon=":material/map:",
                              key=f"aoi_ex_{key_of(p)}")

if cand is None:
    stop_with_tree()
TREE["input"] = cand["label"]
CK = key_of(cand.get("path") or cand["probe"].root)
AK = aoi["key"] if aoi else "noaoi"

# ------------------------------------------------------------------------------------------------ 2 decode / check
shp = None
with st.container(border=True):
    if not os.path.exists(cand.get("path") or cand["probe"].root):
        # the work folder vanished under the page (deleted from another tab or in Explorer): say so, no traceback
        st.error("The data of this run is no longer on disk (its folder was removed): start over, or open the input "
                 "again.", icon=":material/error:")
        stop_with_tree()
    if cand["kind"] == "raw":
        st.subheader(":material/memory: 2 · Decode")
        fid = cand["decoder"]
        root = cand["probe"].root
        if root not in ss.units:
            with st.spinner("Listing the tasks / machines / loads ..."):
                ss.units[root] = er.list_units(cand)
        units = ss.units[root]
        if not units:
            st.error("No harvest data with grain flow was found in this dataset.", icon=":material/error:")
            stop_with_tree()
        U = pd.DataFrame([dataclasses.asdict(u) for u in units])
        U["field"] = U["field"].replace("", "(no field)")
        dflt = detect.default_options(fid)
        table_cols = ["label", "crop", "year", "machine", "n_records", "start", "end"]
        col_cfg = {"label": st.column_config.TextColumn("Unit", width="large"),
                   "n_records": st.column_config.NumberColumn("Records", format="%d")}
        if aoi is not None:
            # the field of interest chooses the units: every unit of the latest season is decoded once (positions
            # cached in the work folder) and its share of readings inside the field + 50 m measured
            sk = (root, aoi["key"])
            if sk not in ss.aoi_shares:
                with st.status("Measuring which units lie in the field of interest ...", expanded=True) as status:
                    try:
                        ss.aoi_shares[sk] = er.units_inside_aoi(cand, units, er.plan_union_wgs84(aoi["plan"]), dflt,
                                                                ss.workdir, log=status.text)
                        status.update(label="Units measured against the field of interest", state="complete",
                                      expanded=False)
                    except Exception as e:                  # shown, never swallowed
                        status.update(label="Measuring failed", state="error")
                        st.exception(e)
                        ss.aoi_shares[sk] = {}
            shares = ss.aoi_shares[sk]
            U["inside"] = U["id"].map(lambda i: (shares.get(i) if shares.get(i) is not None else np.nan))
            U["inside_pct"] = U["inside"] * 100.0
            U["pre"] = U["inside"].fillna(0.0) >= PRESELECT
            hidden = U["inside"].isna() | (U["inside"] < HIDE)
            with st.container(horizontal=True, vertical_alignment="center"):
                st.caption(f"Units with at least {100 * PRESELECT:.0f} % of their readings inside the field of interest "
                           f"+ {BUFFER_M:g} m are pre-selected; units of other fields or seasons (< {100 * HIDE:.0f} % "
                           "inside, or not of the latest season) are hidden. Click rows to change the selection.")
                show_all = st.toggle("Show all units", value=False, key=f"showall_{CK}_{AK}")
            V = (U if show_all else U[~hidden]).reset_index(drop=True)
            table_cols = table_cols + ["inside_pct"]
            col_cfg["inside_pct"] = st.column_config.NumberColumn("inside AOI (%)", format="%.1f")
            if not U["pre"].any():
                dist = er.units_aoi_distance_m(cand, units, er.plan_union_wgs84(aoi["plan"]), dflt, ss.workdir)
                near = min(dist.values()) if dist else float("nan")
                st.error(f"No unit has {100 * PRESELECT:.0f} % of its readings inside the field of interest; the "
                         f"nearest unit is {near:,.0f} m away. Check that the field file is the right field (or clear "
                         "it and choose the units by hand).", icon=":material/error:")
            ss.aoi_preselect = U.loc[U["pre"], "id"].tolist()
            default_rows = [int(i) for i in V.index[V["pre"]]]
            tkey = f"units_{CK}_{AK}"
        else:
            rec = U[U["default"]].groupby("field").n_records.sum()
            fields = sorted(U.field.unique())
            fdef = rec.idxmax() if len(rec) else fields[0]
            c1, c2 = st.columns([1, 3])
            field = c1.selectbox("Field", fields, index=fields.index(fdef), key=f"field_{CK}")
            c2.caption("One field per DIFM file. The units pre-selected are those of the most recent season; click "
                       "rows to change the selection. Load a field of interest in step 1 to choose the units by their "
                       "position instead of the monitor's field name.")
            V = U[U.field == field].reset_index(drop=True)
            default_rows = [int(i) for i in V.index[V["default"]]]
            tkey = f"units_{CK}_{key_of(field)}"
        if ss.get("restored_units") and set(ss.restored_units) & set(V["id"]):
            default_rows = [int(i) for i in V.index[V["id"].isin(ss.restored_units)]]    # a reopened saved field
        ev = st.dataframe(V[table_cols], hide_index=True, on_select="rerun", selection_mode="multi-row", key=tkey,
                          selection_default={"selection": {"rows": default_rows}}, column_config=col_cfg)
        chosen = V.iloc[list(ev.selection.rows)].id.tolist()
        mon_crops = sorted({str(c) for c in V.iloc[list(ev.selection.rows)].crop if str(c)})
        st.caption("Crop recorded by the monitor for the selected units: **" + (", ".join(mon_crops) or "none")
                   + "**. If that is not the harvested crop, choose the crop below: its test weight and standard "
                     "moisture then come from the crop table, not from the monitor's profile.")
        mixed = er.mixed_units([u for u in units if u.id in set(chosen)], aoi=aoi is not None)
        allow_mixed = False
        if mixed:
            st.warning("The selection is more than one harvest: " + "; ".join(mixed) + ". DIFM and the overlap filter "
                       "expect one field, crop and season per file.", icon=":material/warning:")
            allow_mixed = st.checkbox("Decode them into one file anyway", value=False, key=f"mixed_{CK}")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            crop = st.selectbox("Crop", [FROM_MONITOR] + list(common.CROPS), key=f"crop_{CK}")
            tw = st.number_input("Test weight (lb/bu)", min_value=1.0, max_value=100.0, value=None, step=0.5,
                                 key=f"tw_{CK}", placeholder="monitor / crop table")
            sm = st.number_input("Standard moisture (%)", min_value=0.0, max_value=40.0, value=None, step=0.5,
                                 key=f"sm_{CK}", placeholder="monitor / crop table")
            shrink = st.segmented_control("Dry yield", ["one_sided", "symmetric"], default=dflt.shrink,
                                          required=True, key=f"shrink_{fid}_{CK}",
                                          format_func={"one_sided": "One-sided", "symmetric": "Symmetric"}.get,
                                          help=f"Vendor convention for this format: {dflt.shrink.replace('_', '-')}. "
                                               "One-sided never credits grain drier than the standard moisture.")
        kw = {}
        if fid == "cnh_cn1":
            kw["calibration"] = st.segmented_control(
                "Calibration curve", ["task", "latest"], default="task", required=True, key=f"cal_{CK}",
                format_func={"task": "Each task's own (as SMS)", "latest": "Crop's latest"}.get)
        elif fid == "jd_gs3_rcd":
            from engine.formats import jd_gs3_rcd as gs3
            with st.container(horizontal=True):
                kw["flow_delay_s"] = st.number_input("Grain flow delay (s)", 0.0, 60.0, gs3.FLOW_DELAY_S, 1.0,
                                                     key=f"fd_{CK}")
                kw["moisture_delay_s"] = st.number_input("Moisture delay (s)", 0.0, 60.0, gs3.MOISTURE_DELAY_S, 1.0,
                                                         key=f"md_{CK}")
        if st.button("Decode", type="primary", icon=":material/play_arrow:",
                     disabled=not chosen or bool(mixed and not allow_mixed), key=f"dec_{CK}"):
            opts = dataclasses.replace(dflt, crop=None if crop == FROM_MONITOR else crop, test_weight_lb_bu=tw,
                                       std_moisture_pct=sm, shrink=shrink)
            ss.decoded, ss.result = None, None
            with st.status("Decoding ...", expanded=True) as status:
                try:
                    d = er.decode(cand, chosen, opts, ss.workdir, log=status.text, allow_mixed=allow_mixed,
                                  aoi=aoi is not None, **kw)
                    d.pop("df", None)
                    d["cand"], d["unit_ids"] = CK, list(chosen)         # unit_ids: kept in the saved field
                    ss.decoded = d
                    status.update(label=f"Decoded {d['n']:,} readings", state="complete", expanded=False)
                except ValueError as e:
                    status.update(label="Decoding stopped", state="error")
                    st.error(str(e), icon=":material/error:")
                except Exception as e:                  # shown, never swallowed
                    status.update(label="Decoding failed", state="error")
                    st.exception(e)
        D = ss.decoded if (ss.decoded and ss.decoded.get("cand") == CK) else None
        if D and not os.path.exists(D["shp"]):
            st.error("The decoded file of this run is no longer on disk: decode again.", icon=":material/error:")
            ss.decoded, D = None, None
        if D:
            rep, t = D["report"], D["report"].get("totals") or {}
            area = t.get("area_ac") or 0
            with st.container(horizontal=True):
                st.metric("Readings", f"{D['n']:,}", border=True)
                st.metric("Area", f"{area:,.1f} ac", border=True)
                st.metric("Wet total", f"{t.get('bu_wet', 0):,.0f} bu", border=True)
                st.metric("Dry total", f"{t.get('bu_dry', 0):,.0f} bu", border=True)
                st.metric("Mean dry yield", f"{(t.get('bu_dry', 0) / area if area else 0):,.1f} bu/ac", border=True)
            st.caption(f"Time basis: {rep.get('time_basis')} · {rep.get('n_records_read') or 0:,} records read · "
                       f"shrink {rep['options']['shrink'].replace('_', '-')}")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Per machine**")
                st.dataframe(pd.DataFrame(rep.get("machines") or []), hide_index=True)
            with c2:
                st.markdown("**Records not exported as readings (before cleaning)**")
                st.dataframe(pd.Series(rep.get("pre_step") or {}, name="records").rename_axis("reason")
                             .reset_index(), hide_index=True)
            with st.expander("Calibration and validation"):
                st.json(rep.get("calibration") or {}, expanded=2)
            show_warnings(rep.get("warnings"), "Decoder warnings")
            pv = swath_preview(D["shp"], mtime(D["shp"]), "Yld_Vol_Dr", ss.get(f"hw_{key_of(D['shp'])}"))
            swath_map(pv, aoi)
            st.caption(strip_count_text(len(pv), D["n"])
                       + (" as the strips their header swept since the previous reading" if "polygon" in pv
                          else " as points")
                       + ", coloured by dry yield (red low, green high), before cleaning"
                       + ("; the field of interest is outlined in blue." if aoi else "."))
            file_download("Decoded points, all readings (.zip)", D["zip"], "application/zip", where="decode")
            shp = D["shp"]
            TREE["input"] = f"{cand['label']} · {D['n']:,} readings decoded"
        else:
            TREE["input"] = f"{cand['label']} · not decoded yet"
    else:
        st.subheader(":material/scatter_plot: 2 · Export")
        info = shp_info(cand["path"], mtime(cand["path"]))
        det = yc.detect_columns(info["fields"])
        with st.container(horizontal=True):
            st.metric("Points", f"{info['n']:,}", border=True)
            st.metric("Columns", len(info["fields"]), border=True)
            st.metric("Yield column", det["yield"] or "not found", border=True)
        st.dataframe(pd.DataFrame([{"key": k, "column found": det[k] or "-", "unit": yc.COLUMN_UNITS[k]}
                                   for k in yc.COLUMN_KEYS]), hide_index=True, height=250)
        if det["yield"]:
            pv = swath_preview(cand["path"], mtime(cand["path"]), det["yield"], ss.get(f"hw_{key_of(cand['path'])}"))
            swath_map(pv, aoi)
            why = ("no coordinate system (.prj)" if info.get("crs") in (None, "None") else
                   "no heading, or no distance / width column and no harvester width yet")
            st.caption(strip_count_text(len(pv), info["n"])
                       + (" as the strips their header swept since the previous reading (header line to header "
                          "line, across the travel)" if "polygon" in pv else f" as points ({why})")
                       + ", coloured by yield (red low, green high)"
                       + ("; the field of interest is outlined in blue." if aoi else "."))
        shp = cand["path"]
        TREE["input"] = cand["label"] if "point" in cand["label"] else f"{cand['label']} · {info['n']:,} points"

# ------------------------------------------------------------------------------------------------ 3 cleaning
settings, settings_error, S = None, None, None
with st.container(border=True):
    with st.container(horizontal=True, vertical_alignment="center"):
        st.subheader(":material/tune: 3 · Cleaning")
        st.button("Reset to house standard", on_click=reset_settings, icon=":material/restart_alt:")
    if shp is None:
        st.info("Decode the raw data first (step 2).", icon=":material/info:")
    else:
        info = shp_info(shp, mtime(shp))
        det = yc.detect_columns(info["fields"])
        SK = key_of(shp)
        D = ss.decoded if (cand["kind"] == "raw" and ss.decoded and ss.decoded.get("cand") == CK) else None
        # ---- crop: prefilled from the decoder (its options or the crop it used), else from the export's product name
        crop_guess, std_m_guess = step3_guesses(D, shp)
        tag_default = default_tag(cand, D)
        # the house defaults of every step-3 input for this file: what 'Reset to house standard' assigns
        ss.step3_defaults = step3_defaults(shp, det, info["fields"], crop_guess, tag_default)
        crop_opts = [CROP_UNKNOWN] + list(common.CROPS)
        if f"crop_clean_{SK}" not in ss:
            ss[f"crop_clean_{SK}"] = crop_guess if crop_guess in common.CROPS else CROP_UNKNOWN
        with st.container(horizontal=True, vertical_alignment="bottom"):
            crop_sel = st.selectbox("Crop", crop_opts, key=f"crop_clean_{SK}",
                                    help="Sets the F1 moisture window and the standard moisture of the moisture basis "
                                         "(the crop table of engine/formats/common.py). Prefilled from the decoder or "
                                         "the export's product name.")
            st.caption(("Decoder crop: " + crop_guess) if (D and crop_guess) else
                       ("Product column suggests: " + crop_guess) if crop_guess else
                       "No crop found in the data: the small-cereal defaults apply (8-20 % moisture).")
        crop_key = None if crop_sel == CROP_UNKNOWN else crop_sel
        if ss.get("clean_method") not in METHODS:
            ss["clean_method"] = "occd"
        for k_, v_ in sms_widget_defaults().items():      # the SMS 3-sigma inputs start at the house defaults
            if k_ != "clean_method" and k_ not in ss:
                ss[k_] = v_
        method = st.segmented_control(
            "Cleaning method", METHODS, default="occd", required=True, key="clean_method",
            format_func=METHOD_LABEL.get,
            help="OCCD cascade: the house standard, filters F0-F11 with measured thresholds. SMS 3-sigma: the Ag Leader "
                 "SMS Advanced sequence done by hand (clip to the field, Optimize Swath Widths, then speed, moisture and "
                 "dry yield within mean ± 3 SD). Both: the two run on the same readings and step 4 compares them.") \
            or "occd"
        if method == "sms3sigma":
            st.caption("SMS 3-sigma: the options are in the **SMS 3-sigma** tab below; the OCCD filters, the flow-delay "
                       "correction and the combine harmonisation are not used.")
        elif method == "both":
            st.caption("Both methods run on the same readings: the OCCD cascade with the settings below and the SMS "
                       "3-sigma sequence with the options of the **SMS 3-sigma** tab; step 4 shows each result and what "
                       "differs between them.")
        # seed / reseed F1 from the crop default: when the crop changes, and when the inputs' state is gone (a run
        # that died before step 3 drops the state of the widgets not drawn; the f_F1_crop marker is not a widget and
        # survives, so without this check the inputs would come back at 0-0 and the settings would be refused)
        if (ss.get("f_F1_crop", "__unset__") != crop_key or "f_F1_min_pct" not in ss or "f_F1_max_pct" not in ss):
            lo, hi = F1_CROP_RANGES.get(crop_key, F1_DEFAULT_RANGE)
            ss["f_F1_min_pct"], ss["f_F1_max_pct"], ss["f_F1_crop"] = float(lo), float(hi), crop_key

        cols_override, harvester_w, tw_f9 = {}, None, None
        with st.expander("Column mapping", icon=":material/table_chart:"):
            st.caption("Prefilled from the column names. Required: dry yield, speed, heading, distance or duration, "
                       "and swath width (or a harvester width).")
            grid = st.columns(3)
            for i, k in enumerate(yc.COLUMN_KEYS):
                opts_c = [NOT_USED] + info["fields"]
                cur = det[k] if det[k] in info["fields"] else NOT_USED
                lab = COL_LABEL[k] + (" *" if k in REQUIRED else "")
                v = grid[i % 3].selectbox(lab, opts_c, index=opts_c.index(cur), key=f"col_{k}_{SK}")
                v = None if v == NOT_USED else v
                if v != det[k]:
                    cols_override[k] = v
            with st.container(horizontal=True):
                harvester_w = st.number_input("Harvester width (ft), only without a width column", 1.0, 200.0,
                                              value=None, key=f"hw_{SK}")
                tw_f9 = st.number_input("Test weight (lb/bu): F9 without a wet-mass column, and the grower's weight",
                                        1.0, 100.0, value=None, key=f"twf9_{SK}",
                                        help="Leave empty to take the file's own ratio Yld_Mass_W / Yld_Vol_We "
                                             "(else the crop table) when the grower's weight is converted to bushels.")
        eff = {k: (cols_override[k] if k in cols_override else det[k]) for k in yc.COLUMN_KEYS}
        if crop_key is None and eff.get("moisture"):
            med_m = moisture_median(shp, mtime(shp), eff["moisture"])
            lo_d, hi_d = F1_DEFAULT_RANGE
            if med_m is not None and not (lo_d <= med_m <= hi_d):
                st.warning(f"No crop is set and the median moisture of this file is {med_m:.1f} %, outside the small-cereal "
                           f"F1 window {lo_d:g}-{hi_d:g} %: F1 would remove most of the points. Choose the crop above "
                           "(canola / flax for a dry oilseed, corn for wet grain) or widen F1 in the Sensor & record tab.",
                           icon=":material/warning:")

        filters = {}
        tab_labels = [g for g, _ in UI_GROUPS] + SECTION_TABS + ([SMS_TAB] if method != "occd" else [])
        tab_default = ss.get("step3_tab") if ss.get("step3_tab") in tab_labels else None
        tabs = st.tabs(tab_labels, default=tab_default,
                       key=f"step3_tabs_{ss.get('step3_nonce', 0)}")        # a tree heading opens its tab
        for tab, (gname, fids) in zip(tabs, UI_GROUPS):
            with tab:
                if method == "sms3sigma":
                    st.caption(SMS_NOT_USED)
                for fid in fids:
                    d0 = yc.DEFAULT_SETTINGS["filters"][fid]
                    finfo = yc.FILTER_INFO[fid]
                    with st.container(border=True, key=f"filter_box_{fid}"):   # key: CSS hook of the smaller heading
                        c1, c2 = st.columns([1, 3], vertical_alignment="center")
                        on = filter_on(fid)                    # owned by the switch in the processing tree
                        with c1:
                            st.subheader(f"{fid} · {finfo['name']}", anchor=fid.lower())
                            if not on and method != "sms3sigma":
                                st.caption(TREE_OFF_NOTE)
                        p = {"on": on}
                        with c2.container(horizontal=True):
                            if fid == "F8":
                                mode = st.segmented_control("Threshold", ["auto", "manual"], default="auto",
                                                            required=True, key="f_F8_mode", disabled=not on,
                                                            format_func={"auto": "Auto (dose-response)",
                                                                         "manual": "Manual %"}.get,
                                                            help="F8 removes the records whose swept strip lies over "
                                                                 "ground already cut by more than the threshold. Auto "
                                                                 "reads it from this field's dose-response: every "
                                                                 "record of the pass interiors (in-plot with a "
                                                                 "trial design) against no-overlap records of the "
                                                                 "same combine on other passes within max(15 m, "
                                                                 "1.5 header widths) at the same distance from the "
                                                                 "harvested edge, never below 5 %. Check what "
                                                                 "stopped the scan after the run: too few records "
                                                                 "with controls, or a yield drop.")
                                pct = st.number_input("Manual threshold %", 0.0, 100.0, 10.0, 1.0, key="f_F8_pct",
                                                      disabled=not on or mode != "manual")
                                p["threshold"] = "auto" if mode == "auto" else pct / 100.0
                            for name, v0 in d0.items():
                                if name in ("on", "threshold"):
                                    continue
                                if fid == "F1":            # seeded from the crop default (session state, no value=)
                                    p[name] = st.number_input(PARAM_LABEL.get(name, name), min_value=0.0,
                                                              max_value=100.0, step=0.5, key=f"f_F1_{name}",
                                                              disabled=not on)
                                    continue
                                if name in F8_CHOICES:     # the overlap-model switches: v2.4 default, v2.3 option
                                    opts = F8_CHOICES[name]
                                    if isinstance(v0, bool):
                                        p[name] = st.checkbox(PARAM_LABEL.get(name, name), value=v0,
                                                              key=f"f_{fid}_{name}", disabled=not on)
                                    else:
                                        p[name] = st.selectbox(PARAM_LABEL.get(name, name), opts,
                                                               index=opts.index(v0), key=f"f_{fid}_{name}",
                                                               format_func=lambda o, n=name: F8_CHOICE_LABEL[n][o],
                                                               disabled=not on)
                                    continue
                                step = 1 if isinstance(v0, int) else (0.05 if v0 < 1 else 0.5 if v0 < 100 else 50.0)
                                p[name] = st.number_input(PARAM_LABEL.get(name, name), value=v0, step=step,
                                                          key=f"f_{fid}_{name}", disabled=not on)
                        try:
                            rule = yc.describe_filter(fid, {**d0, **p})
                        except (KeyError, ValueError, TypeError):
                            rule = finfo["rule"]
                        st.caption(f"Removes points with {rule}")
                        if fid == "F9":
                            st.caption(f9_in_bu(p, bool(eff.get("wet_mass_lbac")), tw_f9, tw_of_file(shp, mtime(shp)),
                                                crop_key))
                        if fid == "F1":
                            lo, hi = F1_CROP_RANGES.get(crop_key, F1_DEFAULT_RANGE)
                            st.caption(f"Default for {crop_key or 'an unknown crop (small cereals)'}: {lo:g}-{hi:g} % "
                                       "(house convention per crop).")
                        sources_footer(fid, finfo.get("source", ""))
                        filters[fid] = p

        # ---- corrections: flow delay, scale ticket, output name
        with tabs[len(UI_GROUPS)]:
            lag_auto = bool(ss.get("lag_auto", True))          # owned by the switch in the processing tree
            st.subheader("Flow-delay correction", anchor="flow-delay")
            if not lag_auto:
                st.caption(TREE_OFF_NOTE)
            with st.container(horizontal=True, vertical_alignment="bottom"):
                lag_mode = st.segmented_control("Flow delay", ["auto", "fixed"], default="auto",
                                                required=True, key="lag_mode", disabled=not lag_auto,
                                                help="Auto shifts only when the scan between opposite-direction "
                                                     "neighbours, on the passes of the direction the field was "
                                                     "harvested in, proves a delay of 2 to 7 records (r gain > "
                                                     "0.01). When it is applied: the setting below.")
                lag_rec = st.number_input("Fixed: flow delay to correct (records)", -50, 50, 0, 1, key="lag_records",
                                          disabled=not lag_auto or lag_mode != "fixed",
                                          help="Enter the best lag of the flow-delay scan as its figure shows it; "
                                               "the positions then move by minus that many records, as the auto "
                                               "rule does.")
            lag_stage = st.selectbox("When the delay is measured and applied", list(yc.LAG_STAGES),
                                     key="lag_stage", disabled=not lag_auto,
                                     format_func=lambda o: LAG_STAGE_LABEL[o],
                                     help="Default (as v2.3): measured on the kept records after the cascade and "
                                          "applied to the output positions only. Option: measured after F6 and "
                                          "applied before F7 and F8, every yield tied to the position its grain came "
                                          "from. The option failed its pre-registered test (29 Oct 2026: the "
                                          "end-of-pass deficit did not fall below 0.10 and the scan moved with its "
                                          "population), so use it only to study a field.")
            lag_axis = st.selectbox("Passes the delay scan compares", list(yc.LAG_AXES),
                                    key="lag_axis", disabled=not lag_auto,
                                    format_func=lambda o: LAG_AXIS_LABEL[o],
                                    help="Default (v2.4): the passes of the direction the field was harvested in. "
                                         "v2.3: east-west whenever the east and the west passes both hold 200 records "
                                         "or more, which scanned the headlands of a field harvested north-south "
                                         "(Trial 29: -5 records instead of +2). Choose v2.3 only to repeat a cleaning "
                                         "delivered before v2.4, with the F8 choices marked (v2.3).")
            if not lag_auto:
                lag_mode = "none"
            sources_footer("lag", "flow-delay scan: house method")
            st.subheader("Grower's weight (scale ticket) — the real level", anchor="scale-ticket")
            st.caption("The total weight the grower got for this field (scale or cart). The monitor's bu/ac are leveled "
                       "to it: L = weight / monitor total; the DIFM file keeps the monitor's columns and adds the leveled "
                       "yields Yld_Level (and Yld_Lvl_Sy on the symmetric dry basis), which become the column to map. "
                       "With several combines the weight also closes the test of a paired factor above the maximum.")
            with st.container(horizontal=True, vertical_alignment="bottom"):
                # whole numbers for lb / kg / bu (a 2-decimal "1500000.00" reads wrong); tonnes keep 3 decimals
                t_fmt = "%.3f" if ss.get("ticket_unit") == "t" else "%.0f"
                ticket = st.number_input("Grower's weight", 0.0, 1e12, value=None, step=100.0, key="ticket",
                                         format=t_fmt, placeholder="optional, e.g. 1500000",
                                         help="As the ticket gives it; choose its unit at the right.")
                t_unit = st.segmented_control("Unit", TICKET_UNITS, default="lb", required=True, key="ticket_unit",
                                              format_func=lambda u: TICKET_UNIT_LABEL.get(u, u),
                                              help="lb, kg and t are converted to bushels with the test weight "
                                                   "(given above in the column mapping, else the file's own, else the "
                                                   "crop table); t = metric tonne (1,000 kg).")
                basis = st.segmented_control("Basis", ["wet", "dry"], default="dry", required=True, key="ticket_basis",
                                             help="Wet: the scale weighed the grain as delivered (compared with the "
                                                  "wet integral of the monitor). Dry: the weight is already at the "
                                                  "standard moisture (compared with the dry integral).")
                t_moist = st.number_input("Ticket moisture (%)", 0.0, 60.0, value=None, step=0.1, key="ticket_moisture",
                                          placeholder="optional", disabled=basis != "wet",
                                          help="When the ticket states the grain moisture: the weight is also brought "
                                               "to the standard moisture (symmetric) and compared with the dry "
                                               "integral; both are reported.")
                tag = st.text_input("Output name", value=tag_default, key=f"tag_{SK}")
            ticket_dict = None
            if ticket:
                ticket_dict = {"value": float(ticket), "unit": t_unit or "lb", "basis": basis or "wet",
                               "moisture_pct": (float(t_moist) if (t_moist is not None and basis == "wet") else None),
                               "note": None}
                try:
                    conv = er.ticket_conversion(ticket_dict, test_weight=tw_f9, file_tw=tw_of_file(shp, mtime(shp)),
                                                crop=crop_key)
                except ValueError as e:
                    conv = {"error": str(e), "text": str(e)}
                if conv.get("error"):
                    st.warning(f"Grower's weight {er.ticket_label(ticket_dict)}: {conv['error']}", icon=":material/warning:")
                else:
                    st.caption(f"Grower's weight {er.ticket_label(ticket_dict)} {conv['text']}"
                               + (f"; {ticket_dict['moisture_pct']:g} % moisture on the ticket" if ticket_dict["moisture_pct"]
                                  is not None else "") + f"; {ticket_dict['basis']} basis.")
                if not er.engine_knows_ticket():
                    st.caption("This cleaning engine knows the ticket in bushels only: the weight is converted here and "
                               "passed as scale_ticket_bu (Yld_Level is written; no Yld_Lvl_Sy, no closure test).")
            sources_footer("level", "scale-ticket level factor: house method")
            sources_footer("order", "", prefix="Order of the steps: ")

        # ---- field of interest
        with tabs[len(UI_GROUPS) + 1]:
            if aoi is None:
                st.info("No field of interest loaded (step 1). Without one the whole export is cleaned and the "
                        "monitor's field name defines the field.", icon=":material/info:")
            else:
                st.caption(f"{aoi['name']}: {aoi['n_polygons']} polygon(s), {aoi['n_plots']} plot(s), "
                           f"{aoi['area_ac']:,.1f} ac.")
            with st.container(horizontal=True, vertical_alignment="bottom"):
                aoi_buffer = st.number_input("Cleaning buffer beyond the boundary (m)", 0.0, 1000.0, float(AOI_CUT_M),
                                             10.0, key="aoi_buffer", disabled=aoi is None,
                                             help="0 m (default): the records are cut at the boundary before the "
                                                  "cleaning, so the other fields never enter the cascade, the F10 "
                                                  "limits or the sessions. A buffer (the engine's 50 m) keeps the "
                                                  "headland context of the passes that run past the boundary (pass "
                                                  "ends F7, the overlap raster F8, the flow-delay scan) but also takes "
                                                  "in the edge passes of the neighbouring fields.")
                aoi_clip = st.toggle("Clip the DIFM file to the field (0 m)", value=True, key="aoi_clip",
                                     disabled=aoi is None,
                                     help="The flagged file keeps every processed point with an In_AOI column.")
            if aoi is not None:
                st.caption("The cleaning sees only the records inside the field of interest; the preview of step 2 "
                           "keeps every raw reading." if not aoi_buffer else
                           f"The cleaning also takes the records up to {aoi_buffer:g} m outside the field (headland "
                           "context), which can include the edges of the neighbouring fields; the preview of step 2 "
                           "keeps every raw reading.")
            sources_footer("aoi", "field of interest: house method")

        # ---- harvest sessions and the moisture basis
        with tabs[len(UI_GROUPS) + 2]:
            add_sym = bool(ss.get("add_sym", True))             # owned by the switch in the processing tree
            st.subheader("Moisture basis", anchor="moisture-basis")
            st.caption("A harvest over several days changes the grain moisture between sessions (machine x calendar "
                       "day). The cleaning reports every session, adds Harv_Day / Session to the outputs and a "
                       "symmetric dry yield Yld_Dry_Sy = wet yield x (100 - M) / (100 - Ms); it never corrects the data.")
            st.caption("Symmetric dry yield column (Yld_Dry_Sy): " + ("added to the outputs" if add_sym else
                                                                       TREE_OFF_NOTE))
            with st.container(horizontal=True, vertical_alignment="bottom"):
                std_m = st.number_input("Standard moisture Ms (%)", 0.0, 40.0, value=None, step=0.5, key="std_m",
                                        placeholder=(f"decoder: {std_m_guess:g}" if std_m_guess is not None else
                                                     "auto: decoder > inferred from the export > crop table"),
                                        help="Leave empty to take the decoder's value, else the value inferred from "
                                             "the export's dry / wet ratio, else the crop table.")
                shrink_mode = st.segmented_control("Shrink of the mapped dry yield", ["auto", "one_sided", "symmetric"],
                                                   default="auto", required=True, key="shrink_mode",
                                                   format_func={"auto": "Auto (detect)", "one_sided": "One-sided",
                                                                "symmetric": "Symmetric"}.get,
                                                   help="How the monitor / export computed the mapped dry yield. "
                                                        "One-sided (John Deere, SMS) never credits grain drier than Ms.")
            if std_m is None and std_m_guess is not None:
                st.caption(f"Decoder standard moisture: {std_m_guess:g} % (used unless you set Ms above).")
            sources_footer("sessions", "harvest sessions: house method")

        # ---- combines
        with tabs[len(UI_GROUPS) + 3]:
            if D:
                mrows = [{"machine": str(m.get("machine")), "n": int(m.get("n_readings") or 0),
                          "mean_yield": m.get("mean_bu_ac_dry")} for m in (D["report"].get("machines") or [])]
            else:
                mrows = machines_of(shp, mtime(shp), eff.get("machine"), eff.get("yield")) if eff.get("machine") else []
            machines = [r["machine"] for r in mrows]

            def machine_label(m):
                if m == AUTO:
                    return "auto (most kept points)"
                r = next((x for x in mrows if x["machine"] == m), None)
                if r is None:
                    return str(m)
                s = f"{r['machine']} ({r['n']:,} readings"
                return s + (f", mean {r['mean_yield']:.1f} bu/ac)" if r.get("mean_yield") is not None else ")")
            harmonise = bool(ss.get("harmonise", True))         # owned by the switch in the processing tree
            st.subheader("Harmonise combines", anchor="combines")
            st.caption("Only acts when a combine id column has more than one value and the difference is proven at "
                       "30 m and 50 m (CIs exclude 1, factors agree within 2 %)." if harmonise else TREE_OFF_NOTE)
            with st.container(horizontal=True, vertical_alignment="bottom"):
                ref_machine = st.selectbox("Reference combine", [AUTO] + machines, key="ref_machine",
                                           disabled=not harmonise or len(machines) < 2, format_func=machine_label)
                same_plot = st.toggle("Pair cells of the same plot only", value=True, key="same_plot",
                                      disabled=not harmonise or aoi is None or not aoi["n_plots"],
                                      help="With a trial design the paired cells compare the same treatment.")
                max_factor = st.number_input("Max factor to apply (%)", 1.0, 50.0, 10.0, 1.0, key="max_factor",
                                             disabled=not harmonise,
                                             help="A proven difference larger than this is reported but not "
                                                  "applied: ask the grower for per-machine weights, or give the "
                                                  "grower's field weight (Corrections tab): when the weight confirms "
                                                  "the factor, it is applied.")
                ticket_confirms = True
                if ENGINE_TICKET_CONFIRMS:
                    ticket_confirms = st.toggle("Grower's weight may confirm a factor above the max", value=True,
                                                key="ticket_confirms", disabled=not harmonise,
                                                help="Closure test: a proven factor above the max is applied when the "
                                                     "harmonised total closes with the grower's weight (within 1 %) "
                                                     "while the unharmonised total does not (> 3 %).")
            totals = {}
            if len(machines) >= 2:
                st.caption("Per-machine totals (wet bushels from the scale, optional): one level factor per combine "
                           "L_m = ticket_m / integral_m; the paired-cell factor is then reported as a validation.")
                base = pd.DataFrame({"machine": machines,
                                     "readings": [r["n"] for r in mrows],
                                     "mean_yield": [r.get("mean_yield") for r in mrows],
                                     "wet_bu": pd.Series([np.nan] * len(machines), dtype="float")})
                # the editor cannot be set through the session state: a reset / start over remounts it (mt_nonce)
                ed = st.data_editor(base, key=f"mt_{SK}_{ss.get('mt_nonce', 0)}", hide_index=True, num_rows="fixed",
                                    disabled=["machine", "readings", "mean_yield"],
                                    column_config={"machine": st.column_config.TextColumn("Combine"),
                                                   "readings": st.column_config.NumberColumn("Readings", format="%d"),
                                                   "mean_yield": st.column_config.NumberColumn("Mean yield (bu/ac)",
                                                                                               format="%.1f"),
                                                   "wet_bu": st.column_config.NumberColumn("Wet bushels (scale)",
                                                                                           min_value=0.0,
                                                                                           format="%.0f")})
                for _, r in ed.iterrows():
                    if pd.notna(r["wet_bu"]) and float(r["wet_bu"]) > 0:
                        totals[str(r["machine"])] = float(r["wet_bu"])
            elif machines:
                st.caption(f"One combine in the data ({machines[0]}): nothing to harmonise.")
            else:
                st.caption("No combine id column mapped: the file is treated as one combine.")
            sources_footer("machines", "machine harmonisation: house method")

        # ---- the SMS 3-sigma sequence (engine/clean/sms3sigma.py)
        sms_settings = None
        if method != "occd":
            with tabs[len(UI_GROUPS) + len(SECTION_TABS)]:
                with st.container(border=True, key="filter_box_s3_seq"):
                    st.subheader("SMS 3-sigma sequence", anchor="sms3sigma")
                    st.caption("The Ag Leader SMS Advanced steps in the order of the house procedure: S0 the SMS import "
                               "check, S1 Clip To Field Boundary, S2 Optimize Swath Widths (individual swath rectangles, "
                               "per-area values scaled), then S3 speed, S4 moisture and S5 dry yield each kept within "
                               "mean ± k SD of the points still alive (the plain point mean and SD of SMS Edit Legend, "
                               "limits rounded to 2 decimals, the lower yield limit floored at 0). Another yield pass "
                               "runs only while the previous one cut the SD by more than the drop below.")
                    with st.container(horizontal=True, vertical_alignment="bottom"):
                        s3_group = st.segmented_control(
                            "Mean and SD computed", SMS_GROUPS, default="auto", required=True, persist_state="session", key="s3_group",
                            format_func=SMS_GROUP_LABEL.get,
                            help="Auto does what was done in SMS: one pooled mean and SD for the whole field when one "
                                 "combine cut it (the filter added on the operation), one per task when several "
                                 "combines worked (the filter added on each task). A task is a dataset of the export "
                                 "(Case IH task log, GreenStar task), machine x day for John Deere logs.") or "auto"
                        s3_k = st.number_input("k (SD)", 1.0, 6.0, step=0.5, key="s3_k", persist_state="session")
                        s3_drop = st.number_input("Another yield pass when the SD fell by more than (%)", 0.0, 100.0,
                                                  step=5.0, key="s3_drop", persist_state="session")
                        s3_passes = st.number_input("Max yield passes", 1, 10, step=1, key="s3_passes", persist_state="session")
                    with st.container(horizontal=True, vertical_alignment="bottom"):
                        s3_minyield = st.number_input("S0 minimum dry yield (bu/ac)", 0.0, 1000.0, step=1.0,
                                                      persist_state="session", key="s3_minyield",
                                                      help="SMS drops the readings below 5 bu/ac when it imports a "
                                                           "monitor file (every SMS raw export starts at 5.00): this "
                                                           "makes decoded raw data start where SMS starts. 0 = off.")
                        s3_clip = st.toggle("S1 Clip to the field", persist_state="session", key="s3_clip", disabled=aoi is None,
                                            help="Clip To Field Boundary: the logged point inside the field of interest "
                                                 "(a point on the edge counts as inside). Needs a field of interest.")
                        s3_swath = st.toggle("S2 Optimize swath widths", key="s3_swath", persist_state="session")
                        s3_scale = st.toggle("Scale the yield to the new area", persist_state="session", key="s3_scale", disabled=not s3_swath,
                                             help="SMS 'Scale Per Area attribute values automatically': a narrowed or "
                                                  "shortened reading's yield is multiplied by its old / new area (mass "
                                                  "is conserved), so the yield passes can then remove the thin "
                                                  "slivers.")
                    with st.container(horizontal=True, vertical_alignment="bottom"):
                        s3_speed = st.toggle("S3 Speed", key="s3_speed", persist_state="session")
                        s3_moist = st.toggle("S4 Moisture", persist_state="session", key="s3_moist", disabled=not eff.get("moisture"))
                        s3_yield = st.toggle("S5 Dry yield", key="s3_yield", persist_state="session")
                    if aoi is None:
                        st.caption("No field of interest loaded: S1 has nothing to clip to (as in SMS without a field "
                                   "boundary).")
                    if len(machines) > 1:
                        st.caption(f"{len(machines)} combines in the data: Auto filters each task separately.")
                    elif len(machines) == 1:
                        st.caption("One combine in the data: Auto uses one pooled mean and SD for the whole field.")
                    else:
                        st.caption("No combine id column: Auto pools the field when the SMS dataset names carry one "
                                   "display serial (one combine), else it filters each task.")
                    st.caption("Shared with the OCCD settings: the crop, the column mapping, the field of interest, the "
                               "moisture basis (Yld_Dry_Sy) and the grower's weight. The DIFM-ready file is written as "
                               "SMS exports it: the narrowed points carry the optimised width, the shortened ones the "
                               "new distance and speed, both with yields scaled to the new area (original width in "
                               "Wdth_Raw, factor in Swath_Scl); the files are named <output name>_sms3s_*.")
                    st.caption("Source: Ag Leader SMS Advanced help (Optimize Swath Widths, Clip To Field Boundary, "
                               "Filter Data); the mean ± 3 SD rule as in the F10 literature; the 25 % rule and the "
                               "grouping: house procedure (the SMS guide of the OFPE team).")
                sms_settings = {"group_by": s3_group, "k_sd": float(s3_k), "sd_drop_pct": float(s3_drop),
                                "max_yield_passes": int(s3_passes),
                                "min_yield": (float(s3_minyield) if s3_minyield else None),
                                "clip": bool(s3_clip), "swath": bool(s3_swath), "scale_per_area": bool(s3_scale),
                                "speed": bool(s3_speed), "moisture": bool(s3_moist), "yield": bool(s3_yield)}

        # ---- settings. F1 min / max are sent only when the user moved them off the crop (or default) seed, so that
        # the engine seeds the window from the crop itself and reports where it came from (f1_origin)
        lo_s, hi_s = F1_CROP_RANGES.get(crop_key, F1_DEFAULT_RANGE)
        f1 = filters.get("F1") or {}
        if (f1.get("min_pct") is not None and f1.get("max_pct") is not None
                and abs(float(f1["min_pct"]) - float(lo_s)) < 1e-9 and abs(float(f1["max_pct"]) - float(hi_s)) < 1e-9):
            filters["F1"] = {"on": f1["on"]}
        S = {"filters": filters, "crop": crop_key,
             "lag_correction": int(lag_rec) if lag_mode == "fixed" else lag_mode, "lag_stage": lag_stage,
             "lag_axis": lag_axis,
             "tag": tag or None,
             "cols": cols_override or None, "harvester_width_ft": harvester_w, "test_weight_lb_bu": tw_f9,
             "moisture": {"standard_pct": std_m, "shrink": shrink_mode, "add_symmetric_column": bool(add_sym)},
             "machines": {"harmonise": bool(harmonise), "reference": ref_machine or AUTO,
                          "totals_bu": totals or None, "same_plot_only": bool(same_plot),
                          "max_factor": float(max_factor) / 100.0}}
        if ticket_dict is not None:                     # the grower's weight: the v2 dict (unit, basis, moisture)
            S["scale_ticket"] = dict(ticket_dict)
        if ENGINE_TICKET_CONFIRMS:
            S["machines"]["ticket_confirms"] = bool(ticket_confirms)
        if aoi is not None:
            S["aoi"] = {"file": aoi["path"], "buffer_m": float(aoi_buffer), "clip_output": bool(aoi_clip),
                        "feature": (int(aoi["feature"]) if aoi.get("feature") else None)}
        if method != "occd":                            # only when chosen: the OCCD settings stay exactly as before
            S["method"] = method
            S["sms3sigma"] = dict(sms_settings or {})
        ss.settings_user = S                            # what the run receives (read by the AppTest tests)
        S_engine, compat_notes = er.compat_settings(S, shp=shp)
        try:
            settings = yc.merge_settings(S_engine)
        except ValueError as e:
            settings_error = str(e)
            st.error(f"Settings: {e}", icon=":material/error:")
        if aoi_pending:
            settings_error = "field of interest not chosen"
            settings = None
            st.error("The field-of-interest file holds several fields: choose one in step 1 before running.",
                     icon=":material/error:")
        if compat_notes:
            show_warnings(compat_notes, "Cleaning engine without the v2 settings")
        enabled_steps = ([f for f, p in filters.items() if p["on"]] if method != "sms3sigma" else ["F10"]) \
            + ["order", "sessions"]
        if lag_mode != "none" and method != "sms3sigma":
            enabled_steps.append("lag")
        if harmonise and method != "sms3sigma":
            enabled_steps.append("machines")
        if ticket:
            enabled_steps.append("level")
        if aoi is not None:
            enabled_steps.append("aoi")
        references_expander(enabled_steps)

def methods_of(R: dict):
    """(SMS 3-sigma result, comparison) of a 'both' run, read from their JSON files in the run's folder."""
    try:
        from engine.clean import compare as cmp_mod
        return cmp_mod.load_methods(R)
    except Exception:                                    # a missing / broken file: the tabs say so, the page stays
        return None, None


def show_result(R: dict, where: str = "results"):
    """One cleaning result: metrics, warnings, downloads, the DIFM note and the figures. `where` keeps the widget keys
    unique when two results are on the page (both methods)."""
    sms_r = (R.get("method") == "sms3sigma")
    f8, lag, F = R["f8"], R["lag"], R["files"]
    RA, RS, RM = R.get("aoi") or {}, R.get("sessions") or {}, R.get("machines") or {}
    RL = R.get("level") or {}
    difm_col, difm_why = er.recommended_yield_column(R)
    ymean = yield_mean_of(F.get("difm_ready_shp"), mtime(F.get("difm_ready_shp") or ""), difm_col)
    # the compact summary: the few numbers that matter, the details one line below (the tabs hold the rest)
    with st.container(horizontal=True):
        st.metric("Readings in", f"{R['n_in']:,}", border=True)
        st.metric("Kept", f"{R['n_kept']:,}", border=True)
        st.metric("Removed", f"{R['removed_pct']:.1f} %", border=True)
        st.metric("Mean yield", f"{ymean:,.1f} bu/ac" if ymean is not None else "-", border=True,
                  help=f"mean of {difm_col} over the kept points of the DIFM-ready file")
        if RL:                                       # only with a grower's weight: its absence is not a gap
            st.metric("Level factor", er.level_factor_text(RL).split(" ")[0], border=True,
                      help=er.level_caption(R) or None)
        st.metric("DIFM column", difm_col, border=True, help=difm_why)
    if sms_r:
        M3 = R.get("sms3sigma") or {}
        gr, sw = M3.get("grouping") or {}, M3.get("swath") or {}
        pv = sorted(set((M3.get("yield_passes") or {}).values()))
        details = [f"SMS 3-sigma, mean and SD per {gr.get('mode', '?')} ({gr.get('n_groups', '?')} group(s))",
                   f"swath widths: {int(sw.get('n_removed') or 0):,} removed, {int(sw.get('n_narrowed') or 0):,} "
                   "narrowed" + (f", {int(sw['n_shortened']):,} shortened" if sw.get("n_shortened") else ""),
                   "yield passes: " + (f"{pv[0]}" if len(pv) == 1 else f"{pv[0]}-{pv[-1]}" if pv else "0")]
        clip = M3.get("clip") or {}
        if clip.get("pre_step_removed"):
            details.append(f"SMS clip {int(clip.get('sms_clip_equivalent') or 0):,} = {cut_text(RA.get('buffer_m'))} "
                           f"pre-step {int(clip['pre_step_removed']):,} + S1 {int(clip.get('s1_removed') or 0):,}")
        if "GreenStar" in str(sw.get("order") or ""):
            details.append("swath order: GreenStar 4 log files put back in time order")
    else:
        ref8 = {"local": "; local controls", "field": "; no-overlap band"}.get(f8.get("reference_mode"), "")
        stop8 = {"too_few": "; scan stopped by too few records with controls",
                 "tolerance": "; scan stopped by a yield drop"}.get(f8.get("stop_kind"), "")
        n_orph = int(lag.get("n_orphans") or 0)
        details = ["F8 threshold " + ("off" if f8["threshold"] is None else f"{100 * f8['threshold']:.3g} %")
                   + f" ({f8['mode']}; dose-response {100 * f8['threshold_auto']:.3g} %"
                   + (", floor" if f8.get("floor_applied") else "") + f"{ref8}{stop8})",
                   f"flow delay {lag['applied_records']} rec (scan best {lag['best_records']}"
                   + ("; before F7 / F8" if lag.get("stage") == "before_f7" else "")
                   + (f"; {n_orph:,} records from beyond their pass to F7" if n_orph else "") + ")"]
        if RA:
            details.append(f"{RA.get('n_outside_buffer', 0):,} records outside {cut_text(RA.get('buffer_m'))} dropped "
                           "before the cascade")
    st.caption(" · ".join(details))
    if RL:
        lc = RL.get("closure") or {}
        st.caption(f"Level factor {er.level_factor_text(RL)}: {er.level_caption(R)}"
                   + (f". {lc['verdict']}." if lc.get("verdict") else "."))
    show_warnings(R.get("warnings"), "Cleaning warnings")              # only when there are any
    show_warnings(R.get("advice"), "Worth checking")
    with st.container(horizontal=True):
        file_download("DIFM-ready shapefile (.zip)" + (", SMS 3-sigma" if sms_r else ""), F["difm_ready_zip"],
                      "application/zip", primary=True, icon=":material/cloud_upload:", where=where)
        file_download("Report (PDF)", F["report_pdf"], "application/pdf", icon=":material/picture_as_pdf:",
                      where=where)
        file_download("Flagged points (.zip)", F["flagged_zip"], "application/zip", where=where)
        if cand["kind"] == "raw" and ss.decoded and where in ("results", "occd"):
            file_download("Decoded points (.zip)", ss.decoded["zip"], "application/zip", where=where)
        file_download("Cleaning record (JSON)", F["json"], "application/json", icon=":material/data_object:",
                      where=where)
    st.info("**How to upload to DIFM.** " + er.difm_note(R)
            + (" The file has the columns of the original export, as an SMS export after Optimize Swath Widths: map "
               "them as you map an SMS export." if sms_r else
               " Every original column is kept, so the DIFM column mapping is the same as for the original export."),
            icon=":material/lightbulb:")
    figs = F.get("figures") or {}
    fig_box = st.expander("Figures and diagnostics", icon=":material/analytics:", expanded=True)
    with fig_box:
        st.caption("Output folder")
        st.code(F["dir"], language=None, wrap_lines=True)
        if sms_r:
            labels = ["Map", "Limits", "Steps", "Sessions", "Combines", "Field of interest", "Limits per group",
                      "Steps table"]
            figkeys = ["map", "limits", "cascade"]
        else:
            labels = ["Map", "Overlap dose-response", "Cascade", "Flow delay", "Sessions", "Combines",
                      "Field of interest", "Cascade table"]
            figkeys = ["map", "f8", "cascade", "lag"]
        t = st.tabs(labels)
        nf = len(figkeys)
        for tab, k in zip(t[:nf], figkeys):
            with tab:
                if figs.get(k) and os.path.exists(figs[k]):
                    st.image(figs[k])
                else:
                    st.caption("figure not written")
                if k == "map" and F.get("difm_ready_shp") and os.path.exists(F["difm_ready_shp"]):
                    ycol = er.recommended_yield_column(R)[0]
                    rd = shp_info(F["difm_ready_shp"], mtime(F["difm_ready_shp"]))
                    ycol = ycol if ycol in rd["fields"] else None
                    pvk = swath_preview(F["difm_ready_shp"], mtime(F["difm_ready_shp"]), ycol,
                                        (R.get("settings") or {}).get("harvester_width_ft"),
                                        bool((((R.get("settings") or {}).get("filters") or {}).get("F8") or {})
                                             .get("y_offset", True)))
                    swath_map(pvk, aoi, height=420)
                    st.caption("The " + strip_count_text(len(pvk), rd["n"]).replace(" readings", " kept readings", 1)
                               + " of the DIFM-ready file"
                               + ((" as SMS draws them (rectangles with the optimised width and distance of "
                                   "Optimize Swath Widths)" if sms_r else
                                   " as the strips their header swept since the previous kept reading")
                                  if "polygon" in pvk else " as points (no strips: no heading, or no distance / "
                                  "width and no harvester width)")
                               + f", coloured by {ycol or 'yield'} (red low, green high)"
                               + ("; the field of interest is outlined in blue." if aoi is not None else "."))
        with t[nf]:                                                  # sessions
            if not RS:
                st.caption("No session diagnostics in this result (the cleaning engine did not report sessions).")
            else:
                mo = R.get("moisture") or {}
                if mo and mo.get("standard_pct") is None:
                    st.warning("Standard moisture Ms unknown (no crop, no decoder value, too few shrunk records in the "
                               "export): no Yld_Dry_Sy column and no share below Ms. Set the crop or Ms in step 3.",
                               icon=":material/warning:")
                elif mo:
                    n_below = mo.get("n_below_standard")
                    st.caption(f"Standard moisture Ms {mo.get('standard_pct')} % (source: {mo.get('source')}), shrink "
                               f"{str(mo.get('shrink', '')).replace('_', '-')}; {(n_below or 0):,} readings "
                               f"({100 * float(mo.get('share_below_standard') or 0):.1f} %) below Ms.")
                if RS.get("table"):
                    st.dataframe(pd.DataFrame(RS["table"]), hide_index=True)
                fld = RS.get("field") or {}
                if fld:
                    def _fmt(v):
                        return f"{float(v):,.2f}" if isinstance(v, (int, float)) and np.isfinite(v) else str(v)
                    st.caption(f"Field mean over all processed readings: {_fmt(fld.get('mean_mass_per_area_all'))} "
                               f"({fld.get('mean_mass_per_area_basis', 'mass per area')}); cleaned-map mean: "
                               f"{_fmt(fld.get('cleaned_map_mean'))}; cleaned-map mean on the symmetric dry basis: "
                               f"{_fmt(fld.get('cleaned_map_mean_dry_sym'))}. {fld.get('note', '')}")
                if RS.get("offsets"):
                    st.markdown("**Discontinuity between consecutive sessions of one machine (diagnostic)**")
                    st.dataframe(pd.DataFrame(RS["offsets"]), hide_index=True)
                fig_s = figs.get("sessions") or os.path.join(F["dir"], "fig_clean_sessions.png")
                if fig_s and os.path.exists(fig_s):
                    st.image(fig_s)
                rec = RS.get("recommendation")
                if isinstance(rec, dict):
                    rec = rec.get("text") or "; ".join(str(x) for x in (rec.get("reasons") or []))
                if rec and sms_r:
                    has_sy = "Yld_Dry_Sy" in (R.get("difm_ready_added_columns") or [])
                    sym_on = bool(((R.get("settings") or {}).get("moisture") or {}).get("add_symmetric_column", True))
                    tail = ("; Yld_Dry_Sy (scaled the same way) is also in the file if you prefer the symmetric basis."
                            if has_sy else
                            "; Yld_Dry_Sy was not written (the symmetric column is switched off in the processing "
                            "tree)." if not sym_on else
                            "; Yld_Dry_Sy is not in the DIFM-ready file (it needs a standard moisture, a wet yield and "
                            "a moisture column, and a run that gives the crop, the standard moisture or the field of "
                            "interest).")
                    st.caption(f"OCCD sessions diagnostic: {rec}. This SMS 3-sigma file maps the export's dry yield, as "
                               "SMS does" + tail)
                elif rec:
                    st.info(str(rec), icon=":material/lightbulb:")
                elif RS.get("basis"):
                    st.caption(f"Session basis: {RS['basis']}. No moisture discontinuity that calls for the symmetric "
                               "basis was found.")
        with t[nf + 1]:                                              # combines
            if not RM:
                st.caption("One combine (or no combine id column): nothing to harmonise.")
            else:
                st.caption(f"Combine column {RM.get('column')}; reference {RM.get('reference') or '-'}; "
                           f"method: {RM.get('method') or RM.get('rule') or '-'}")
                means = RM.get("means")
                if isinstance(means, dict) and means:
                    st.markdown("**Per machine**")
                    st.dataframe(pd.DataFrame(means).T.rename_axis("machine").reset_index(), hide_index=True)
                elif RM.get("n_points"):
                    st.dataframe(pd.DataFrame({"machine": list(RM["n_points"]),
                                               "points": list(RM["n_points"].values()),
                                               "kept": [RM.get("n_kept", {}).get(m) for m in RM["n_points"]]}),
                                 hide_index=True)
                if RM.get("tests"):
                    st.markdown("**Paired cells against the reference (factor with CI)**")
                    st.dataframe(pd.DataFrame(RM["tests"]), hide_index=True)
                dec_ = RM.get("decision") or {}
                fa = RM.get("factor_applied") or {}
                if dec_ or fa:
                    st.dataframe(pd.DataFrame({"machine": list(dec_ or fa),
                                               "factor applied": [fa.get(m) for m in (dec_ or fa)],
                                               "decision": [dec_.get(m) for m in (dec_ or fa)]}), hide_index=True)
                tt = RM.get("ticket_test")
                if isinstance(tt, dict) and tt:
                    st.markdown("**Closure test with the grower's weight**")
                    wo, wi = tt.get("without") or {}, tt.get("with") or {}
                    tick_bu = (R.get("level") or {}).get("ticket_bu", (R.get("level") or {}).get("scale_ticket_bu"))
                    st.dataframe(pd.DataFrame([
                        {"monitor total": "without the factor", "total (bu)": wo.get("total_bu"),
                         "vs the scale (%)": wo.get("diff_pct")},
                        {"monitor total": "with the factor", "total (bu)": wi.get("total_bu"),
                         "vs the scale (%)": wi.get("diff_pct")},
                        {"monitor total": "grower's weight", "total (bu)": tick_bu, "vs the scale (%)": 0.0}]),
                        hide_index=True,
                        column_config={"total (bu)": st.column_config.NumberColumn(format="%.1f"),
                                       "vs the scale (%)": st.column_config.NumberColumn(format="%+.2f")})
                    machs = ", ".join(map(str, tt.get("machines") or [])) or "-"
                    st.caption(("Factor applied" if tt.get("applied") else "Factor not applied") + f" ({machs}): "
                               + (str(tt.get("text") or tt.get("verdict") or
                                      ("the grower's weight confirms the paired factor above the maximum" if tt.get("applied")
                                       else "the harmonised total does not close with the grower's weight"))))
                if RM.get("per_machine_totals"):
                    st.markdown("**Per-machine totals (level factors)**")
                    st.json(RM["per_machine_totals"], expanded=2)
                if RM.get("validation"):
                    st.markdown("**Validation of the paired-cell estimate against the totals**")
                    st.json(RM["validation"], expanded=2)
        with t[nf + 2]:                                              # field of interest
            if not RA and aoi is None:
                st.caption("No field of interest was given: the whole export was cleaned.")
            elif not RA:
                st.caption(f"Field of interest {aoi['name']} ({aoi['n_polygons']} polygon(s), {aoi['n_plots']} plot(s), "
                           f"{aoi['area_ac']:,.1f} ac) was passed to the cleaning, but this engine did not report "
                           "the field-of-interest counts (used as the level boundary only).")
            else:
                with st.container(horizontal=True):
                    st.metric("Polygons", f"{RA.get('n_polygons', 0):,}", border=True)
                    st.metric("Plots", f"{RA.get('n_plots', 0):,}", border=True)
                    st.metric("Area", f"{float(RA.get('area_ac') or 0):,.1f} ac", border=True)
                    st.metric("Records inside + buffer", f"{RA.get('n_in', 0):,}", border=True)
                    st.metric("Dropped before the cascade", f"{RA.get('n_outside_buffer', 0):,}", border=True)
                    st.metric("Kept points outside the field", f"{RA.get('n_output_outside_aoi', 0):,}",
                              help="kept points between the field and the buffer: in the flagged file (In_AOI = 0), "
                                   "not in the DIFM file when the output is clipped", border=True)
                st.caption(f"File {RA.get('file')} · CRS {RA.get('crs')} · buffer {RA.get('buffer_m', BUFFER_M):g} m · "
                           f"plot id column {RA.get('id_col') or 'row index'} · rate column {RA.get('rate_col') or '-'}"
                           + (" · rates " + ", ".join(f"{r:g}" for r in RA["rates"]) if RA.get("rates") else ""))
                if (R.get("f8") or {}).get("dose_population"):
                    st.caption(f"F8 dose-response population: {R['f8']['dose_population']}.")
        if sms_r:
            with t[nf + 3]:                                          # the SMS limits, as Edit Legend shows them
                steps = (R.get("sms3sigma") or {}).get("steps") or []
                st.caption("Mean and SD of the points still alive before each step (the plain point statistics of SMS "
                           "Edit Legend) and the limits typed into Filter Data. The dry yield is the yield scaled by "
                           "Optimize Swath Widths. " + str(((R.get("sms3sigma") or {}).get("clip") or {}).get("note")
                                                           or ""))
                if steps:
                    st.dataframe(pd.DataFrame(steps)[["group", "step", "attribute", "n_before", "mean", "sd", "lo",
                                                      "hi", "unit", "removed", "n_after", "sd_after", "sd_drop_pct",
                                                      "next_pass"]], hide_index=True,
                                 column_config={"mean": st.column_config.NumberColumn(format="%.3f"),
                                                "sd": st.column_config.NumberColumn(format="%.3f"),
                                                "lo": st.column_config.NumberColumn("low", format="%.2f"),
                                                "hi": st.column_config.NumberColumn("high", format="%.2f"),
                                                "sd_after": st.column_config.NumberColumn(format="%.3f"),
                                                "sd_drop_pct": st.column_config.NumberColumn("SD drop %",
                                                                                             format="%.1f")})
                grp = (R.get("sms3sigma") or {}).get("grouping") or {}
                if grp:
                    st.caption(f"Grouping: {grp.get('rule', '')} (key: {grp.get('basis', '')}).")
            with t[nf + 4]:
                st.dataframe(pd.DataFrame(R["cascade"])[["filter", "name", "on", "criterion", "removed", "remaining",
                                                         "source"]], hide_index=True)
        else:
            with t[7]:
                st.dataframe(pd.DataFrame(R["cascade"])[["filter", "name", "on", "criterion", "removed", "remaining",
                                                         "source"]], hide_index=True)


def show_comparison(C: dict | None, R: dict, R3: dict | None):
    """The 'Compare methods' tab: where OCCD and SMS 3-sigma agree, the side-by-side statistics, the steps that
    removed the points the other method kept, per combine / session / plot / rate, the figures and the downloads."""
    if not C:
        st.warning("The comparison of this run is not in its folder any more: run the cleaning again.",
                   icon=":material/warning:")
        return
    cnt = C.get("counts") or {}
    sa, sb = (C.get("stats") or {}).get("occd") or {}, (C.get("stats") or {}).get("sms3sigma") or {}
    with st.container(horizontal=True):
        st.metric("Kept by both", f"{cnt.get('both', 0):,}", border=True)
        st.metric("OCCD only", f"{cnt.get('occd_only', 0):,}", border=True,
                  help="kept by the OCCD cascade, removed by SMS 3-sigma")
        st.metric("SMS 3-sigma only", f"{cnt.get('sms_only', 0):,}", border=True,
                  help="kept by SMS 3-sigma, removed by the OCCD cascade")
        st.metric("Removed by both", f"{cnt.get('neither', 0):,}", border=True)
        st.metric("Agreement", f"{C.get('agreement_pct') or 0:.1f} %", border=True,
                  help="points kept by both / points kept by either")
        uc = C.get("upload_columns") or {}
        if sa.get("mean") is not None and sb.get("mean") is not None:
            st.metric("Mean yield SMS - OCCD", f"{sb['mean'] - sa['mean']:+.2f} bu/ac", border=True,
                      help=f"OCCD {sa['mean']:.2f} ({uc.get('occd', 'the DIFM column')}), SMS 3-sigma {sb['mean']:.2f} "
                           f"({uc.get('sms3sigma', 'the DIFM column')}) bu/ac: point means of the DIFM-ready points, "
                           "on the column each method tells you to map")
    st.caption(f"Both methods cleaned the same {int(C.get('n_processed') or 0):,} processed readings. "
               + str(C.get("yield_basis") or ""))
    rows = pd.DataFrame(C.get("table") or [])
    if len(rows):
        st.dataframe(rows[["label", "occd", "sms3sigma", "difference", "difference_pct"]], hide_index=True,
                     column_config={"label": st.column_config.TextColumn("Metric"),
                                    "occd": st.column_config.NumberColumn("OCCD", format="%.2f"),
                                    "sms3sigma": st.column_config.NumberColumn("SMS 3-sigma", format="%.2f"),
                                    "difference": st.column_config.NumberColumn("Difference", format="%+.2f"),
                                    "difference_pct": st.column_config.NumberColumn("%", format="%+.1f")})
    oo = C.get("occd_only_removed_by_sms") or {}
    so = C.get("sms_only_removed_by_occd") or {}
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Kept by OCCD, removed by SMS 3-sigma** (by SMS step)")
        if oo:
            st.dataframe(pd.DataFrame({"SMS step": list(oo), "points": list(oo.values())}), hide_index=True)
        else:
            st.caption("none")
    with c2:
        st.markdown("**Kept by SMS 3-sigma, removed by OCCD** (by OCCD filter; clip = the output clip)")
        if so:
            st.dataframe(pd.DataFrame({"OCCD filter": list(so), "points": list(so.values())}), hide_index=True)
        else:
            st.caption("none")
    figs = ((C.get("files") or {}).get("figures") or {})
    tabs_ = [("Agreement map", "map"), ("Yield distribution", "hist"), ("Steps", "steps")]
    if figs.get("plots"):
        tabs_.append(("Plot means", "plots"))
    extra = [("Cross table", None)]
    if C.get("by_machine"):
        extra.append(("By combine", "by_machine"))
    if C.get("by_session"):
        extra.append(("By session", "by_session"))
    if C.get("by_plot"):
        extra.append(("By plot", "by_plot"))
    if C.get("by_rate"):
        extra.append(("By target rate", "by_rate"))
    tt = st.tabs([a for a, _ in tabs_ + extra])
    for tab, (lab, k) in zip(tt, tabs_ + extra):
        with tab:
            if k in ("map", "hist", "steps", "plots"):
                if figs.get(k) and os.path.exists(figs[k]):
                    st.image(figs[k])
                else:
                    st.caption("figure not written")
                if k == "plots" and C.get("plot_summary"):
                    ps = C["plot_summary"]
                    rtxt = f"r = {ps['r']:.3f}" if ps.get("r") is not None else "r = n/a"
                    st.caption(f"{ps['n_plots']} plots: {rtxt}, mean difference {ps['mean_diff']:+.2f} bu/ac, "
                               f"mean |difference| {ps['mean_abs_diff']:.2f}, largest {ps['max_abs_diff']:.2f} "
                               f"(plot {ps['plot_max_abs_diff']}).")
            elif k is None:
                ct = C.get("crosstab") or {}
                if ct.get("rows"):
                    st.caption("Rows: the OCCD filter that removed the reading; columns: the SMS 3-sigma step. kept = "
                               "in the DIFM-ready file; clip = kept by the cleaning but left out of the DIFM file by "
                               "the output clip.")
                    st.dataframe(pd.DataFrame(ct["values"], index=ct["rows"], columns=ct["columns"]))
            else:
                st.dataframe(pd.DataFrame(C[k]), hide_index=True)
    F = C.get("files") or {}
    with st.container(horizontal=True):
        file_download("Comparison report (PDF)", F.get("report_pdf"), "application/pdf",
                      icon=":material/picture_as_pdf:", where="compare", primary=True)
        file_download("Comparison table (CSV)", F.get("csv"), "text/csv", where="compare")
        file_download("Points with both decisions (.zip)", F.get("points_zip"), "application/zip", where="compare")
        if F.get("plots_csv"):
            file_download("Per plot (CSV)", F.get("plots_csv"), "text/csv", where="compare")
        file_download("Comparison record (JSON)", F.get("json"), "application/json", icon=":material/data_object:",
                      where="compare")
    st.info("**Which file to upload.** Both DIFM-ready files are complete. The OCCD cascade is the house standard "
            "(measured thresholds, the export's values untouched); the SMS 3-sigma file reproduces the SMS procedure "
            "(narrowed widths and scaled yields on the overlapped points). Use the agreement map and the plot table to "
            "see where the choice matters for the trial.", icon=":material/lightbulb:")


# ------------------------------------------------------------------------------------------------ 4 run
with st.container(border=True):
    st.subheader(":material/rocket_launch: 4 · Run and download")
    seed_field_name(aoi, (S or {}).get("tag") if S else None)        # before the widget: the default name follows the input
    with st.container(horizontal=True, vertical_alignment="bottom"):
        go = st.button("Run cleaning", type="primary", icon=":material/play_arrow:",
                       disabled=shp is None or settings is None)
        st.text_input("Field name", key="field_name", on_change=field_name_changed,
                      help="The name of the saved field (sidebar). Default: the name in the field-of-interest file, "
                           "else the output name. Changing it after the run renames the saved field.")
    run_key = None
    if settings is not None:
        run_key = run_key_of(shp, settings, aoi["path"] if aoi else None)
    if go:
        user = dict(S)
        ss.result = None
        out = er.free_output_dir(ss.workdir)
        src = ss.decoded.get("source") if (cand["kind"] == "raw" and ss.decoded) else None
        t_start = time.time()
        mth_ = user.get("method") or "occd"
        with st.status({"occd": "Cleaning ...", "sms3sigma": "Cleaning (SMS 3-sigma) ...",
                        "both": "Cleaning with both methods and comparing ..."}.get(mth_, "Cleaning ..."),
                       expanded=True) as status:
            try:
                R = er.clean(shp, out, user, log=status.text, source=src)
                ss.result, ss.result_shp, ss.result_key = R, shp, run_key
                lab = f"Cleaned: {R['n_kept']:,} of {R['n_in']:,} points kept"
                if mth_ == "sms3sigma":
                    lab += " (SMS 3-sigma)"
                elif mth_ == "both":
                    m3 = (R.get("methods") or {}).get("sms3sigma") or {}
                    lab = (f"Cleaned: OCCD {R['n_kept']:,}, SMS 3-sigma {int(m3.get('n_kept') or 0):,} of "
                           f"{R['n_in']:,} points kept")
                status.update(label=lab, state="complete", expanded=False)
            except ValueError as e:
                status.update(label="Cleaning stopped", state="error")
                st.error(str(e), icon=":material/error:")
            except Exception as e:                      # shown, never swallowed
                status.update(label="Cleaning failed", state="error")
                st.exception(e)
        if ss.result is not None:                       # the field is saved at the end of every successful run
            try:
                autosave_field(ss.result, shp, run_key, user, aoi, cand, (ss.get("cand_idx") or 0),
                               round(time.time() - t_start, 1))
            except Exception as e:                      # a save problem is said, the result stays on the page
                st.error(f"The field could not be saved ({type(e).__name__}): {e}", icon=":material/error:")
    R = ss.result if ss.result_shp == shp else None
    TREE["result"], TREE["stale"] = R, bool(R and ss.result_key != run_key)
    ss.field_fresh = bool(R is not None and not TREE["stale"] and ss.get("field_saved") == ss.workdir)
    if R and ss.result_key != run_key:
        st.warning("The settings changed since the last run: run the cleaning again to get a DIFM file that matches "
                   "them (the previous result is hidden).", icon=":material/warning:")
        R = None
    if R:
        if (R.get("method") or "occd") == "both":
            R3, CMP = methods_of(R)
            TREE["result3"] = R3
            t_cmp, t_occd, t_sms = st.tabs(["Compare methods", "OCCD cascade", "SMS 3-sigma"])
            with t_cmp:
                show_comparison(CMP, R, R3)
            with t_occd:
                show_result(R, "occd")
            with t_sms:
                if R3:
                    show_result(R3, "sms3sigma")
                else:
                    st.warning("The SMS 3-sigma result of this run is not in its folder any more: run the cleaning "
                               "again.", icon=":material/warning:")
        else:
            show_result(R, "results")

finish_page()
