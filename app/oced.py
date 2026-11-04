# -*- coding: utf-8 -*-
"""OCED — Olds College Extract Data: raw yield data of any monitor OCCD reads -> maps of every attribute -> the SMS
3-sigma cleaning -> clean point shapefiles.

    python -m streamlit run app/oced.py --server.port 8502      (or double-click run_oced.bat)

OCED is a part of OCCD, not a new engine: the input, the decoders, the strips of the maps and the SMS 3-sigma sequence
are OCCD's own code (engine/run.py, engine/formats, engine/clean/sms3sigma.py through engine/clean/yield_clean.py with
settings method = "sms3sigma"). What OCED leaves out: the OCCD cascade (F0-F11), the combine factor
(machines.harmonise False), the grower's weight, the field of interest and the DIFM notes. Four steps on one page:

  1 Raw data: upload the monitor files (a zipped card or JD-Data folder, the files of a GreenStar card, a point export
    or its .kml / .kmz) or type a file or folder on this computer. A raw monitor dataset lists its units (tasks /
    machines / loads); the chosen units are extracted as ONE POINT SHAPEFILE PER FIELD, SEASON AND CROP (engine.run.
    decode on each group), so a card of many fields gives many files at once. A point export is used as it is.
  2 Map and attributes: one button per attribute of the file (dry and wet yield, moisture, speed, width, distance,
    heading, elevation, time, mass, machine, dataset, field ...) colours the map (the strips the header swept over the
    satellite image, or the points); the legend, the statistics and the histogram of that attribute sit beside it;
    the attribute table and the first records below.
  3 SMS 3-sigma cleaning, the sequence of Ag Leader SMS Advanced as OCCD reproduces it: S0 import check, S2 Optimize
    Swath Widths, S3 speed, S4 moisture, S5 dry yield (mean +/- k SD on the points still alive, another yield pass
    while the SD falls by more than 25 %). One file or every file; the steps, the limits and the maps of the result.
  4 Clean shapefiles: <name>_clean.zip for each file (the kept points with every attribute of the extracted file, as
    SMS exports them after Optimize Swath Widths: the narrowed readings carry their new width and scaled per-area
    values; Wdth_Raw and Swath_Scl added), all of them in one zip, the flagged points (every point with Keep and the
    step that removed it, Rem_By) and the cleaning report (PDF).

Work folder: workspace_oced/<YYYYmmdd-HHMMSS>_<name>/ (OCED_WORKSPACE moves it), with input/, decoded/ (the extracted
files), clean/<name>/ (the SMS 3-sigma outputs) and clean_shapefiles/ (what step 4 hands out). Every value on the maps
is a reading's own value: nothing is interpolated or smoothed.
"""
import base64
import dataclasses
import datetime as dt
import hashlib
import html
import json
import os
import shutil
import sys
import threading
import zipfile

import numpy as np
import pandas as pd
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)


def _drop_stale_engine() -> None:
    """As in app/app.py: an engine whose source files changed since it was imported (an update while the app runs) is
    dropped, so that the imports below read the new code."""
    eng = sys.modules.get("engine")
    if eng is None:
        return
    stamp, now = getattr(eng, "SOURCE_STAMP", None), getattr(eng, "source_stamp", None)
    try:
        stale = stamp is None or now is None or now() != stamp
    except OSError:                                      # pragma: no cover
        stale = False
    if stale:
        for name in [n for n in sys.modules if n == "engine" or n.startswith("engine.")]:
            sys.modules.pop(name, None)


@st.cache_resource(show_spinner=False)
def _engine_lock():
    return threading.RLock()


with _engine_lock():
    _drop_stale_engine()
    from engine import run as er  # noqa: E402
    from engine.clean import sms3sigma as sms  # noqa: E402
    from engine.clean import yield_clean as yc  # noqa: E402
    from engine.formats import common, detect  # noqa: E402
import brand  # noqa: E402

try:
    import pydeck as pdk
except ImportError:                                      # pragma: no cover
    pdk = None

NAME, VERSION = "OCED", "0.1.0"
TAGLINE = "Olds College Extract Data · raw yield data to clean shapefiles with the SMS 3-sigma sequence"
WORKSPACE = os.path.abspath(os.environ.get("OCED_WORKSPACE") or os.path.join(ROOT, "workspace_oced"))
MAP_N = 60000                    # strips or points drawn on a map; above it a random sample of this size
FROM_MONITOR = "from the monitor"
PALETTE_CAT = ["#FFC20E", "#00E5FF", "#FF4FA3", "#76FF03", "#FF8F00", "#B388FF", "#FFFFFF", "#00B373", "#FF5252",
               "#90A4AE", "#1DE9B6", "#F4FF81"]
MAX_CATEGORIES = 40              # a text attribute with more distinct values is listed, not mapped

# the attributes OCED knows by name: (label, unit, colour map); "cat" = categories, "time" = time of the reading
STD_INFO = {c[0]: c for c in common.STANDARD_COLUMNS}
ATTR_INFO = {
    "Yld_Vol_Dr": ("Dry yield", "bu/ac", "RdYlGn"), "Yld_Vol_We": ("Wet yield", "bu/ac", "RdYlGn"),
    "Yld_Mass_D": ("Dry mass", "lb/ac", "RdYlGn"), "Yld_Mass_W": ("Wet mass", "lb/ac", "RdYlGn"),
    "Moisture__": ("Moisture", "%", "YlGnBu"), "Speed_mph_": ("Speed", "mph", "plasma"),
    "Swth_Wdth_": ("Swath width", "ft", "viridis"), "Distance_f": ("Distance", "ft", "viridis"),
    "Track_deg_": ("Heading", "deg", "twilight"), "Elevation_": ("Elevation", "ft", "terrain"),
    "Duration_s": ("Duration", "s", "viridis"), "Time": ("Time", "", "time"), "Obj__Id": ("Record", "", "viridis"),
    "Machine": ("Machine", "", "cat"), "Dataset": ("Dataset", "", "cat"), "Field": ("Field", "", "cat"),
    "Product": ("Product", "", "cat"), "Crop": ("Crop", "", "cat"), "Src_Fmt": ("Format", "", "cat"),
    "Wdth_Raw": ("Width as logged", "ft", "viridis"), "Swath_Scl": ("Swath scale (old / new area)", "", "viridis"),
    "Keep": ("Kept", "", "cat"), "Rem_By": ("Removed by step", "", "cat"),
}
# the same for the columns of a vendor export, by the key yield_clean.detect_columns gives them
DET_INFO = {"yield": ("Dry yield", "bu/ac", "RdYlGn"), "yield_wet": ("Wet yield", "bu/ac", "RdYlGn"),
            "moisture": ("Moisture", "%", "YlGnBu"), "speed_mph": ("Speed", "mph", "plasma"),
            "width_ft": ("Swath width", "ft", "viridis"), "distance_ft": ("Distance", "ft", "viridis"),
            "heading": ("Heading", "deg", "twilight"), "duration_s": ("Duration", "s", "viridis"),
            "wet_mass_lbac": ("Wet mass", "lb/ac", "RdYlGn"), "dataset": ("Dataset", "", "cat"),
            "machine": ("Machine", "", "cat"), "time": ("Time", "", "time"), "order": ("Record", "", "viridis")}
FIRST = ["Yld_Vol_Dr", "Yld_Vol_We", "Moisture__", "Speed_mph_", "Swth_Wdth_", "Distance_f", "Track_deg_",
         "Elevation_", "Time", "Duration_s", "Yld_Mass_W", "Yld_Mass_D", "Machine", "Dataset", "Field", "Product"]
DET_FIRST = ["yield", "yield_wet", "moisture", "speed_mph", "width_ft", "distance_ft", "heading", "time", "duration_s",
             "wet_mass_lbac", "machine", "dataset"]          # the same order for the columns of a vendor export
HIDDEN = {"Src_Fmt", "X_log", "Y_log"}          # never offered as a button (still in the attribute table)
STEP_COLORS = {"kept": "#00B373", "S0": "#90A4AE", "S1": "#B0BEC5", "S2": "#B388FF", "S3": "#00B4D8",
               "S4": "#1565C0", "S5": "#FF5252"}

st.set_page_config(page_title=NAME, page_icon=brand.page_icon(), layout="wide")
if os.path.exists(brand.LOGO_H):
    st.logo(brand.LOGO_H, icon_image=brand.LOGO_SHIELD if os.path.exists(brand.LOGO_SHIELD) else None, size="large")
brand.inject()
# the attribute buttons (st.pills in a keyed box): large, navy when chosen, as the method buttons of OCCD
st.html(f"""<style>
.stApp [class*="st-key-attr_box_"] {{ background: #F3F7FC; border: 1px solid #C9D8EC;
  border-left: 5px solid {brand.LIGHT_BLUE}; border-radius: 12px; padding: 0.7rem 1rem 0.8rem !important; }}
.stApp [class*="st-key-attr_box_"] [data-testid="stWidgetLabel"] p {{ font-weight: 700; font-size: 1.02rem;
  color: {brand.NAVY}; }}
.stApp [class*="st-key-attr_box_"] button[role="radio"] {{ min-height: 2.35rem; padding: 0.3rem 0.95rem;
  background: #FFFFFF; border: 1px solid #C9D8EC; }}
.stApp [class*="st-key-attr_box_"] button[role="radio"] p {{ font-weight: 600; color: #0B2A5B; }}
.stApp [class*="st-key-attr_box_"] button[role="radio"]:hover {{ background: #E8F1FB; border-color: {brand.LIGHT_BLUE}; }}
.stApp [class*="st-key-attr_box_"] button[role="radio"][aria-checked="true"] {{
  background: {brand.NAVY}; border-color: {brand.NAVY}; box-shadow: 0 2px 8px rgba(0,53,142,0.28); }}
.stApp [class*="st-key-attr_box_"] button[role="radio"][aria-checked="true"] p {{ color: #FFFFFF; }}
.stApp .st-key-run_go_2 [data-testid="stBaseButton-primary"] {{ min-height: 3.1rem; padding: 0.7rem 2rem;
  border-radius: 12px; font-size: 1.08rem; font-weight: 700; }}
.oced-legend {{ display: flex; align-items: center; gap: 0.6rem; margin: 0.35rem 0 0.2rem; font-size: 0.86rem;
  color: #1F2937; }}
.oced-bar {{ flex: 1; height: 14px; border-radius: 7px; border: 1px solid #C9D8EC; }}
</style>""")

ss = st.session_state
for k, v in {"workdir": None, "cands": None, "open_error": None, "open_exc": None, "open_request": None,
             "open_log": [], "units": {}, "datasets": {}, "cleaned": {}, "active": None}.items():
    ss.setdefault(k, v)


# ------------------------------------------------------------------------------------------------ helpers
def key_of(s: str) -> str:
    return hashlib.md5(str(s).encode("utf-8")).hexdigest()[:8]


def mtime(p: str) -> float:
    return os.path.getmtime(p) if p and os.path.exists(p) else 0.0


def start_over():
    for k in ("cands", "open_error", "open_exc", "open_request", "active"):
        ss[k] = None
    ss.open_log, ss.units, ss.datasets, ss.cleaned = [], {}, {}, {}
    ss.workdir = None
    for k in [k for k in ss if str(k).startswith(("cand_idx", "units_", "attr_", "path_in"))]:
        ss.pop(k, None)


def request_open(source):
    ss.open_request = source


def do_open(source):
    """source: ('upload', [UploadedFile]) or ('path', str). A new work folder; the content detected (engine.run)."""
    for k in ("cands", "open_error", "open_exc", "active"):
        ss[k] = None
    ss.open_log, ss.datasets, ss.cleaned = [], {}, {}
    ss.pop("cand_idx", None)
    kind, val = source
    try:
        if kind == "upload":
            ss.workdir = er.new_workdir(WORKSPACE, os.path.splitext(val[0].name)[0])
            up = os.path.join(ss.workdir, "uploads")
            os.makedirs(up, exist_ok=True)
            for f in val:
                with open(os.path.join(up, os.path.basename(f.name)), "wb") as fh:
                    fh.write(f.getbuffer())
            paths = [up]
        else:
            p = val.strip().strip('"')
            if not p or not os.path.exists(p):
                raise ValueError(f"not found on this computer: {p or '(empty)'}")
            ss.workdir = er.new_workdir(WORKSPACE, os.path.splitext(os.path.basename(p.rstrip('\\/')))[0])
            paths = [p]
        ss.cands = er.open_input(paths, ss.workdir, log=ss.open_log.append)
    except ValueError as e:
        ss.open_error = str(e)
    except Exception as e:                               # shown with its traceback, never swallowed
        ss.open_error = f"Opening failed ({type(e).__name__}): {e}"
        ss.open_exc = e


@st.cache_data(max_entries=12, show_spinner="Reading the points ...")
def read_points(path: str, mt: float) -> pd.DataFrame:
    """Every point of a point shapefile with every attribute, plus lon / lat (WGS 84)."""
    import pyogrio
    g = pyogrio.read_dataframe(path)
    if g.crs is not None and not g.crs.equals("EPSG:4326"):
        g = g.to_crs("EPSG:4326")
    df = pd.DataFrame(g.drop(columns="geometry"))
    df["lon"], df["lat"] = g.geometry.x.to_numpy(float), g.geometry.y.to_numpy(float)
    return df


@st.cache_data(max_entries=12, show_spinner="Building the strips the header swept ...")
def strips_of(path: str, mt: float) -> pd.DataFrame:
    """The readings as the strips they swept (engine.run.preview_swaths, MAP_N at most), each with its file row."""
    try:
        return er.preview_swaths(path, None, n_max=MAP_N)
    except Exception:                                    # a preview problem never takes the page down: the points
        return pd.DataFrame()


def attributes(df: pd.DataFrame) -> list:
    """[(column, label, unit, kind)] of the attributes worth a button: the known ones first (FIRST), then the other
    numeric columns, then the text columns with few distinct values. kind: 'num' (with its colour map), 'cat' or
    'time'."""
    cols = [c for c in df.columns if c not in ("lon", "lat")]
    det = yc.detect_columns(cols)
    by_det = {v: k for k, v in det.items() if v}
    out = {}
    for c in cols:
        if c in HIDDEN:
            continue
        if c in ATTR_INFO:
            lab, unit, cmap = ATTR_INFO[c]
        elif c in by_det and by_det[c] in DET_INFO:
            lab, unit, cmap = DET_INFO[by_det[c]]
        else:
            num = pd.api.types.is_numeric_dtype(df[c])
            if num:
                lab, unit, cmap = c, "", "viridis"
            else:
                n = df[c].astype(str).nunique()
                if n > MAX_CATEGORIES or n < 1:
                    continue
                lab, unit, cmap = c, "", "cat"
        if cmap not in ("cat", "time") and not pd.api.types.is_numeric_dtype(df[c]):
            if pd.to_numeric(df[c], errors="coerce").notna().mean() < 0.5:
                continue                                 # a text column that is not numbers
        if cmap == "cat" and df[c].astype(str).nunique() > MAX_CATEGORIES:
            continue
        v = df[c]
        if cmap not in ("cat", "time") and not np.isfinite(pd.to_numeric(v, errors="coerce").to_numpy(float)).any():
            continue                                     # all empty
        out[c] = (c, lab, unit, cmap)
    known = [c for c in FIRST if c in out] + [det[k] for k in DET_FIRST if det.get(k) in out]
    known = list(dict.fromkeys(known))
    order = known + [c for c in out if c not in known]
    return [out[c] for c in order]


def values_of(df: pd.DataFrame, col: str, kind: str):
    """(numeric values, categories or None, time origin or None) of one attribute: numbers as they are; a time as
    minutes since the first reading; categories as their codes."""
    if kind == "cat":
        s = df[col].astype(str).replace({"": "(empty)", "nan": "(empty)", "None": "(empty)"})
        cats = s.value_counts().index.tolist()
        return s.map({c: i for i, c in enumerate(cats)}).to_numpy(float), cats, None
    if kind == "time":
        t = pd.to_datetime(df[col], errors="coerce")
        if t.notna().any():
            t0 = t.min()
            return ((t - t0).dt.total_seconds() / 60.0).to_numpy(float), None, t0
        return pd.to_numeric(df[col], errors="coerce").to_numpy(float), None, None
    return pd.to_numeric(df[col], errors="coerce").to_numpy(float), None, None


def rgba_of(v, kind, cmap, lo, hi, cats) -> np.ndarray:
    """(n, 4) uint8 colours: categories from PALETTE_CAT; numbers through the colour map between lo and hi; no value
    grey."""
    import matplotlib
    n = len(v)
    out = np.zeros((n, 4), np.uint8)
    fin = np.isfinite(v)
    if kind == "cat":
        pal = np.array([[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)] for h in PALETTE_CAT], np.uint8)
        idx = np.where(fin, v, 0).astype(int) % len(pal)
        out[:, :3] = pal[idx]
    else:
        cm = matplotlib.colormaps["viridis" if cmap == "time" else cmap]
        t = np.clip((np.where(fin, v, lo) - lo) / (hi - lo if hi > lo else 1.0), 0, 1)
        out[:, :3] = (cm(t)[:, :3] * 255).astype(np.uint8)
    out[:, 3] = 220
    out[~fin] = [158, 158, 158, 150]
    return out


def fmt_value(x, unit="", kind="num", t0=None, cats=None) -> str:
    if x is None or not np.isfinite(x):
        return "—"
    if kind == "cat" and cats is not None:
        return str(cats[int(x)])
    if kind == "time" and t0 is not None:
        return (t0 + pd.Timedelta(minutes=float(x))).strftime("%Y-%m-%d %H:%M")
    a = abs(x)
    s = f"{x:,.0f}" if a >= 1000 else f"{x:,.1f}" if a >= 10 else f"{x:,.2f}" if a >= 0.1 else f"{x:.3g}"
    return f"{s} {unit}".strip()


# satellite basemap (as in app/app.py): Esri World Imagery as a one-source MapLibre style sent as a data URL
SATELLITE_STYLE = {
    "version": 8,
    "sources": {"satellite": {
        "type": "raster", "tileSize": 256, "maxzoom": 19,
        "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
        "attribution": "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community"}},
    "layers": [{"id": "satellite", "type": "raster", "source": "satellite"}]}
SATELLITE_STYLE_URL = "data:application/json;base64," + base64.b64encode(json.dumps(SATELLITE_STYLE).encode()).decode()

if pdk is not None:
    class _CompactDeck(pdk.Deck):
        """Compact JSON (as app/app.py): 60,000 strips in about a third of pydeck's indented payload."""

        def to_json(self):
            from pydeck.bindings.json_tools import default_serialize
            return json.dumps(self, sort_keys=True, default=default_serialize, separators=(",", ":"))


def deck(layers, lon, lat, height, tooltip=None, width=900):
    lo0, lo1 = float(np.nanmin(lon)), float(np.nanmax(lon))
    la0, la1 = float(np.nanmin(lat)), float(np.nanmax(lat))
    coslat = np.cos(np.radians((la0 + la1) / 2))
    z_w = np.log2(0.9 * width * 360.0 / (512.0 * max(lo1 - lo0, 1e-6)))
    z_h = np.log2(0.9 * height * 360.0 * coslat / (512.0 * max(la1 - la0, 1e-6)))
    view = pdk.ViewState(latitude=(la0 + la1) / 2, longitude=(lo0 + lo1) / 2,
                         zoom=float(np.clip(min(z_w, z_h), 9, 17)))
    st.pydeck_chart(_CompactDeck(layers=layers, initial_view_state=view, map_style=SATELLITE_STYLE_URL,
                                 tooltip=tooltip), height=height)


def legend(kind, cmap, lo, hi, unit, t0=None, cats=None, counts=None):
    """Under the map: the colour bar from lo to hi, or one chip per category with its points."""
    if kind == "cat":
        items = []
        for i, c in enumerate(cats[:MAX_CATEGORIES]):
            col = PALETTE_CAT[i % len(PALETTE_CAT)]
            n = int(counts.get(i, 0)) if counts is not None else None
            items.append(f'<span style="display:inline-flex;align-items:center;gap:6px;margin:2px 14px 2px 0;'
                         f'font-size:0.86rem"><span style="width:12px;height:12px;border-radius:50%;background:{col};'
                         f'border:1px solid #1F2937"></span><b>{html.escape(str(c))}</b>'
                         + (f" {n:,} points" if n is not None else "") + "</span>")
        st.html('<div style="display:flex;flex-wrap:wrap">' + "".join(items) + "</div>")
        return
    import matplotlib
    cm = matplotlib.colormaps["viridis" if cmap == "time" else cmap]
    stops = ", ".join(matplotlib.colors.to_hex(cm(x)) for x in np.linspace(0, 1, 11))
    st.html(f'<div class="oced-legend"><span>{html.escape(fmt_value(lo, unit, kind, t0))}</span>'
            f'<div class="oced-bar" style="background:linear-gradient(90deg,{stops})"></div>'
            f'<span>{html.escape(fmt_value(hi, unit, kind, t0))}</span></div>')


def stats_of(v: np.ndarray) -> dict:
    f = v[np.isfinite(v)]
    if not len(f):
        return {"n": int(len(v)), "valid": 0}
    m, sd = float(f.mean()), float(f.std(ddof=1)) if len(f) > 1 else 0.0
    return {"n": int(len(v)), "valid": int(len(f)), "min": float(f.min()), "p2": float(np.percentile(f, 2)),
            "mean": m, "median": float(np.median(f)), "p98": float(np.percentile(f, 98)), "max": float(f.max()),
            "sd": sd, "cv": (100 * sd / m if m else None)}


def attribute_table(df: pd.DataFrame) -> pd.DataFrame:
    """Every column of the file: what it is, its unit, how many points have a value, and its range or values."""
    rows = []
    det = yc.detect_columns([c for c in df.columns if c not in ("lon", "lat")])
    by_det = {v: k for k, v in det.items() if v}
    for c in df.columns:
        if c in ("lon", "lat"):
            continue
        meaning = (STD_INFO[c][3] if c in STD_INFO else
                   f"{DET_INFO[by_det[c]][0]} (recognised by the cleaning)" if c in by_det and by_det[c] in DET_INFO
                   else ATTR_INFO[c][0] if c in ATTR_INFO else "")
        unit = STD_INFO[c][2] if c in STD_INFO else (ATTR_INFO.get(c) or DET_INFO.get(by_det.get(c), ("", "")))[1]
        s = df[c]
        num = pd.to_numeric(s, errors="coerce") if not pd.api.types.is_numeric_dtype(s) else s
        if pd.api.types.is_numeric_dtype(s) or num.notna().mean() > 0.9:
            f = num[np.isfinite(num.astype(float))]
            rng = (f"{f.min():,.4g} … {f.max():,.4g}" if len(f) else "—")
            mean = f"{f.mean():,.4g}" if len(f) else "—"
            valid = int(len(f))
        else:
            vals = s.astype(str)
            vals = vals[~vals.isin(["", "nan", "None"])]
            u = vals.unique()
            rng = ", ".join(map(str, u[:4])) + (f" … ({len(u):,} values)" if len(u) > 4 else "")
            mean, valid = "", int(len(vals))
        rows.append({"attribute": c, "meaning": meaning, "unit": unit, "points with a value": valid,
                     "range / values": rng, "mean": mean})
    return pd.DataFrame(rows)


def explorer(shp: str, key: str, title: str = "", height: int = 520, default: str | None = None):
    """The map of a point file coloured by the attribute chosen on the buttons, with its legend, statistics and
    histogram beside it, and the attribute table and the first records below."""
    if not shp or not os.path.exists(shp):
        st.error("The file is no longer on disk.", icon=":material/error:")
        return
    df = read_points(shp, mtime(shp))
    attrs = attributes(df)
    if not attrs:
        st.warning("This file holds no attribute to map.", icon=":material/warning:")
        return
    names = [a[0] for a in attrs]
    info = {a[0]: a for a in attrs}
    akey = f"attr_{key}"
    if ss.get(akey) not in names:
        ss[akey] = default if default in names else names[0]
    with st.container(key=f"attr_box_{key}"):
        pick = st.pills("Attribute on the map", names, selection_mode="single", key=akey,
                        format_func=lambda c: info[c][1] + (f" ({info[c][2]})" if info[c][2] else ""))
    col = pick or names[0]
    _, label, unit, cmap = info[col]
    kind = "cat" if cmap == "cat" else "time" if cmap == "time" else "num"
    v, cats, t0 = values_of(df, col, kind)
    S = stats_of(v) if kind != "cat" else None
    lo, hi = ((S["p2"], S["p98"]) if (S and S.get("valid")) else (0.0, max(len(cats or []) - 1, 1)))
    if kind == "num" and S and S.get("valid") and hi <= lo:
        lo, hi = S["min"], S["max"]
    c_map, c_side = st.columns([2.6, 1], gap="medium")
    with c_map:
        draw = st.segmented_control("Draw the readings as", ["strips", "points"], default="strips", required=True,
                                    key=f"draw_{key}", format_func={"strips": "Strips the header swept",
                                                                    "points": "Points"}.get)
        pv = strips_of(shp, mtime(shp)) if draw == "strips" else pd.DataFrame()
        if draw == "strips" and ("polygon" not in pv or "row" not in pv):
            st.caption("The strips cannot be built for this file (no heading, width or distance): points instead.")
            pv = pd.DataFrame()
        if pv.empty:
            rows = np.flatnonzero(np.isfinite(df["lon"].to_numpy()) & np.isfinite(df["lat"].to_numpy()))
            if len(rows) > MAP_N:
                rows = np.sort(np.random.default_rng(0).choice(rows, MAP_N, replace=False))
            pv = pd.DataFrame({"lon": df["lon"].to_numpy()[rows], "lat": df["lat"].to_numpy()[rows], "row": rows})
        rows = pv["row"].to_numpy(int)
        vr = v[rows]
        rgba = rgba_of(vr, kind, cmap, lo, hi, cats)
        txt = [fmt_value(x, unit, kind, t0, cats) for x in vr]
        if pdk is None:
            st.map(pd.DataFrame({"lat": pv["lat"], "lon": pv["lon"]}), height=height)
        else:
            layers = []
            has = pv["polygon"].notna().to_numpy() if "polygon" in pv else np.zeros(len(pv), bool)
            if has.any():
                layers.append(pdk.Layer("PolygonLayer", data=pd.DataFrame(
                    {"polygon": pv["polygon"][has].tolist(), "rgb": rgba[has].tolist(),
                     "v": [t for t, h in zip(txt, has) if h]}), get_polygon="polygon", get_fill_color="rgb",
                    filled=True, stroked=False, pickable=True))
            if (~has).any():
                layers.append(pdk.Layer("ScatterplotLayer", data=pd.DataFrame(
                    {"lon": pv["lon"].to_numpy()[~has], "lat": pv["lat"].to_numpy()[~has],
                     "rgb": rgba[~has].tolist(), "v": [t for t, h in zip(txt, has) if not h]}),
                    get_position=["lon", "lat"], get_fill_color="rgb", get_radius=2, radius_min_pixels=1.5,
                    radius_max_pixels=6, pickable=True))
            deck(layers, pv["lon"].to_numpy(), pv["lat"].to_numpy(), height,
                 tooltip={"html": f"<b>{html.escape(label)}</b>: {{v}}",
                          "style": {"backgroundColor": "#00358E", "color": "white", "fontSize": "12px"}})
        counts = pd.Series(v[np.isfinite(v)].astype(int)).value_counts().to_dict() if kind == "cat" else None
        legend(kind, cmap, lo, hi, unit, t0, cats, counts)
        st.caption((f"All {len(df):,} readings" if len(pv) >= len(df) else
                    f"A random {len(pv):,} of the {len(df):,} readings")
                   + (" as the strips their header swept" if "polygon" in pv else " as points")
                   + f", coloured by {label}" + (" (2nd to 98th percentile; beyond it the end colours)"
                                                 if kind != "cat" else "")
                   + ". Point at a strip to read its value. Nothing is interpolated or smoothed.")
    with c_side:
        st.markdown(f"**{label}**" + (f" · {unit}" if unit else "") + f"  \n`{col}`")
        if kind == "cat":
            vc = pd.Series(df[col].astype(str).replace({"": "(empty)", "nan": "(empty)"})).value_counts()
            st.dataframe(pd.DataFrame({"value": vc.index, "points": vc.values,
                                       "share (%)": 100 * vc.values / max(len(df), 1)}), hide_index=True,
                         height=min(36 * (len(vc) + 1) + 3, 420),
                         column_config={"share (%)": st.column_config.NumberColumn(format="%.1f")})
        elif S and S.get("valid"):
            rows_ = [("points with a value", f"{S['valid']:,} of {S['n']:,}"),
                     ("minimum", fmt_value(S["min"], unit, kind, t0)), ("2nd percentile", fmt_value(S["p2"], unit, kind, t0)),
                     ("mean", fmt_value(S["mean"], unit, kind, t0)), ("median", fmt_value(S["median"], unit, kind, t0)),
                     ("98th percentile", fmt_value(S["p98"], unit, kind, t0)), ("maximum", fmt_value(S["max"], unit, kind, t0))]
            if kind == "num":
                rows_ += [("SD", fmt_value(S["sd"], unit)), ("CV", f"{S['cv']:.1f} %" if S.get("cv") else "—")]
            st.dataframe(pd.DataFrame(rows_, columns=["statistic", "value"]), hide_index=True,
                         height=36 * (len(rows_) + 1) + 3)
            f = v[np.isfinite(v)]
            if len(f) > 1 and kind == "num" and S["p98"] > S["p2"]:
                import altair as alt
                pad = 0.25 * (S["p98"] - S["p2"])
                h, e = np.histogram(np.clip(f, S["p2"] - pad, S["p98"] + pad), bins=30)
                hist = pd.DataFrame({"from": e[:-1], "to": e[1:], "points": h})
                ch = (alt.Chart(hist, height=210).mark_bar(color=brand.NAVY)
                      .encode(x=alt.X("from:Q", bin="binned", title=label + (f" ({unit})" if unit else ""),
                                      axis=alt.Axis(format=",.4~r", tickCount=6)),
                              x2="to:Q", y=alt.Y("points:Q", title="points"),
                              tooltip=[alt.Tooltip("from:Q", format=".3~g"), alt.Tooltip("to:Q", format=".3~g"),
                                       "points:Q"]))
                st.altair_chart(ch, use_container_width=True)
                st.caption("Values beyond the scale are counted in the end bars.")
        else:
            st.caption("No point has a value.")
    with st.expander(f"The attributes of this file ({len(df.columns) - 2} columns)", icon=":material/table_view:"):
        st.dataframe(attribute_table(df), hide_index=True,
                     column_config={"points with a value": st.column_config.NumberColumn(format="%d")})
    with st.expander("The first 1,000 records", icon=":material/list:"):
        st.dataframe(df.drop(columns=["lon", "lat"]).head(1000), hide_index=True)


def zip_shapefile(shp: str, zpath: str, stem: str | None = None) -> str:
    """The .shp / .shx / .dbf / .prj / .cpg of shp in one zip, renamed to `stem` when given."""
    base = os.path.splitext(shp)[0]
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for e in er.SHP_EXTS:
            if os.path.exists(base + e):
                z.write(base + e, (stem or os.path.basename(base)) + e)
    return zpath


def download(label, path, mime, key, primary=False, icon=":material/download:"):
    if path and os.path.exists(path):
        with open(path, "rb") as fh:
            st.download_button(label, fh.read(), file_name=os.path.basename(path), mime=mime, key=key,
                               type="primary" if primary else "secondary", icon=icon)


def extract(cand, chosen_units, opts, kw, log):
    """The chosen units as one shapefile per field, season and crop (engine.run.decode on each group)."""
    groups = {}
    for u in chosen_units:
        groups.setdefault((u.field or "", u.year, str(u.crop or "").strip().lower()), []).append(u)
    made = {}
    for (field, year, crop), us in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0, kv[0][2])):
        tag = er.candidate_tag(cand, us)
        if tag in made:                                  # the same field and season in two crops
            tag = yc.sanitise_tag(f"{tag}_{crop or 'crop'}")[:60]
        ss.cleaned.pop(tag, None)                        # extracted again: its old cleaning no longer applies
        log(f"extracting {field or '(no field)'} {year or ''} ({len(us)} unit(s)) ...")
        d = er.decode(cand, [u.id for u in us], opts, ss.workdir, log=log, tag=tag, **kw)
        d.pop("df", None)
        t = d["report"].get("totals") or {}
        made[d["tag"]] = {"tag": d["tag"], "shp": d["shp"], "zip": d["zip"], "n": d["n"], "kind": "raw",
                          "label": f"{field or '(no field)'} · {year or 'no season'} · {crop or 'crop?'}",
                          "source": d["source"], "report": d["report"], "area_ac": t.get("area_ac"),
                          "units": [u.label for u in us]}
    return made


def clean_one(tag: str, sset: dict, log=lambda m: None) -> dict:
    """The SMS 3-sigma sequence on one extracted file (yield_clean through engine.run.clean, method sms3sigma, no
    combine factor), then <tag>_clean.shp / .zip in clean_shapefiles/."""
    D = ss.datasets[tag]
    out = os.path.join(ss.workdir, "clean", tag)
    settings = {"method": "sms3sigma", "tag": tag, "machines": {"harmonise": False}, "sms3sigma": dict(sset)}
    R = er.clean(D["shp"], out, settings, log=log, source=D.get("source"))
    F = R["files"]
    cdir = os.path.join(ss.workdir, "clean_shapefiles")
    os.makedirs(cdir, exist_ok=True)
    src = os.path.splitext(F["difm_ready_shp"])[0]
    stem = os.path.join(cdir, f"{tag}_clean")
    for e in er.SHP_EXTS:
        if os.path.exists(src + e):
            shutil.copyfile(src + e, stem + e)
    clean_zip = zip_shapefile(stem + ".shp", stem + ".zip")
    return {"R": R, "shp": stem + ".shp", "zip": clean_zip, "flagged_shp": F.get("flagged_shp"),
            "flagged_zip": F.get("flagged_zip"), "report_pdf": F.get("report_pdf"), "json": F.get("json"),
            "settings": dict(sset), "at": dt.datetime.now().strftime("%H:%M:%S")}


def all_clean_zip() -> str | None:
    C = {t: c for t, c in ss.cleaned.items() if os.path.exists(c["shp"])}
    if not C:
        return None
    zp = os.path.join(ss.workdir, "clean_shapefiles", "OCED_clean_shapefiles.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for t, c in C.items():
            base = os.path.splitext(c["shp"])[0]
            for e in er.SHP_EXTS:
                if os.path.exists(base + e):
                    z.write(base + e, f"{t}/{os.path.basename(base)}{e}")
    return zp


# ------------------------------------------------------------------------------------------------ header
with st.container(key="app_header"):
    h1, h2, h3 = st.columns([1.4, 3.8, 1.5], vertical_alignment="center")
    with h1:
        logo = brand.LOGO_H_REV if os.path.exists(brand.LOGO_H_REV) else brand.LOGO_H
        if os.path.exists(logo):
            st.image(logo, width=200)
    with h2:
        brand.brand_block(NAME, VERSION, TAGLINE)
    with h3:
        if st.button("Start over", icon=":material/restart_alt:", key="start_over",
                     help="Clears the screen. The files already written stay in the work folder."):
            start_over()
            st.rerun()

with st.sidebar:
    st.markdown(f"**{NAME} {VERSION}** · Olds College Extract Data")
    st.caption("Part of OCCD: the decoders, the maps and the SMS 3-sigma sequence are OCCD's own code "
               f"(engine {er.__version__}).")
    st.caption("Raw formats: Case IH / New Holland .cn1 cards, John Deere Gen4 / G5 logs (JD-Data .jdl), John Deere "
               "GreenStar 3 cards (.fdd / .fdl). Point exports: SMS and Operations Center shapefiles, .kml / .kmz.")
    if ss.workdir:
        st.caption("Work folder")
        st.code(ss.workdir, language=None, wrap_lines=True)

# ------------------------------------------------------------------------------------------------ 1 raw data
with st.container(border=True, key="occd_step_1"):
    brand.step_header(1, "Raw data", "Upload the monitor files or a point export, or open a file or folder on this "
                                     "computer: every format OCCD reads")
    ups = st.file_uploader("Upload files", accept_multiple_files=True, key="uploads",
                           help="A zipped card or JD-Data folder, the files of a GreenStar card, a point export "
                                "(.shp + .shx + .dbf + .prj, or a zip) or its .kml / .kmz.")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.text_input("or a file or folder on this computer", key="path_in",
                      placeholder=r"C:\...\JD-Data   or   C:\...\CARD19.cn1   (nothing is copied)")
        if st.button("Open", type="primary", icon=":material/folder_open:", key="open_btn"):
            if ups:
                request_open(("upload", ups))
            elif (ss.get("path_in") or "").strip():
                request_open(("path", ss.path_in))
            else:
                st.toast("Upload files or type a path first", icon=":material/info:")
    if ss.open_request:
        req, ss.open_request = ss.open_request, None
        with st.spinner("Unpacking and recognising the input ..."):
            do_open(req)
    if ss.open_error:
        st.error(ss.open_error, icon=":material/error:")
        if ss.open_exc is not None:
            st.exception(ss.open_exc)
    cands, cand = ss.cands, None
    if cands is not None:
        if not cands:
            st.error(cands.message or "Nothing that OCED can read was found.", icon=":material/help:")
        else:
            idx = (st.selectbox("Several datasets were found: which one?", range(len(cands)),
                                format_func=lambda i: cands[i]["label"], key="cand_idx", index=None,
                                placeholder="choose a dataset ...") if len(cands) > 1 else 0)
            cand = cands[idx] if idx is not None else None
        with st.expander("Details of the unpacking"):
            st.text("\n".join(ss.open_log + [f"note: {n}" for n in getattr(cands, "notes", [])]) or "nothing")
    if cand is not None:
        icon = ":material/memory:" if cand["kind"] == "raw" else ":material/scatter_plot:"
        st.success(cand["label"], icon=icon)
        CK = key_of(cand.get("path") or cand["probe"].root)
        if cand["kind"] == "raw":
            root = cand["probe"].root
            if root not in ss.units:
                with st.spinner("Listing the tasks / machines / loads ..."):
                    ss.units[root] = er.list_units(cand)
            units = ss.units[root]
            if not units:
                st.error("No harvest data with grain flow was found in this dataset.", icon=":material/error:")
            else:
                U = pd.DataFrame([dataclasses.asdict(u) for u in units])
                U["field"] = U["field"].replace("", "(no field)")
                U = U.sort_values(["field", "year", "start"], na_position="last").reset_index(drop=True)
                n_fields = U["field"].nunique()
                st.markdown(f"**{len(U):,} unit(s) in {n_fields:,} field(s).** Choose the units to extract: each "
                            "field, season and crop becomes its own shapefile. The most recent season is pre-selected.")
                ev = st.dataframe(U[["field", "year", "crop", "machine", "n_records", "start", "end", "label"]],
                                  hide_index=True, on_select="rerun", selection_mode="multi-row", key=f"units_{CK}",
                                  selection_default={"selection": {"rows": [int(i) for i in U.index[U["default"]]]}},
                                  column_config={"n_records": st.column_config.NumberColumn("records", format="%d"),
                                                 "label": st.column_config.TextColumn("unit", width="large")})
                chosen_ids = U.iloc[list(ev.selection.rows)]["id"].tolist()
                chosen = [u for u in units if u.id in set(chosen_ids)]
                groups = sorted({(u.field or "(no field)", u.year) for u in chosen}, key=lambda g: (g[0], g[1] or 0))
                fid = cand["decoder"]
                dflt = detect.default_options(fid)
                with st.expander("Decoding options (crop, test weight, standard moisture, dry yield)",
                                 icon=":material/tune:"):
                    with st.container(horizontal=True, vertical_alignment="bottom"):
                        crop = st.selectbox("Crop", [FROM_MONITOR] + list(common.CROPS), key=f"crop_{CK}")
                        tw = st.number_input("Test weight (lb/bu)", min_value=1.0, max_value=100.0, value=None,
                                             step=0.5, key=f"tw_{CK}", placeholder="monitor / crop table")
                        sm = st.number_input("Standard moisture (%)", min_value=0.0, max_value=40.0, value=None,
                                             step=0.5, key=f"sm_{CK}", placeholder="monitor / crop table")
                        shrink = st.segmented_control("Dry yield", ["one_sided", "symmetric"], default=dflt.shrink,
                                                      required=True, key=f"shrink_{CK}",
                                                      format_func={"one_sided": "One-sided",
                                                                   "symmetric": "Symmetric"}.get)
                    kw = {}
                    if fid == "cnh_cn1":
                        kw["calibration"] = st.segmented_control(
                            "Calibration curve", ["task", "latest"], default="task", required=True, key=f"cal_{CK}",
                            format_func={"task": "Each task's own (as SMS)", "latest": "Crop's latest"}.get)
                    elif fid == "jd_gs3_rcd":
                        from engine.formats import jd_gs3_rcd as gs3
                        with st.container(horizontal=True):
                            kw["flow_delay_s"] = st.number_input("Grain flow delay (s)", 0.0, 60.0, gs3.FLOW_DELAY_S,
                                                                 1.0, key=f"fd_{CK}")
                            kw["moisture_delay_s"] = st.number_input("Moisture delay (s)", 0.0, 60.0,
                                                                     gs3.MOISTURE_DELAY_S, 1.0, key=f"md_{CK}")
                    st.caption("Empty = the monitor's own values (else the crop table). The vendor's convention for "
                               f"the dry yield of this format: {dflt.shrink.replace('_', '-')}.")
                with st.container(key="run_go"):
                    go = st.button(f"Extract {len(groups)} file" + ("s" if len(groups) != 1 else "") if groups
                                   else "Extract", type="primary",
                                   icon=":material/file_export:", disabled=not chosen, key=f"extract_{CK}")
                if go:
                    opts = dataclasses.replace(dflt, crop=None if crop == FROM_MONITOR else crop,
                                               test_weight_lb_bu=tw, std_moisture_pct=sm, shrink=shrink)
                    with st.status("Extracting ...", expanded=True) as status:
                        try:
                            made = extract(cand, chosen, opts, kw, status.text)
                            ss.datasets.update(made)
                            ss.active = next(iter(made), ss.active)
                            status.update(label=f"Extracted {len(made)} file(s): "
                                                + ", ".join(f"{m['tag']} ({m['n']:,} readings)" for m in made.values()),
                                          state="complete", expanded=False)
                        except ValueError as e:
                            status.update(label="Extraction stopped", state="error")
                            st.error(str(e), icon=":material/error:")
                        except Exception as e:                       # shown, never swallowed
                            status.update(label="Extraction failed", state="error")
                            st.exception(e)
        else:
            if cand.get("sections") and not cand.get("source_path"):
                with st.spinner("One point per header section: collapsing to one reading per combine and second ..."):
                    er.use_candidate(cand, ss.workdir, log=ss.open_log.append)
            tag = er.candidate_tag(cand)
            if tag not in ss.datasets:
                ss.datasets[tag] = {"tag": tag, "shp": cand["path"], "zip": None, "n": int(cand.get("n") or 0),
                                    "kind": "export", "label": os.path.basename(cand.get("source_path") or cand["path"]),
                                    "source": None, "report": None, "area_ac": None, "units": []}
                ss.active = tag
            st.caption("A point export is used as it is: its attributes are the vendor's columns.")

DS = ss.datasets
if not DS:
    st.info("Open the raw data of a field (step 1): the map, the attributes and the cleaning follow.",
            icon=":material/arrow_upward:")
    st.stop()

# ------------------------------------------------------------------------------------------------ 2 map and attributes
with st.container(border=True, key="occd_step_2"):
    brand.step_header(2, "Map and attributes", "One button per attribute: the map, its legend, its statistics")
    tags = list(DS)
    if ss.active not in tags:
        ss.active = tags[0]
    if len(tags) > 1:
        ss.active = st.selectbox("File", tags, index=tags.index(ss.active), key="active_pick",
                                 format_func=lambda t: f"{t} · {DS[t]['label']} · {DS[t]['n']:,} readings")
    D = DS[ss.active]
    df0 = read_points(D["shp"], mtime(D["shp"]))
    det = yc.detect_columns([c for c in df0.columns if c not in ("lon", "lat")])
    yv = pd.to_numeric(df0[det["yield"]], errors="coerce") if det.get("yield") else None
    tcol = det.get("time")
    tt = pd.to_datetime(df0[tcol], errors="coerce") if tcol else None
    mcol = det.get("machine")
    with st.container(horizontal=True):
        st.metric("Readings", f"{len(df0):,}", border=True)
        if D.get("area_ac"):
            st.metric("Area harvested", f"{float(D['area_ac']):,.1f} ac", border=True,
                      help="The strips the readings swept (distance x width), added up.")
        if yv is not None and yv.notna().any():
            st.metric("Mean dry yield", f"{yv.mean():,.1f} bu/ac", border=True)
        if tt is not None and tt.notna().any():
            st.metric("Harvest", f"{tt.min():%d %b %Y}" + (f" – {tt.max():%d %b}" if tt.max().date() != tt.min().date()
                                                            else ""), border=True)
        if mcol:
            st.metric("Machines", f"{df0[mcol].astype(str).replace('', np.nan).nunique():,}", border=True)
    explorer(D["shp"], key=f"raw_{key_of(D['shp'])}", default="Yld_Vol_Dr" if "Yld_Vol_Dr" in df0 else det.get("yield"))
    if D.get("report"):
        with st.expander("What the decoder reported", icon=":material/memory:"):
            rep = D["report"]
            st.caption("Units: " + "; ".join(D.get("units") or []))
            if rep.get("machines"):
                st.dataframe(pd.DataFrame(rep["machines"]), hide_index=True)
            if rep.get("pre_step"):
                st.dataframe(pd.Series(rep["pre_step"], name="records").rename_axis("not exported as readings")
                             .reset_index(), hide_index=True)
            for w in rep.get("warnings") or []:
                st.warning(w, icon=":material/warning:")
    if D.get("zip"):
        download("Extracted points, all readings (.zip)", D["zip"], "application/zip", key=f"dl_ext_{ss.active}")

# ------------------------------------------------------------------------------------------------ 3 SMS 3-sigma
with st.container(border=True, key="occd_step_3"):
    brand.step_header(3, "Cleaning: SMS 3-sigma", "The sequence of Ag Leader SMS Advanced, as OCCD reproduces it")
    st.caption("S0 import check (no position, no yield, dry yield below the SMS import minimum) · S2 Optimize Swath "
               "Widths (overlapping strips removed or narrowed, per-area values scaled) · S3 speed, S4 moisture and S5 "
               "dry yield: keep the mean ± k SD of the points still alive, another yield pass while the SD falls by "
               "more than 25 %. No OCCD cascade, no combine factor, no scale ticket.")
    D0 = sms.DEFAULTS
    with st.container(key="method_panel"):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            k_sd = st.number_input("k (SD)", 1.0, 6.0, float(D0["k_sd"]), 0.5, key="k_sd",
                                   help="Keep mean ± k standard deviations (3 = the 3-sigma of SMS).")
            group_by = st.selectbox("Mean and SD per", list(sms.GROUP_MODES), key="group_by",
                                    format_func={"auto": "auto", "task": "task (dataset)", "machine": "machine",
                                                 "field": "field"}.get,
                                    help="auto: one mean and SD for the field when one combine cut it, one per task "
                                         "(dataset) when several did, as the OFPE team runs SMS.")
            max_passes = st.number_input("Yield passes (max)", 1, 10, int(D0["max_yield_passes"]), 1, key="max_passes")
            min_yield = st.number_input("Import minimum (bu/ac)", 0.0, 50.0, float(D0["min_yield"]), 1.0,
                                        key="min_yield", help="S0: SMS drops the readings below 5 bu/ac at import.")
        with st.container(horizontal=True):
            swath = st.toggle("S2 Optimize Swath Widths", value=bool(D0["swath"]), key="t_swath")
            speed = st.toggle("S3 speed", value=bool(D0["speed"]), key="t_speed")
            moist = st.toggle("S4 moisture", value=bool(D0["moisture"]), key="t_moist")
            yld = st.toggle("S5 dry yield", value=bool(D0["yield"]), key="t_yield")
    sset = {"k_sd": float(k_sd), "group_by": group_by, "max_yield_passes": int(max_passes),
            "min_yield": float(min_yield), "swath": bool(swath), "speed": bool(speed), "moisture": bool(moist),
            "yield": bool(yld)}
    many = False
    with st.container(horizontal=True, key="run_go_box"):
        with st.container(key="run_go_2"):
            one = st.button(f"Clean {ss.active}", type="primary", icon=":material/cleaning_services:", key="clean_one")
        if len(DS) > 1:
            many = st.button(f"Clean all {len(DS)} files", icon=":material/done_all:", key="clean_all")
    todo = [ss.active] if one else (list(DS) if many else [])
    for t in todo:
        with st.status(f"SMS 3-sigma on {t} ...", expanded=True) as status:
            try:
                ss.cleaned[t] = clean_one(t, sset, log=status.text)
                R = ss.cleaned[t]["R"]
                status.update(label=f"{t}: {R['n_in']:,} in → {R['n_kept']:,} kept ({R['removed_pct']:.1f} % "
                                    "removed)", state="complete", expanded=False)
            except Exception as e:                                   # shown, never swallowed
                status.update(label=f"{t}: the cleaning failed", state="error")
                st.exception(e)
    C = ss.cleaned.get(ss.active)
    if C and os.path.exists(C["shp"]):
        R = C["R"]
        if C["settings"] != sset:
            st.warning("The settings changed since this file was cleaned: clean it again to apply them.",
                       icon=":material/sync_problem:")
        with st.container(horizontal=True):
            st.metric("Readings in", f"{R['n_in']:,}", border=True)
            st.metric("Kept", f"{R['n_kept']:,}", border=True)
            st.metric("Removed", f"{R['removed_pct']:.1f} %", border=True)
            M3 = R.get("sms3sigma") or {}
            sw = M3.get("swath") or {}
            st.metric("Narrowed by S2", f"{int(sw.get('n_narrowed') or 0):,}", border=True,
                      help="Readings whose strip overlapped ground already cut: narrowed to the new strip, their "
                           "per-area values scaled (mass kept).")
        t_steps, t_lim, t_clean, t_rem = st.tabs(["Steps", "Limits", "Clean map", "Removed points"])
        with t_steps:
            st.dataframe(pd.DataFrame(R["cascade"])[["filter", "name", "on", "criterion", "removed", "remaining"]],
                         hide_index=True)
        with t_lim:
            steps = (R.get("sms3sigma") or {}).get("steps") or []
            if steps:
                cols = [c for c in ["group", "step", "attribute", "n_before", "mean", "sd", "lo", "hi", "unit",
                                    "removed", "n_after", "sd_drop_pct"] if c in pd.DataFrame(steps)]
                st.dataframe(pd.DataFrame(steps)[cols], hide_index=True,
                             column_config={"mean": st.column_config.NumberColumn(format="%.3f"),
                                            "sd": st.column_config.NumberColumn(format="%.3f"),
                                            "lo": st.column_config.NumberColumn("low", format="%.2f"),
                                            "hi": st.column_config.NumberColumn("high", format="%.2f"),
                                            "sd_drop_pct": st.column_config.NumberColumn("SD drop %", format="%.1f")})
                st.caption("Mean and SD of the points still alive before each step, and the limits typed into "
                           "Filter Data (mean ± k SD, rounded to 2 decimals). Grouping: "
                           + str(((R.get("sms3sigma") or {}).get("grouping") or {}).get("rule", "")) + ".")
        with t_clean:
            explorer(C["shp"], key=f"clean_{key_of(C['shp'])}", height=480,
                     default="Yld_Vol_Dr" if "Yld_Vol_Dr" in read_points(C["shp"], mtime(C["shp"])) else None)
        with t_rem:
            fl = C.get("flagged_shp")
            if fl and os.path.exists(fl):
                F_ = read_points(fl, mtime(fl))
                rb = F_["Rem_By"].astype(str).str[:2]
                grp = np.where(pd.to_numeric(F_["Keep"], errors="coerce").to_numpy(float) == 1, "kept", rb)
                rows = np.flatnonzero(np.isfinite(F_["lon"].to_numpy()) & np.isfinite(F_["lat"].to_numpy()))
                if len(rows) > MAP_N:
                    rows = np.sort(np.random.default_rng(0).choice(rows, MAP_N, replace=False))
                g = grp[rows]
                cols_ = [STEP_COLORS.get(x, "#FF8F00") for x in g]
                rgb = [[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16), 90 if x == "kept" else 230]
                       for h, x in zip(cols_, g)]
                pts = pd.DataFrame({"lon": F_["lon"].to_numpy()[rows], "lat": F_["lat"].to_numpy()[rows], "rgb": rgb,
                                    "v": g})
                if pdk is not None:
                    deck([pdk.Layer("ScatterplotLayer", data=pts, get_position=["lon", "lat"], get_fill_color="rgb",
                                    get_radius=2, radius_min_pixels=1.5, radius_max_pixels=6, pickable=True)],
                         pts["lon"].to_numpy(), pts["lat"].to_numpy(), 460, tooltip={"text": "{v}"})
                vc = pd.Series(grp).value_counts()
                names = {str(r["filter"])[:2]: sms.STEP_INFO.get(str(r["filter"])[:2], {}).get("name", r["name"])
                         for r in R["cascade"]}
                st.html('<div style="display:flex;flex-wrap:wrap">' + "".join(
                    f'<span style="display:inline-flex;align-items:center;gap:6px;margin:2px 14px 2px 0;'
                    f'font-size:0.86rem"><span style="width:12px;height:12px;border-radius:50%;'
                    f'background:{STEP_COLORS.get(k, "#FF8F00")};border:1px solid #1F2937"></span><b>'
                    f'{html.escape("kept" if k == "kept" else k + " " + names.get(k, ""))}</b> {int(n):,} points</span>'
                    for k, n in vc.items()) + "</div>")
                st.caption("Every reading of the file: kept in green (faint), the removed ones in the colour of the "
                           "step that removed them.")

# ------------------------------------------------------------------------------------------------ 4 clean shapefiles
with st.container(border=True, key="occd_step_4"):
    brand.step_header(4, "Clean shapefiles", "The kept readings of each file, with every attribute")
    if not ss.cleaned:
        st.info("Clean a file in step 3: its clean shapefile appears here.", icon=":material/info:")
    else:
        rows = []
        for t, c in ss.cleaned.items():
            R = c["R"]
            rows.append({"file": t, "readings in": R["n_in"], "kept": R["n_kept"], "removed (%)": R["removed_pct"],
                         "cleaned at": c["at"], "clean shapefile": os.path.basename(c["zip"])})
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     column_config={"removed (%)": st.column_config.NumberColumn(format="%.1f")})
        zp = all_clean_zip()
        if zp and len(ss.cleaned) > 1:
            download(f"All {len(ss.cleaned)} clean shapefiles (.zip)", zp, "application/zip", key="dl_all",
                     primary=True, icon=":material/folder_zip:")
        for t, c in ss.cleaned.items():
            st.markdown(f"**{t}**")
            with st.container(horizontal=True):
                download("Clean shapefile (.zip)", c["zip"], "application/zip", key=f"dl_clean_{t}", primary=True,
                         icon=":material/cloud_download:")
                download("Flagged points (.zip)", c.get("flagged_zip"), "application/zip", key=f"dl_flag_{t}")
                download("Report (PDF)", c.get("report_pdf"), "application/pdf", key=f"dl_pdf_{t}",
                         icon=":material/picture_as_pdf:")
                download("Cleaning record (JSON)", c.get("json"), "application/json", key=f"dl_json_{t}",
                         icon=":material/data_object:")
        st.caption("Clean shapefile = the kept readings with every attribute of the extracted file, as SMS exports "
                   "them after Optimize Swath Widths (the narrowed readings carry their new width and scaled per-area "
                   "values; Wdth_Raw and Swath_Scl added). Flagged = every reading with Keep and the step that removed "
                   "it (Rem_By). The files are also in the work folder: "
                   + os.path.join(ss.workdir or "", "clean_shapefiles") + ".")
