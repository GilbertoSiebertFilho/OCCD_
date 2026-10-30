# OCCD — Olds College Cleaning Data

> **Public copy.** Grower and field names, machine serials, scale weights and personal paths were removed from this
> copy. Trials appear as T19, T20 and so on, fields as field A, combines as A to E, and W, V, M and S stand for a
> scale weight, its volume, a monitor total and the scale total at the standard moisture. The tests, the validation
> data, the format notes, the figures and the literature files are not included, so some links here do not resolve.

OCCD is the Olds College Smart Farm app that cleans yield data for the **DIFM platform**: upload the yield data of
one field, choose the cleaning, and get the shapefile to upload. The input can be the point export of the vendor
software (Ag Leader SMS, John Deere Operations Center) **or the raw files of the combine's monitor, without going
through SMS**: the app opens them, decodes them, shows what it read, cleans the readings and returns the DIFM-ready
shapefile. A **field of interest** (boundary or trial design) keeps only the field of the trial when the grower's
export holds several fields, and the run reports the **harvest sessions** (days / combines), the **moisture basis**
and the **combine harmonisation** so that the yield column mapped in DIFM is the right one.

Owner: Gilberto Siebert Filho, Olds College Smart Farm (OFPE). App version 2.4.1 (2.4.1 = 2.4.0 with the fixes of its deploy review: a field saved
before v2.4 opens with its result as the previous run, the flow-delay scan's axis is a step-3 choice, the app reloads
the engine on any changed file; 2.4 = the overlap filter F8 on the strip
the header swept between two readings, placed by `Y_Offset`, with its threshold read on the pass interiors against
local no-overlap controls of the same combine at the same distance from the harvested edge, and never below 5 %; the
flow-delay scan on the passes of the direction the field was harvested in, still applied to the output geometry after
the cascade as in v2.3; the maps drawn with the swept strips; `LEGACY_V23` reproduces a cleaning delivered before:
sections *The overlap model of v2.4* and *Evidence for v2.4* below; v2.3 = a second cleaning method, the **SMS 3-sigma** sequence of Ag Leader
SMS Advanced, and the option to run **both methods and compare** them; v2.2 = the OCCD brand, saved fields and *Start
over*; v2.1 = cleaning only with the field of interest, sessions, combines and references). The DIFM-analysis version
(v1) is archived in `_archive/v1_difm_analysis/` (see the end of this page).

## Start the app

Double-click `run_app.bat`, or from this folder:

```
python -m streamlit run app\app.py
```

The app opens in the browser at http://localhost:8501. Install the packages once with
`python -m pip install -r requirements.txt` (Python 3.12 or newer; tested with Python 3.14 and Streamlit 1.61.1 on
Windows 11). R is no longer needed.

On a new computer: copy this folder (the `workspace/` with the saved fields is optional), install Python 3.12 or newer
and double-click `install_occd.bat`, which creates a private environment `.venv` here and installs
`requirements.txt`; `run_app.bat` uses that environment when it exists. `INSTALAR.txt` has the steps in Portuguese.

After an update of the app's files, refresh the browser page: the running app re-imports the changed code (app.py compares the time and size of every file of `engine/` and of `app/brand.py` with the ones it imported and reloads them when any differs, also when a restored backup puts older times back; Streamlit itself only reloads `app/`). Only a change to `.streamlit/config.toml` (the theme) needs the app closed and started again, and so does going back to 2.4.0 or older: their app.py reloads the engine only for newer files, so close the app before copying the old files and start it again after.

The same work runs from the command line, from the input to the DIFM-ready zip:

```
python -m engine.run <file|folder|zip> --out <work folder>
                     [--aoi FIELD.geojson|.shp|.zip|.gpkg|.kml|.kmz] [--crop C]
                     [--scale-ticket VALUE --ticket-unit lb|kg|bu|t --ticket-basis wet|dry --ticket-moisture PCT]
                     [--scale-ticket-bu BU] [--machine-total VIN=BU ...] [--reference-machine ID] [--standard-moisture PCT]
                     [--shrink auto|one_sided|symmetric] [--settings s.json]
                     [--method occd|sms3sigma|both] [--sms-group auto|task|machine|field]
                     [--field NAME] [--year YYYY] [--units all|id,id] [--allow-mixed]
                     [--test-weight LB] [--std-moisture PCT] [--boundary FILE] [--candidate N] [--list]
```

`--list` only shows what was recognised and the units of a raw dataset (`*` = pre-selected). One file is one
harvest: without `--field` the CLI decodes the pre-selected (most recent season) units of the field with the most
records, as the app does; `--field` takes that field (exact name, else a substring) in its most recent season unless
`--year` is given. **With `--aoi` and no `--field`/`--units`, the field of interest chooses the units**: every
latest-season unit with at least 20 % of its readings inside the polygon + 50 m is decoded (Trial 19 card: the four
field A 2026 tasks, 100 % inside; the task logged under field A but 63 m outside the boundary is left out). A
selection with more than one field, crop or season is refused unless `--allow-mixed` is given (DIFM and the overlap
filter expect one harvest per file); with an AOI several monitor field names are not a mix (a GreenStar
card: two fields, one boundary file). When several datasets are detected, the CLI uses the only raw one, otherwise it
stops and asks for `--candidate N`. Each call unpacks into its own `input/` (`input_2`, ... when the work folder is
reused), so a reused `--out` never picks up an earlier input. Exit codes: 0 done, 2 a problem the user can fix (the
message says what), 3 an unexpected error (the traceback is written to `<out>/error_<time>.log`).

## The four steps of the app

1. **Input.** Upload files (a zip, the `.shp` + `.shx` + `.dbf` + `.prj` (+ `.cpg`) of an export, or raw monitor
   files), or type a file or folder on this computer and press *Open*. A folder on this computer is read in place
   (nothing is copied), which is the fast way for a whole monitor card. Zips are unpacked recursively (a zip of
   per-combine zips is fine). The app lists what it recognised; when there are several datasets, choose one.
   **Field of interest (optional):** upload the boundary or the trial design of the field (`.shp` zip, `.geojson`,
   `.gpkg`, `.kml`, `.kmz`, any coordinate system) or pick the example (Trial 29 trial design). The app shows polygons / plots / headland polygons / area and the rate column found.
2. **Decode** (raw data only). Pick the field and the units (tasks, machines or loads; the most recent season is
   pre-selected; with a field of interest the units are pre-selected by their share of readings inside it and the
   table shows that share; a selection of several seasons or crops must be confirmed), the crop (default: the
   monitor's, shown next to the box; a different crop also replaces the monitor's test weight and standard moisture
   by the crop table's), test weight and standard moisture (default: the monitor's, else the crop table), and the
   dry-yield convention (default: the vendor's, one-sided for the three raw formats).
   *Decode* writes every reading (uncleaned) in the standard SMS / Ops Center schema and shows the totals, a
   per-machine table, the records not exported and why, the calibration and validation notes, the decoder warnings
   and a map (with the field outline when one is loaded). For an export, this step shows the points, the columns and
   the column mapping found.
3. **Cleaning.** Crop (prefilled from the decoder or the export's Product column; it sets the F1 moisture window),
   column mapping (prefilled; required columns marked `*`), the 13 filters in four groups, each with its switch, its
   thresholds, its rule and **the literature behind it (one line under the filter; the *References* popover lists
   the full citations with their DOI)**, and the corrections in tabs: flow delay; *Field of interest* (processing
   buffer, clip of the DIFM file); *Sessions & moisture* (standard moisture, shrink convention, the `Yld_Dry_Sy`
   column); *Combines* (reference combine, per-combine weighed totals, same-plot pairs, maximum factor); the
   **grower's weight** (scale ticket: the value in lb / kg / bu / t, wet or dry basis, the ticket's moisture; the
   conversion to bushels is shown under the box, e.g. "= 31,256.5 bu at 47.99 lb/bu (test weight from the file)");
   output name. *Reset to house standard* restores the defaults below. A *References* expander lists every
   work cited by the enabled steps. The **Cleaning method** selector at the top chooses the OCCD cascade (the house
   standard, default), the **SMS 3-sigma** sequence (the steps done by hand in SMS: clip, Optimize Swath Widths, then
   speed, moisture and dry yield within mean +/- 3 SD; its options are in the *SMS 3-sigma* tab) or **Both, and
   compare** (section *The SMS 3-sigma method* below).
4. **Run and download.** *Run cleaning* (with the *Field name* box beside it) streams the log, then shows a compact
   summary: the metrics readings in / kept / removed % / mean yield of the DIFM column / the level factor (only when
   a weight was given, with "monitor 38,613 bu vs scale 36,608 bu (-5.2 %)" under it) / the DIFM column, one line
   with the F8 threshold, the flow delay and the records dropped outside the field, the warnings and the checks worth
   doing only when there are any, the downloads: the **DIFM-ready shapefile (.zip)**, the report PDF, the flagged
   points, the decoded points (raw input) and the cleaning JSON, and **which column to map in DIFM and why**. The
   *Figures and diagnostics* expander holds the output folder and the tabs: the map (each reading as the strip its
   header swept, with the field and plot outlines), the overlap dose-response, the cascade, the flow-delay scan, the **Sessions** (table, discontinuity
   check, figure, recommendation), the **Combines** (means, paired factors with CI, decisions, the closure test with
   the grower's weight, per-machine totals and their validation), the **Field of interest** (counts, DIFM-ready
   points on a map) and the cascade table. With the SMS 3-sigma method the tabs are the map, the limits of every
   3-sigma step, the steps, the sessions, the combines, the field of interest, the **limits per group** (mean,
   SD, low, high of every step as SMS *Edit Legend* shows them) and the steps table. With *Both* the result has three tabs: **Compare
   methods** (kept by both / by one only, agreement, side-by-side statistics, which step removed what the other
   method kept, by combine / session / plot / target rate, the agreement map and the comparison report), the OCCD
   result and the SMS 3-sigma result. Changing a setting after a run hides that result until the cleaning is
   run again. The decoder's warnings, the source and the checks are written into the cleaning JSON and PDF.

Every opened input gets its own work folder `workspace/<YYYYmmdd-HHMMSS>_<tag>/` with `input/` (uploads and unpacked
zips), `decoded/` (`<tag>_decoded.zip` and `<tag>_decode_report.json`) and `output/` (one folder per cleaning run:
`output`, `output_2`, ...); uploaded field files go to `workspace/aoi_uploads/`. A full run writes about 120 MB for a
33,000-point field: delete old run folders when they are no longer needed. Set the environment variable
`YIELD_APP_WORKSPACE` to put the work folders elsewhere.

## Saved fields and start over

Every cleaning run is **saved as a field**. At the end of a successful run the app writes `field.json` into the
run's work folder (`workspace/<stamp>_<tag>/`) and shows "Saved: <name>". The record (version 1) holds the input
(kind, paths as given, tag, format / decoder, units and decode options), the decoded file, the field of interest
(the file is copied into `<workdir>/aoi/`, so the folder is self-contained, with the buffer, the clip choice and the
id / rate columns), the crop, the exact settings the engine received, the grower's weight when one was given (none
is not a problem: the app never asks for it), the outputs (DIFM-ready zip, flagged zip, cleaning JSON, report PDF,
figures) as relative paths and a summary (readings in, kept, removed %, mean yield, DIFM column, level factor,
combines, sessions, run time). The default name is the field name of the plan or boundary when one is loaded, else
the input tag; the *Field name* box next to *Run cleaning* sets it before or after the run (renaming after the run
rewrites `field.json`).

The **Saved fields** block at the top of the sidebar lists the saved runs (name · date · crop; the caption under the buttons gives the
readings in and kept) with *Open*, *Rename* and *Delete*. *Open* restores the whole screen from the saved files **without running the engine
again**: the input, the decoded data, the field of interest (outline and plot tagging), the step-3 settings and the
processing tree as they were used, and the result of step 4 (metrics, downloads, report and figures). A field cleaned
before v2.4 opens with the v2.4 settings on the screen and its result marked as the previous run: it was cleaned
with the v2.3 overlap model, which those settings would not repeat; the page says so, and the (v2.3) choices of
step 3 make it current again (*The overlap model of v2.4* below). A reopened
field can be run again (new outputs; `field.json` is updated). When the outputs are missing (the folder was moved
or deleted outside the app) the app says so once and *Run cleaning* rebuilds them with the restored settings (for a field cleaned before
v2.4 the page adds that those settings carry the v2.4 model unless the (v2.3) choices are set). *Delete* asks for confirmation and removes that
one run folder with its input, decoded data and outputs; nothing else is touched. A run folder of an older version
(no `field.json`, but an `output/*_cleaning.json`) is listed too and left as it is until it is renamed or run again.
`engine/fields.py` holds the record and the list / load / save / rename / delete functions (relative paths, so a
moved workspace still opens).

**Start over** (the button at the top right of the page) clears the current
process: every session value and every widget goes back to the house standard and the page is empty again. It
deletes nothing on disk; the saved fields stay in the sidebar. It asks for confirmation only when the input on the
screen is not saved yet (opened or decoded without a completed run, or settings changed after the last save);
otherwise it is immediate.

## Supported inputs and what to upload

| Input | Recognised by | What to give the app |
|---|---|---|
| Point export (Ag Leader SMS, John Deere Ops Center, or any point shapefile with yield, speed, heading, distance and swath width) | any POINT shapefile with a yield column (dry or wet yield, or wet mass); polygon layers and point layers without one (as-applied, seeding) are ignored with a note, and the same export found twice (a zip next to its unpacked copy) is listed once | the zip of the export, or the `.shp` with its `.shx`, `.dbf`, `.prj` (`.cpg`) |
| Case IH / New Holland AFS Pro 700 card (`.cn1`) | a folder with `index.vy1` starting with `CNH1` | the whole `<name>.cn1` folder (zipped, or its path on this computer); a partial copy of `.fld` folders is accepted with a warning |
| John Deere Gen4 / G5 / X9 display logs (`.jdl`) | `.jdl` files anywhere under the input | the `JD-Data` folder of each combine, e.g. the Ops Center download: one `<VIN>_<date>.zip` per combine, all in one zip |
| John Deere GreenStar 3 (2630) card (`.fdd` + `.fdl`) | `.fdl` files starting with `<RCDLogFile` with their `.fdd` | the `RCD/EIC/Documentation` folder (or the card above it); keep the `.fdr` load files to get load names |
| **Field of interest** (optional, with any input above) | a polygon file: `.shp` (+ parts, or zipped; a zip that also holds guidance lines is fine, the polygon layer is read), `.geojson`, `.gpkg`, `.kml`, `.kmz`, in any coordinate system | the field boundary (one polygon; a field in several parts = one MultiPolygon feature) or the trial design: one polygon per plot plus the headland / border polygon (`type` = headland or border, or the single untyped polygon larger than 5 x the median plot), with the plot id in `plot` / `Plot_Id` / `id` / `Obj__Id` (else the row number) and the target rate in the first `tgt*` / `Tgt*` column or `rate` / `Rate_l` / `Tgt_Rate_l`. A file that holds **several field boundaries** (no rate / plot column, fewer than 4 polygons or polygons of unlike size) is not a design: the app asks which polygon is the field of interest (CLI `--aoi-feature N`) and never unions the fields |

The decoders write the same columns as an SMS / Ops Center export (`engine/formats/common.py`): Field, Dataset,
Product, Obj__Id, Time (with time of day), Duration_s, Elevation_, Speed_mph_, Distance_f, Track_deg_, Swth_Wdth_,
Moisture__, Yld_Mass_W, Yld_Mass_D, Yld_Vol_We, Yld_Vol_Dr, Machine and Src_Fmt. So a decoded field is cleaned
exactly like an export and the DIFM column mapping is the same. How each format is decoded and validated against the
vendor software is in `docs/FORMATS.md`.

## What to upload to DIFM

Upload `<tag>_difm_ready.zip` (only `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`) as the yield data. The cleaning keeps
every original column and value of the kept points (byte copy of the records) and appends its own columns, so the
mapping is the same as for the original export. The app, the CLI summary and the report say which column to map for
each run (`engine.run.recommended_yield_column`).

### Which yield column to map in DIFM

| Situation (as the run reports it) | Map as the yield | Also map / keep |
|---|---|---|
| One combine, one day, no scale ticket (a plain run) | `Yld_Vol_Dr` (the dry yield as the monitor mapped it) | - |
| A harvest over several days or sessions, or many readings below the standard moisture under one-sided shrink (the run says "map Yld_Dry_Sy ... keep Harv_Day as a block": > 2 moisture points between sessions, or > 20 % of the readings below the standard) | `Yld_Dry_Sy` (wet yield x (100 - M) / (100 - standard moisture), the symmetric dry-matter basis) | `Harv_Day` as a block (and `Session` to audit) |
| Several combines and a harmonisation factor **applied** (paired cells, or per-combine weighed totals) | `Yld_Harm` (mapped dry yield x each combine's factor; 1 where the difference was not proven). It wins over `Yld_Dry_Sy`, which carries no combine factor; keep `Harv_Day` as a block when the sessions also asked for it | - |
| Several combines, no factor applied (difference not proven, too few pairs, or > 10 %: "request per-machine weights") | `Yld_Vol_Dr`, or `Yld_Dry_Sy` when the sessions recommend it; give the per-combine weights (`--machine-total VIN=BU`) to level each combine to its own ticket, or the grower's field weight (below): when it confirms the factor above 10 %, the factor is applied | `Machine` as a block if DIFM allows it |
| **The grower's weight given** (`--scale-ticket 1500000 --ticket-unit lb`; the app's Corrections tab): L = weight / monitor total of the processed set | the **leveled** column is the real yield: `Yld_Lvl_Sy` (= `Yld_Dry_Sy` x factor x L) when the sessions recommend the symmetric basis, else `Yld_Level` (= mapped dry yield x factor x L). The note reads "leveled to the grower's weight 1,500,000 lb (L = 0.948): the bu/ac now sum to the scale" | `Harv_Day` as a block when the sessions asked for it |
| A trial design given as the field of interest | the column above | `Plot_Id` and `Tgt_Rate` (point-in-polygon from the design; empty outside the plots) to check the design against the harvest before the DIFM run |

Rules behind the table: `Yld_Dry_Sy` is a basis change, not a correction (it is identical to the mapped dry yield
above the standard moisture when the monitor shrinks one-sided); the sessions and the moisture basis are
**diagnostics, never corrections**. A harmonisation factor is applied only when it is proven (section *Several
combines* below), otherwise nothing is changed and the reason is written. The file is in WGS 84: an export in another
coordinate system (e.g. UTM) is reprojected and a note says so. A file that is itself an output of the app (it
already holds `Yld_Harm`, `Yld_Level`, `Rem_By`, ...) is refused: clean the original export. No DIFM file is written
when fewer than 30 points survive; the message names the filter that removed the most.

### Columns the cleaning adds

| Column | Type | In | Meaning |
|---|---|---|---|
| `Yld_Harm` | N 15.4 | DIFM-ready, flagged | mapped dry yield x the combine's harmonisation factor (several combines) |
| `Yld_Level` | N 15.4 | DIFM-ready, flagged | mapped dry yield x harmonisation factor x L: the yield leveled to the grower's weight; only with a scale ticket or per-combine totals |
| `Yld_Lvl_Sy` | N 15.4 | DIFM-ready, flagged | `Yld_Dry_Sy` x harmonisation factor x L: the symmetric dry-matter yield leveled to the grower's weight; only when a weight is given in a v2 run and the symmetric column is written (`moisture.add_symmetric_column` true and computable; the legacy `scale_ticket_bu` run writes `Yld_Level` only) |
| `Yld_Dry_Sy` | N 15.4 | flagged; DIFM-ready in a v2 run | wet yield x (100 - M) / (100 - Ms): the symmetric dry-matter basis (needs a wet yield or wet mass + test weight, a moisture column and a standard moisture Ms) |
| `Harv_Day` | C 10 | flagged; DIFM-ready in a v2 run | calendar day of the record (local day: records a decoder reports as UTC are shifted by the decoder's time-zone offset, else by round(longitude / 15) h; times already local are left alone), or, when the records carry no time of day, the date in the dataset name (SMS `YY/MM/DD-HH:MM:SS`, Ops Center `TaskName M/D/YYYY`) or the date-only time column |
| `Session` | C 32 | flagged; DIFM-ready in a v2 run | `<machine>\|<day>` (or the dataset key without a time of day); a long machine id keeps its tail, never a truncated day |
| `In_AOI` | N 1 | flagged | 1 inside the field of interest itself (0 m), 0 in the 50 m buffer |
| `Plot_Id` | C 16 | DIFM-ready, flagged (trial design only) | plot id of the design polygon the point falls in; empty outside the plots |
| `Tgt_Rate` | N 12.3 | DIFM-ready, flagged (design with a rate column) | target rate of that plot |
| `Keep`, `Rem_By`, `Pass_Id`, `Run_Id`, `Overlap_f`, `Lag_rec`, `X_log`, `Y_log` | - | flagged | audit of every removal (as in v2.0); `Overlap_f` is the share of the record's footprint (since v2.4 its swept strip) already cut, the value F8 judged: at the logged position by default, at its flow-delay source (`Lag_rec` records away) only with the `lag_stage` "before_f7" option |
| `Wdth_Opt`, `Dist_Opt`, `Swath_Scl` | N | flagged (SMS 3-sigma) | the optimised width, the shortened distance and the scale factor of Optimize Swath Widths (the DIFM-ready file carries them in the export's own columns, plus `Wdth_Raw` and `Swath_Scl`) |

A **v2 run** is one that gives the crop, the standard moisture or a field of interest (the app does so whenever it
knows the crop; `R["v2_columns"]`). A plain run (none of them) writes the DIFM-ready `.dbf` byte for byte as v2.0 did,
which is what the regression test asserts (Trial 19 with the grower's ticket and the v2.3 overlap model
`LEGACY_V23`, md5 `1181f19cc6b5b921c8bce0b298f43de9`; the v2.4 defaults keep other records, written the same way).

## The SMS 3-sigma method and the comparison of the two methods

`--method sms3sigma` (the app's *Cleaning method*) runs, instead of the cascade, the Ag Leader SMS Advanced sequence
the OFPE team does by hand (`engine/clean/sms3sigma.py`, `engine/clean/sms_swath.py`; docs/METHOD.md section 10):
S0 the SMS import check (no position / no yield / dry yield below 5 bu/ac), S1 Clip To Field Boundary (needs a field
of interest; a point on the edge is inside), S2 Optimize Swath Widths (individual swath rectangles in harvest time
order over every task and combine: fully overlapped readings removed, partly overlapped ones narrowed to the uncovered
strip and moved to its centre, readings overlapped at the back by their predecessor shortened, and the per-area
values of both scaled by old / new area), S3 speed and S4 moisture within mean
+/- 3 SD, S5a the scaled dry yield within mean +/- 3 SD with the lower limit floored at 0, and S5b, S5c ... only while
the previous pass cut the SD by more than 25 %. Mean and SD are recomputed on the points still alive before every step
(the plain point statistics of Edit Legend), the limits are rounded to 2 decimals as typed in SMS, and they are
computed per task when several combines cut the field, pooled when one did (`--sms-group` forces it). The outputs are
named `<tag>_sms3s_*`; the DIFM-ready file is written as SMS exports it after the swath step (the narrowed points
carry the optimised width in the width column and scaled yields; `Wdth_Raw` and `Swath_Scl` are added), so it is
mapped like an SMS export.

`--method both` cleans the same readings with both methods: the OCCD outputs in `output/` (the DIFM-ready and flagged
shapefiles byte-identical to an OCCD-only run; its cleaning JSON adds `method = both` and a `methods` block with the
other two summaries), the SMS 3-sigma outputs in `output/sms3sigma/`, and the comparison in `output/compare/`
(`engine/clean/compare.py`; docs/METHOD.md section 11): points kept by both / by one only, agreement, statistics side
by side, the step of each method that removed what the other kept, by combine / session / plot / target rate,
figures, `<tag>_methods_comparison.json/.csv`, `<tag>_methods_points.zip` and `<tag>_methods_comparison_report.pdf`.

Optimize Swath Widths is not documented by Ag Leader; `engine/clean/sms_swath.py` reproduces it from SMS's own
raw vs cleaned exports. On seven 2026 trials (Case IH and John Deere GreenStar 4, one to four combines) the final
point count is within 0.42 % of SMS's on every field, and on the five trials with a usable SMS clean export
98.8-99.9 % of the kept readings are the same ones (docs/METHOD.md section 10.1). The speed and moisture limits
match SMS to 0.1 or better. The dry-yield limits can differ more, because a few narrow slivers left by the swath
step set the first pass's SD. An SMS export of GreenStar 4 data has dates only, so its datasets are ordered by the
date in their names and its logged files are put back in time order by position (`swath_order` auto).

## The cleaning (house standard)

`engine/clean/yield_clean.py`; the method and its evidence are in its docstring and in `docs/METHOD.md`. Every filter
can be switched off (it is then logged with 0 removed). The literature behind every step is in
`engine/clean/references.py` (`cite(step)`), built only from `docs/literature/references_verified.csv` and the review
`docs/literature/Yield_map_cleaning_literature_review.md`; `docs/REFERENCES.md` lists what each work supports, and
`docs/method_check/OCCD_method_and_references.pdf` (Portuguese: `OCCD_metodo_e_referencias.pdf`) goes through every
step: what the app does, what the literature says, the support and what changed after the check of 29 October 2026.
Those two PDFs were written for v2.3.0 and are not rebuilt: the v2.4 changes to F8, the flow-delay scan and the maps
are in `docs/METHOD.md` (sections 3, 3.1, 4, 8, 12 and 13), in the sections *The overlap model of v2.4* and
*Evidence for v2.4* below, and the evidence itself in `docs/overlap_v24/`. Where a number is a house convention the
line says "house rule".

| Step | Default rule | Sources (at most three per step; what each gives: the app / `docs/REFERENCES.md`) |
|---|---|---|
| AOI Field of interest (pre-step) | records farther than 50 m from the field of interest are set aside before the cascade; the DIFM file is clipped to the field itself | Menegatti & Molin 2004; Owen et al. 2024; Edge et al. 2024; 50 m processing buffer, plan detection from >= 4 similar polygons and the headland as the polygon > 5 x the median area: house rules |
| F0 Record integrity | missing/zero yield, zero distance, or no / implausible position (none, (0,0), outside lon/lat ranges, > 50 km from the median position) | Menegatti & Molin 2004; Menegatti & Molin 2003; Alves et al. 2026; position checks: house rule |
| F1 Moisture | moisture outside the crop window or missing: barley / wheat / durum / oats / rye 8-20 %, canola / flax 4-16 %, peas 8-24 %, lentils 8-22 %, corn 10-33 %, soybeans 8-25 %; no crop -> 8-20 % (small cereals) with a note | Luck & Fulton 2014; Menegatti & Molin 2003; crop windows other than corn 10-33 %: house rule |
| F2 Speed | speed outside 1.5-6.5 mph | Sudduth & Drummond 2007; Luck et al. 2015; Griffin et al. 2008; 1.5-6.5 mph window: house rule |
| F3 Speed change | speed change > 20 % per second | Sudduth & Drummond 2007; Griffin et al. 2008; Luck et al. 2015; SMV ratio per second and over the current speed: house form |
| F4 GNSS step | GNSS step differs from the logged distance by > 50 % | Lyle et al. 2014; Damiano & Niemi 2022; Menegatti & Molin 2003; GNSS step vs logged distance test and its 50 % tolerance: house method |
| F5 Short pass | pass shorter than 10 surviving points | Ping & Dobermann 2005; Clarke et al. 2024; Arslan & Colvin 2002a; 10 points per pass: house value within the published 3-12 points |
| F6 Heading change | heading change > 30 deg/s | Clarke et al. 2024; Drummond et al. 1999; Marchant et al. 2019; 30 deg/s removal and the 60 deg and 15 m pass breaks: house values |
| F7 Pass ends | first 4 and last 2 points of every pass (with the `lag_stage` "before_f7" option, also the records whose flow-delay source lies beyond their pass) | Sudduth & Drummond 2007; Griffin et al. 2008; Simbahan et al. 2004; first 4 / last 2 surviving records, one setting for all fields: house values, inside the 3-8 s / 2-4 s of the cited works |
| F8 Overlap | the swept strip (from the header line at the previous reading of the pass to the header line at this one, across the travel, centred `Y_Offset` to the right) over ground already cut, above the automatic threshold: the field's own dose-response, measured on **every record of the pass interiors** (>= 15 records alive after F7 on both sides; **in-plot when a trial design is given**) against its **local no-overlap controls** (same combine - the machine column, else the SMS serial in the dataset names, else the Ops Center log -, another pass, within max(15 m, 1.5 header widths), the same distance from the harvested edge within 4 m, >= 5 controls; per band the median ratio over the placebo, >= 30 matched records, tolerance 3 %), **never below 5 %**, or a manual %. With fewer than 30 no-overlap records that have controls, the v2.3 reference (each combine's own no-overlap band, which needs >= 500 points or >= 10 % of the combine's records) with a warning; when already the 0-2 % band fails, the fallback threshold (10 %) with a warning. The JSON reports the footprint, the reference, the placebo and the matched counts, whether the floor applied, the band that set the threshold, its margin to the tolerance, and the band that stopped the scan with why (`stop_kind`: too few matched records, or a yield drop) | Drummond et al. 1999; Han et al. 1997; Alves et al. 2026; dose-response threshold: house method - no paper derives an overlap threshold from yield |
| F9 Wet mass | wet mass outside 500-10,000 lb/ac | Arizo-García et al. 2026; Ping & Dobermann 2005; Menegatti & Molin 2003; 500-10,000 lb/ac wet for every crop: house window |
| F10 Mean +/- k SD | outside mean +/- 3 SD | dos Santos & Miguez 2025; Sudduth & Drummond 2007; Ping & Dobermann 2005; all combines pooled in one mean and SD: house rule |
| F11 Local median | > 30 % from the median of its +/-10 in-pass neighbours | Maldaner & Molin 2020; da Silva et al. 2024; Lyle et al. 2014; +/- 10 records window and a minimum of 6 surviving records in it: house values |
| F5b Short runs | surviving run of fewer than 10 points | Ping & Dobermann 2005; Clarke et al. 2024; Marchant et al. 2019; 10-record minimum re-applied to runs broken by any removal: house extension |

Corrections and diagnostics: the residual flow delay (scan of -8..8 records between opposite-direction neighbours on
the kept records after the cascade, on the passes of the axis the field was harvested in; *auto* shifts by minus the
best lag only when that lag is 2 to 7 records from 0 and improves r by more than 0.01, and the shift moves the output
geometry only: F7 and F8 judge every yield at its logged position), the harvest sessions and the moisture basis
(below), the combine harmonisation (below), the level factor `L = scale ticket / integral of the processed set` (new
column `Yld_Level`) and the old `boundary` setting (a diagnostic of the level only; `--aoi` replaces it).

Order of the readings: per-record time when the time column has a time of day (every decoded file), otherwise the
dataset start and the record id (SMS / Ops Center exports, whose `Time` is a date only). The dataset start is the
time `YY/MM/DD-HH:MM:SS` in an SMS task name or the date `M/D/YYYY` in a GreenStar 4 / Ops Center task name, so
`TaskName 9/9/2026` comes before `TaskName 9/16/2026` (as text it would not; names without either come last).

### The overlap model of v2.4 and the switch back to v2.3

v2.4 (29 October 2026) changed the overlap filter F8, the axis of the flow-delay scan and the maps of the OCCD method
(the SMS 3-sigma method is unchanged). The changes come from the house's pre-registered overlap tests A (bias), B
(pass-end ramp) and C (geometry) on seven 2026 trials (Case IH T19, T20, T25; John Deere GreenStar 4 T22, T23, T29,
T30), their adversarial reviews, and a pre-registered before/after evaluation of v2.4 on the same seven trials (section
*Evidence for v2.4* below; `docs/METHOD.md` sections 3.1, 4 and 13; the files are in `docs/overlap_v24/`, with the
synthesis of the tests in Portuguese, `SINTESE_testes_ABC_pt.md`):

- **F8 footprint = the swept strip** (`filters.F8.footprint` "swept"): the quadrilateral between the header line at
  the previous reading of the pass and the one at this reading, each across the direction of travel taken from the
  positions. Consecutive strips share an edge (0 m² of overlap in 372,435 consecutive pairs), so a reading no longer
  counts its own predecessor as overlap: the v2.3 chord rectangle counted a wedge of about (W² / 8) tan Δβ in every
  curve, which alone caused 9-55 % of the v2.3 F8 removals (evaluation, P2), and in 4 of the 7 trials those records
  yield like their pass. A reading without a usable predecessor (pass start, a step of 0 or a GNSS jump) keeps the
  v2.3 rectangle.
- **The strip sits `Y_Offset_f` to the right of travel** (`filters.F8.y_offset` true), as SMS places it: the John
  Deere monitor logs a narrowed width with the offset of the active sections (|Y_Offset| > 1 ft on 7-30 % of the
  readings, within 1 ft of half the narrowing on 85-99 % of the narrowed ones); Case IH logs about 0. With the offset
  the median overlap of the narrowed John Deere records falls to 0 in 4 of 4 trials (P4).
- **The dose-response is read on the pass interiors against local controls** (`filters.F8.reference` "local"): every
  record with at least 15 records alive after F7 before and after it in its pass (the in-plot ones when a trial
  design is given) is compared with the no-overlap records of that same population that belong to the same combine,
  lie on another pass, within max(15 m, 1.5 header widths) of it (`local_radius_m` is the 15 m; 16-23 m for 35-50 ft
  headers) and within 4 m of its distance from the edge of the harvested area (`edge_tol_m`), at least 5 of them
  (`min_controls`). The combine is the machine column; without one, the display serial that SMS writes at the end of
  Case IH / Ag Leader dataset names; else the Ops Center log (a record-id restart inside a task); else one combine for
  the file (`R["f8"]["local"]["combine_key"]`). Per band, the median ratio of the band's records to their controls is
  divided by the **placebo** (the same ratio of the no-overlap records themselves), and a band counts only with >= 30
  matched records. Why: the overlapped records lie 9-32 m from the edge and the no-overlap ones 60-160 m, and near
  the edge no-overlap records read 0.78-1.23 of no-overlap controls, so the field-wide band of v2.3 mixed the edge
  gradient into the curve; the pass interiors leave out the pass-end ramps, a machine transient longer than F7 (test
  B), not overlap; the radius reaches the next pass of the same combine. With fewer than 30 no-overlap records that
  have controls, the run falls back to the v2.3 reference with a warning (`R["f8"]["reference_mode"]` "field").
- **The automatic threshold never goes below 5 %** (`min_threshold`), the resolution of the overlap measure: 0.3-1 m
  of position error is 2.0-9.4 % of a 10.7-15.2 m header, one 0.25 m raster column 1.7-2.3 %, moving the raster origin
  by 0.125 m changed 59-73 % of the Trial 19 F8 decisions at 5 %, and automatic thresholds of 2 % moved with the
  raster origin in the evaluation (P3). The floor applies only to the automatic threshold, not to a fixed one or to
  the 10 % fallback; `R["f8"]["floor_applied"]` says when it bound. F8 still removes records and corrects none (the
  y / (1 - f) correction over-corrects: 1.051 at 5-10 %, 1.114 at 10-15 % overlap on Case IH).
- **What the JSON says about the threshold.** `R["f8"]` gives the band that set it (`last_pass_band`, `margin_pct`),
  the band that stopped the scan (`stop_band`, `stop_reason`) and why (`stop_kind`: `too_few` = the next band has
  fewer than 30 records with controls, so the threshold reflects how many records found controls, not a measured
  drop; `tolerance` = the next band reads more than 3 % below its controls), `floor_applied`, `reference_mode` and
  `local` (`radius_m`, `placebo_ratio`, `placebo_n`, `matched_n`, `dose_n`, `combine_key`, `population`). The report
  and the app's summary line state them.
- **The flow delay stays where v2.3 applied it** (`lag_stage` "output", the default): the scan runs on the kept
  records after the cascade and the shift moves the output geometry only, so F7 and F8 judge every yield at its logged
  position. New in v2.4 is the axis the scan compares (`lag_axis` "dominant"): the passes of the direction the field
  was harvested in; v2.3 (`"ew_first"`) took the E-W passes whenever both E and W held >= 200 records, which on a N-S
  field scanned its few E-W headland passes (T20, T25, T23 and T29 are 77-94 % N-S). On the seven trials the shift
  becomes T19 0, T20 +5, T25 +4, T22 +2, T23 +2, T29 +2, T30 0 records (v2.3: 0, +2, +3, +2, +2, -5, 0). Measuring the
  delay after F6 and tying every yield to its source position before F7 and F8 (`lag_stage` "before_f7") **failed its
  pre-registered test** (P5: the end-of-pass deficit D5e stayed at 0.126, 0.133 and 0.331 on T22, T23 and T25 against
  a bound of 0.10; it also switched T22's F8 off through relabelled pass-start spikes, threshold 15 % -> 100 %, and
  removed 311-2,313 records whose source lay beyond their pass); it is kept as an option for research runs only.
- **The maps draw the swept strips** (the run's figures, the app's maps, the comparison's agreement map), so a turn
  no longer shows a fan of overlapping rectangles nor a Case IH pass start a stack of strips; the SMS 3-sigma map and
  the app's map of an SMS 3-sigma output keep SMS's rectangles with the optimised width and distance. The strips are
  for display only: no total is computed over them.

**To reproduce a cleaning delivered before v2.4** (every cleaning up to v2.3), run it with the v2.3 model,
`yield_clean.LEGACY_V23`. In the app: step 3's choices marked (v2.3), that is F8's footprint *chord rectangle* and
reference *whole no-overlap band*, its *Y_Offset* off and its floor 0, and under *Flow-delay correction* *Passes the
delay scan compares* = *east-west first*. From the command line: these settings saved as a file and passed with
`--settings`:

```json
{"filters": {"F8": {"footprint": "chord", "y_offset": false, "reference": "field", "min_threshold": 0}},
 "lag_stage": "output", "lag_axis": "ew_first"}
```

It reproduces v2.3 record for record (the same `Keep`, `Rem_By`, `Pass_Id`, `Lag_rec`, `Overlap_f` and positions;
checked on T19, T20, T25, T22, T23, T29 and T30 against the untouched v2.3 engine, E0); only the maps are drawn with
the swept strips. The switches can be set one at a time (`docs/METHOD.md` section 12):

| Setting | v2.4 default | v2.3 (`LEGACY_V23`) | What it does |
|---|---|---|---|
| `filters.F8.footprint` | `"swept"` | `"chord"` | the strip between the header lines of consecutive readings, or the rectangle along the chord from the previous point |
| `filters.F8.y_offset` | `true` | `false` | centre the strip `Y_Offset_f` ft to the right of travel |
| `filters.F8.reference` | `"local"` | `"field"` | pass-interior records against local edge-matched no-overlap controls of the same combine, or each combine's whole no-overlap band |
| `filters.F8.min_threshold` | `0.05` | `0` | floor of the automatic threshold (not applied to a fixed threshold or to the fallback) |
| `filters.F8.local_radius_m` | `15` | not used | minimum radius of the local controls; the radius used is max(this, 1.5 header widths) |
| `filters.F8.edge_tol_m` | `4` | not used | largest difference of edge distance between a record and its controls (m) |
| `filters.F8.min_controls` | `5` | not used | fewest controls a record needs to enter the dose-response |
| `lag_stage` | `"output"` | `"output"` | where the flow delay is measured and applied: after the cascade on the output geometry, or `"before_f7"` (the option that failed P5: after F6, every yield tied to its source position before F7 and F8) |
| `lag_axis` | `"dominant"` | `"ew_first"` | the passes the flow-delay scan compares: the direction the field was harvested in, or E-W whenever E and W both hold >= 200 records |

The pass-interior rule (15 records), the 30 matched records per band and the 30 placebo records of the fallback are
constants of the engine, not settings. A settings file or a saved field from before v2.4 holds none of these keys, so
run again it cleans with the v2.4 defaults (the app opens such a field with its result marked as the previous run); the JSON and the report of every v2.4 run say which model was used
(`R["settings"]`, `R["f8"]["footprint"]`, `y_offset`, `reference_mode`, `floor_applied`, `local`, `stop_kind`;
`R["lag"]["stage"]`, `axis`, `n_orphans`).

### Evidence for v2.4

The changes were tested before they were adopted (`docs/overlap_v24/`; `docs/METHOD.md` section 13 has the details).
The pre-registration `PREREG_v24.txt` (SHA-256 in `PREREG_v24.sha256`) fixed the predictions and decision rules before
the v2.4 code existed and before any after-number was computed; each result in `EVALUATION_v24.md` was produced by an
analyst and reproduced by an independent verifier. Intervals are 95 % bootstraps over passes.

| Item | Registered rule | Verdict | Key numbers |
|---|---|---|---|
| E0 | `LEGACY_V23` reproduces the untouched v2.3 engine on every record | **holds** | 0 differences in 7 of 7 trials (re-checked on the final engine) |
| P1 | the swept strip lowers the mean overlap of the records in curves, to within +/- 2 pp of test C | **supported** | falls in 7 of 7 (paired -4.8 to -9.5 pp, every CI excludes 0); inside the band in 6 of 6 (largest distance 0.49 pp) |
| P2 | the records only the wedge removed yield like their pass: CI of yield / own-pass median includes 1 in >= 4 of 7 | **supported, at the minimum** | 4 of 7 (T19 0.989, T22 1.035, T23 1.024, T30 0.974); T20 0.891, T25 0.983, T29 0.902 lie below 1; the wedge was 9-55 % of the v2.3 F8 removals |
| P3 | the decisions that flip when the raster origin moves 0.125 m fall by >= 36 % | **supported** | 38-94 % fewer flips; T23 (37.8 %) is one flip from 36 %, and the other reading of the share would refute P3 |
| P4 | `Y_Offset` lowers the median overlap of the narrowed John Deere records | **supported** | 4 of 4: median 1.8-10.4 % -> 0, share above 5 % 28-59 % -> 7.7-8.8 % |
| P5 | the flow delay applied before F7 and F8 brings the end-of-pass deficit D5e to <= 0.10 on T22, T23 and T25 | **refuted** | 0.126, 0.133, 0.331; the delay stays on the output (`lag_stage` "output") |
| P6 | the placebo of the local controls lies within 0.97-1.03 | **supported** | 7 of 7 point estimates 0.982-1.004 (evaluated engine) and 0.984-1.012 (final engine, re-checked); the CIs of T19, T20 and T30 reach outside |

The evaluated engine had the flow delay before F7 and F8 as its default and its local controls within 15 m on all
records alive after F7, one combine per file. The final engine follows the evaluation's recommendation (section 7 of
`EVALUATION_v24.md`: the flow delay back on the output) and adds what came after it: the pass interiors, the combine
key, the radius of max(15 m, 1.5 header widths) and the dominant-axis scan (an exploratory finding of section 5, not a
registered prediction). Its runs on the same seven SMS exports (default settings, no field of interest; mean = kept
`Yld_Vol_Dr`):

| Trial | Monitor | Records | Kept v2.3 -> v2.4 | Removed | F8 threshold v2.3 -> v2.4 | What set the v2.4 threshold | Placebo (records) | Mean yield v2.3 -> v2.4 (bu/ac) | Flow-delay shift v2.3 -> v2.4 |
|---|---|---|---|---|---|---|---|---|---|
| T19 | Case IH | 33,017 | 22,055 -> 27,112 (+5,057) | 33.2 -> 17.9 % | 5 % -> 5 % | scan stopped at 5-10 %: 15 of 222 records matched | 1.012 (730) | 72.73 -> 72.20 (-0.73 %) | 0 -> 0 |
| T20 | Case IH | 68,891 | 62,724 -> 63,292 (+568) | 9.0 -> 8.1 % | 5 % -> 5 % | scan stopped at 5-10 %: 0 of 496 matched | 0.997 (726) | 53.52 -> 53.44 (-0.16 %) | +2 -> +5 |
| T25 | Case IH | 51,181 | 43,625 -> 44,538 (+913) | 14.8 -> 13.0 % | 10 % -> 5 % | yield drop: 5-10 % band -3.62 % | 1.000 (8,535) | 66.85 -> 66.84 (-0.01 %) | +3 -> +4 |
| T22 | John Deere | 33,947 | 30,877 -> 31,485 (+608) | 9.0 -> 7.3 % | 15 % -> 5 % | floor (auto 2 %; 2-5 %: 8 of 103 matched) | 0.998 (11,453) | 68.48 -> 68.52 (+0.06 %) | +2 -> +2 |
| T23 | John Deere | 82,314 | 56,114 -> 56,516 (+402) | 31.8 -> 31.3 % | 25 % -> 5 % | floor (auto 2 %; 2-5 %: 28 of 252 matched) | 1.000 (14,684) | 54.63 -> 54.69 (+0.11 %) | +2 -> +2 |
| T29 | John Deere | 78,887 | 60,481 -> 65,189 (+4,708) | 23.3 -> 17.4 % | 10 % (fallback; auto 1 %) -> 5 % | floor (auto 2 %; 2-5 % band -12.0 %) | 0.994 (5,155) | 65.92 -> 65.06 (-1.31 %) | -5 -> +2 |
| T30 | John Deere | 27,210 | 22,067 -> 24,459 (+2,392) | 18.9 -> 10.1 % | 5 % -> 5 % | scan stopped at 5-10 %: 19 of 73 matched | 0.984 (6,508) | 59.36 -> 58.66 (-1.19 %) | 0 -> 0 |

Limits, plainly:

- **In-sample.** The predictions came from tests A-C and their reviews on these same seven trials, so P1-P4 check that
  the engine reproduces the earlier analyses; they are not out-of-sample tests. One season, SMS exports only, 3 Case
  IH and 4 John Deere fields.
- **The final configuration was not the one evaluated.** The pass interiors, the combine key, the radius and the
  dominant axis were decided after the pre-registration. Only E0 and P6 were re-checked on the final engine (both
  hold; the final placebo is 0.984-1.012, its CIs on T19, T20 and T30 reaching outside 0.97-1.03); the table above is
  a set of runs, not a registered test.
- **No machine column in any of the files.** The combine comes from the SMS serial (T19, T20, T25: one combine each)
  or the Ops Center log (T23, T29: 4 logs each); T22 and T30 carry neither and run as one combine. **T29 has no time of
  day**, so the burn order between its 4 combines is file order.
- **Thin local controls.** 10-42 % of the dose population found controls (T29 9.6 %, T20 13.8 %). The scan stopped
  because the next band had fewer than 30 matched records in 5 of 7 trials (T19, T20, T22, T23, T30) and on a yield
  drop in 2 (T25, T29); the 5 % floor decided the threshold in 3 of 7 (T22, T23, T29). So in 3 trials (T19, T20, T30)
  the 5 % threshold is set by the 30-record rule and only in T25 by a measured drop; on the evaluated engine every
  deciding band's CI spanned the -3 % tolerance. A 5 % threshold everywhere is the floor and the matched counts
  speaking more than a measured dose-response.
- **The flow-delay shift is fragile.** The dominant-axis rule was chosen after seeing these data; the r-gain > 0.01
  gate is not a meaningful test (the gain is >= 0 by construction and its bootstrap spread is 0.01-0.05). On T29 the
  +2 records become 0 when the raster origin moves by 0.125 m (the evaluation's evidence for T29 points to +1..2 or no
  shift; v2.3's -5 had the wrong sign).
- **No yield ground truth.** The mean kept yield falls 0.7-1.3 % on T19, T29 and T30. In the evaluation the newly kept
  records read like their own pass but lay nearer the edges and in lower-yield passes; whether those edge yields
  are real cannot be settled with these data.

### Field of interest (AOI)

A grower's export often holds more than the field of the trial (another field, the road, the yard). The field of
interest is a pre-step, not a filter: records farther than `aoi.buffer_m` (50 m) from the polygon are set aside
before the cascade and logged as `{"step": "AOI", "criterion": "outside the field of interest + 50 m", "removed":
n}`; the 50 m keep the headland context that the pass structure, the overlap raster, the flow-delay scan and F7 need
(Menegatti & Molin 2004 delete the points outside the field boundary first; Owen et al. 2024 remove out-of-boundary
blocks before automated cleaning; the buffer is a house rule). The DIFM-ready file then keeps only
the kept points inside the field itself (`aoi.clip_output`, 0 m); the flagged file keeps every processed point with
`In_AOI`. A file with more than one polygon is a **trial plan** only when it looks like one (house rule): a rate
column, an explicit `plot` column, a polygon typed headland / border, or at least 4 polygons of similar size (the
largest, the headland excepted, below 5 x the median). Each polygon is then a plot unless its `type` is a headland
type or it is the single untyped polygon (blank type, or no type column) larger than 5 x the median plot;
`Plot_Id` and `Tgt_Rate` are added, the F8 dose-response is measured on the in-plot records only (the review's
interior figure, section 4.9) and the combine pairs compare the same plot. Otherwise the file holds **several field
boundaries** (three quarters of one farm: 93, 121 and 135 ac, a `Field` column): the run refuses to union them and
asks for the field of interest (`aoi.feature` = 1-based polygon index; CLI `--aoi-feature N`; the app shows a
selector with the names and areas), and no `Plot_Id` is ever written from a boundary file. The level reports the
integral of the processed set (the ticket's denominator) and the integral inside the field (0 m), and **warns when the
records set aside carry more than 5 % of the grain** (also with per-combine tickets): a field total of the whole export
must not be divided by the integral of the trial area (Trial 29: the field total over the design area + 50 m gives L 1.77;
over the whole file 1.007). Settings: `aoi = {file, buffer_m 50, clip_output true, id_col, rate_col, headland_types
["headland", "border"], feature}`; `buffer_m: null` = diagnostic only (the old `boundary` key, which never tags plots
whatever the number of polygons).

### Harvest sessions and the moisture basis

Monitors map a *dry* yield from the wet flow and the moisture sensor; SMS and the three raw formats shrink
**one-sided** (readings below the standard moisture are not raised), so a field harvested drier than the standard is
mapped at its wet yield while the wetter part is shrunk, and two days of harvest at different moistures are not on
the same basis. The run finds the standard moisture Ms (settings > decoder report > inferred from the export where
dry / wet < 0.999 on >= 200 records > crop table) and the shrink convention (one-sided when dry == wet on >= 95 % of
the records below Ms), writes `Yld_Dry_Sy` = wet yield x (100 - M) / (100 - Ms) (the symmetric dry-matter basis),
splits the harvest into **sessions** = machine x calendar day (the dataset when the records carry no time of day,
its day from the SMS or Ops Center task name or the date-only time column; records a decoder reports as UTC take the
local day), and reports per session the readings, kept points, area, wet bushels, moisture (mean, SD,
`share_below_standard_kept` = share of the KEPT readings below Ms; `R["moisture"]["share_below_standard"]` is the
share over every processed record) and the mean yield on the three bases, plus the field mean of mass per area over every
processed reading (which is not the cleaned-map mean). Consecutive sessions of one machine are compared on paired
30 m cells between adjacent passes (same plot / rate with a design): yield ratio with a block-bootstrap CI and
moisture difference, **diagnostic only**. Recommendation (house rule): sessions differing by > 2 moisture points, or
> 20 % of the readings below Ms under one-sided shrink -> "map `Yld_Dry_Sy` as the yield in DIFM and keep `Harv_Day`
as a block". Figure `fig_clean_sessions.png`. Settings: `moisture = {standard_pct, shrink auto|one_sided|symmetric,
add_symmetric_column true}`. Trial 19: Ms 14.5 % inferred from 2,419 records, one-sided (dry == wet on 100 % of the
29,407 records below Ms), 90.7 % of the readings below Ms, 4 sessions on 20-21 Sep -> `Yld_Dry_Sy` recommended.

### Several combines

The reference is the combine with the most kept points (`machines.reference`, or an id; a reference whose records
the cascade removed falls back to it with a warning). Every other combine is compared with it on 30 m and 50 m cells
with >= 5 kept points of both **with <= 2 % of the footprint already cut** (`machines.pair_max_overlap`; same plot
when a design exists): f = exp(mean(log(ref / m))), CI by block bootstrap over pass pairs (1,000 reps, seed 2026).
The overlap rule matters: the pass that follows another carries the overlap below the F8 threshold and its kept
records read 2-3 % low, so pairing every kept record of two combines working side by side measures the overlap, not
the machines (Trial 19 with alternate passes labelled A / B and no yield change: factor 1.029 "applied" with every
record, 1.009 and not applied with the rule). The 30 m factor is **applied** (column `Yld_Harm`) only when there are
>= 30 cells and >= 5 pass pairs at both sizes, both 95 % CIs exclude 1, the two factors agree within 2 % and 1 % <
|f - 1| <= 10 %; above 10 % nothing is applied and the run asks for per-machine weights. The paired t-test p and the
moisture difference on the same pairs are diagnostics. With **per-combine weighed totals** (`machines.totals_bu`, CLI
`--machine-total VIN=BU`; applied whenever they are given, with or without the relative harmonisation and also for a
single combine), L_m = ticket_m / wet integral_m, `Yld_Level` = y x L_m and `Yld_Harm` = y x L_m / L_ref; the paired
estimate is then a validation (agreement = (L_m / L_ref) / f_paired - 1) **only where it passes its own pair gate**,
otherwise the run says "no paired estimate: too few pairs" instead of a false disagreement; a combine without a ticket
is leveled with the reference's L, the level's ticket is the implied field total and a `scale_ticket_bu` given beside
the tickets is compared with it (warning above 1 %). The factors are applied to the non-reference combines: on Trial
29 the reference is combine A (most kept points) and a 5-6 % higher reading on it appears as x 1.04-1.06 on combine B, never
as a factor below 1 on combine A. Means per combine (area, wet bu, mass per area, moisture, cleaned-map mean) are reported
with the tests, with the share of each combine's kept records left out by the overlap rule. Settings: `machines =
{harmonise true, reference "auto", totals_bu, min_pairs 30, min_pass_pairs 5, ci 0.95, min_factor 0.01, max_factor
0.10, same_plot_only true, bootstrap_reps 1000, seed 2026, pair_max_overlap 0.02}`. On a seed-rate trial the gate is
underpowered without the design (adjacent passes carry different rates): give the design.

### Grower's weight as the real level

The grower knows what the field weighed; the monitor does not. When the grower sends the total weight of the field
(the 5-combine barley field: W lb on the scale), enter it as it is written, with its unit (`scale_ticket = {value,
unit lb | kg | bu | t, basis wet | dry, moisture_pct, note}`; CLI `--scale-ticket 1500000 --ticket-unit lb`; the
legacy `scale_ticket_bu` / `--scale-ticket-bu` stay as the alias in bushels and take no unit or moisture: the CLI
refuses `--scale-ticket-bu` with `--ticket-unit` / `--ticket-moisture` instead of taking kilograms for bushels). A
kg / t ticket keeps its decimals in every caption (184.1975 t, not "184 t"). The run converts it to bushels with the
test weight (`test_weight_lb_bu` if given, else the file's own median `Yld_Mass_W / Yld_Vol_We`, else the crop table;
no test weight at all is an error that names `test_weight_lb_bu`, raised before the cascade runs): W lb /
47.99 lb/bu = V bu. **What L does.** `L = weight / monitor total`, the monitor total being the integral of
yield x swept area over every processed record on the same basis as the ticket (wet: the wet volume column; dry: the
mapped dry column; a ticket with its moisture on the wet basis is brought to the standard moisture, symmetric, and
compared with the `Yld_Dry_Sy` integral - every caption then shows that figure as the scale, "monitor 7,749 bu vs
scale S bu (+12.4 %; the ticket at 12 % = S bu at 14.5 %)", the same L divides by; a ticket moisture on the
dry basis is refused, since a dry-basis weight is already at the standard moisture). The 5-combine field: V / M bu,
L = 0.9481 (the monitor read 5.5 % high). **The file keeps the monitor's values** and adds the leveled columns
`Yld_Level` (mapped dry yield x combine factor x L) and `Yld_Lvl_Sy` (`Yld_Dry_Sy` x factor x L, only when
`Yld_Dry_Sy` itself is written: `moisture.add_symmetric_column`); the leveled column is the one to map in DIFM
(`Yld_Lvl_Sy` when the sessions recommend the symmetric basis and it exists, else `Yld_Level`): its bu/ac now sum to
the scale on the comparison basis (the JSON also gives the integral of the written `Yld_Level` itself,
`yld_level_integral_bu`, which differs from the ticket by the one-sided-shrink gap between the mapped dry and the wet
column: 0.007 % on the 5-combine field). The pattern, the cleaning and the ranking of the treatments do not change; the economics
do. **The closure and its verdict.** The run reports the monitor total against the weight before and after the
combine harmonisation (the "after" figures only when a factor changed the total) and bands the verdict on |L - 1|,
the same quantity the *Worth checking* advice uses: <= 1 % a small level correction, 1-3 % the agreement expected
after a field calibration, 3-10 % "the yield monitor's calibration should be checked", > 10 % "check the ticket
coverage before trusting L". Both percentages are named with their direction: Trial 19 reads "the monitor total is
-9.9 % from the grower's weight (L = 1.1099 is +11.0 % from 1, > 10 %)". The level the app and the report show first
is the one applied to the columns (1.0007 on the 5-combine field, "before the combine harmonisation 0.9481"). With per-combine
tickets the verdict bands the field-level gap (sum of the tickets / integral) and says that each combine is leveled
to its own ticket. **The closure test for combines.** A proven paired factor above `machines.max_factor`
(10 %) is normally reported, not applied. With a grower's weight the run computes the monitor total with that factor
applied: when it closes with the weight within `machines.ticket_close_tol` (1 %) while the unharmonised total is
more than 3 x that away, the weight confirms the factor and it is applied ("applied: the paired factor is above
max_factor but the grower's weight confirms it (harmonised total within 0.07 % of the scale)"; switch
`machines.ticket_confirms`). A factor above the gate whose CI includes 1 at one cell size or whose 30 m / 50 m
estimates disagree is not a candidate: the decision and the ticket test both say so ("candidate A rejected: the 30 m
and 50 m factors disagree (1.2135 vs 1.2803)"), and when the weight sits nearer that combine's level than the
reference's the test suggests `machines.reference = A`. The 5-combine field: combine E read 27.8 % high (factor 0.7825,
CI 0.762-0.803, 396 cells), beyond the 10 % gate; with the factor the harmonised total is V' bu, 0.07 % from
the scale, so the factor is applied and the final L is 1.0007; the other four combines (CIs including 1) are
unchanged. The app shows the test in the Combines tab (totals without / with the factor against the scale) and the
report in its Level section.
**When NOT to trust L**: the ticket covers several fields or only part of this one (check the coverage before
believing a |L - 1| above 10 %: the run says so); the weight includes dockage or is net of it while the monitor is
not; the ticket is on another moisture basis than the comparison (a dry-basis weight against the wet integral);
loads were lost, double-counted or weighed on another scale; the field of interest set aside records that the ticket
weighed (the run warns when they carry more than 5 % of the grain).

## Validation of the whole chain

`tools/validate_app_e2e.py` runs the four reference inputs with the default settings and writes
`docs/app_e2e_validation.json` (v2.0 numbers, asserted by `tests/test_run.py`). The v2.1 inputs below were run with
`python -m engine.run` on 2026-10-23 (the per-field numbers of Trial 19 are asserted by
`tests/test_aoi_sessions_machines.py` and `tests/test_app_aoi.py`). All the numbers of this section are those of the
v2.3 overlap and flow-delay model, which `LEGACY_V23` reproduces record for record; with the v2.4 defaults the F8
threshold, the flow-delay shift and the kept counts change (the 2 % of (c), for one, is below the v2.4 floor of 5 %).

| Input | Field of interest | Decoded / in | Processed -> kept (DIFM file) | F8 | Column for DIFM |
|---|---|---|---|---|---|
| (a) Trial 19 SMS export, defaults, no field file (regression) | - | 33,017 | 33,017 -> 22,055 | auto 5 % | `Yld_Vol_Dr`; with the grower's ticket L 1.1099, `.dbf` md5 `1181f19cc6b5b921c8bce0b298f43de9` |
| (a') the same with the 83-polygon seed design (82 plots + headland, `tgt_seed` 90/100/110/130) and the grower's ticket | 592 records set aside (one whole task, 50-302 m outside) | 33,017 | 32,425 -> 26,694 (26,679: 15 kept points outside the field left out) | auto 10 % on the 17,453 in-plot records | `Yld_Dry_Sy` (Ms 14.5 %, 91 % below, one-sided), L 1.1287 (7,495.2 bu processed set; 7,491.8 bu inside the field) |
| (b) Trial 19 Case IH card with the field A boundary, no `--field` | the boundary selects the 4 field A 2026 tasks (I5-I8, 100 % inside; I1 0 %) | 33,693 | 33,693 -> 21,776 (35.4 % removed; 0 set aside) | auto 5 % | `Yld_Dry_Sy` (90 % below 14.5 %); 3 decoder warnings (calibration of tasks I5 / I6) |
| (c) Trial 29 John Deere `.jdl`, 4 X9, with the 152-polygon design (151 plots + border, `Tgt_Rate_l` 90-200) and the field total | 34,620 of 79,984 readings set aside (the design covers 272.8 of 451.6 ac) | 79,984 | 45,364 -> 13,719 (69.8 % removed; flagged by the app) | auto 2 % on the 23,149 in-plot records: combine combine B is already -7.6 % in the 2-5 % band | `Yld_Dry_Sy` (78 % below 13.5 %); no combine factor (too few pairs at 2 %); **warning**: L 1.7669 over the design area vs 1.0072 over the whole file -> the field total belongs to the whole export |
| (c') the same with F8 fixed at 10 % | as (c) | 79,984 | 45,364 -> 34,674 (34,000 in the DIFM file) | 10 % | means (bu/ac wet mass per area / cleaned map): combine A 64.1 / 67.8 (reference, 11,022 kept points), combine C 62.8 / 65.6, combine B 58.7 / 64.2, combine D 59.1 / 61.9. Paired factors ref/m on the <= 2 % overlap records: combine B 1.043 at 30 m (CI 0.972-1.128, 86 cells / 14 pass pairs) and 1.055 at 50 m (CI 1.006-1.096, 151 cells) -> not applied (30 m CI includes 1); combine C 26 cells at 30 m -> too few pairs (1.076; 50 m 1.100 on 102 cells); combine D too few pairs. `Yld_Dry_Sy` |
| (c'') + `--machine-total COMBINE_A=4970 --machine-total COMBINE_B=4980` (synthetic) | as (c) | 79,984 | 34,674 | 10 % | L_A 1.0098, L_B 1.0700, L_m / L_ref 1.0596 vs paired 1.043 (inside its CI, agreement +1.6 %); combine C / combine D without a ticket take the reference's L and read "no paired estimate: too few pairs" (no disagreement is claimed from an ungated estimate). Implied field total 16,088.7 bu, mean L 1.0277, with the set-aside warning (the records outside the design carry 11,806 bu). `Yld_Harm` (wins over `Yld_Dry_Sy`) |
| (d) GreenStar 3 canola, `--crop canola`, with the farm's 3-field boundary file | without `--aoi-feature` the run refuses ("3 field boundaries, not a trial plan: 1 = Centre 93.2 ac; 2 = East 121.1 ac; 3 = SouthWheat 135.3 ac"); with `--aoi-feature 2` the East quarter alone selects one unit (the other field 0 % inside) | 9,576 | 9,576 -> 4,948 (48.3 %; 0 set aside) | auto 5 % | F1 4-16 % removes 0 (moisture 6.9 %; the 8-20 % cereal window removes 8,321 of 8,807 when no crop is set, and the app now warns before the run). No `Plot_Id` from a boundary file. `Yld_Dry_Sy` (Ms 10 %, 99 % below) |

Reports: 8-10 pages (the references section lists the 60-70 works of the steps that ran). Where the house defaults
do not fit the user must decide (the app flags both under *Worth checking*): (c) the 2 % threshold is what the
v2.3 within-combine dose-response gives when one combine reads low as soon as it overlaps (v2.4 would not go below
5 %); check the swath widths and
header offsets of the combines (`docs/formats/jd_jdl.md`, section 8) before accepting it, or set a manual threshold
as the delivered Trial 29 cleaning did (10 %). The 8.7 % drop of the 0-2 % band seen in v2.0 on all records (fallback
10 %) disappears on the in-plot population, as the review predicts for headland-free ground.

## Limitations by input

- **All raw formats:** each decoder was reverse-engineered and validated on one set of machines (see
  `docs/FORMATS.md`); other machines, display software or crops may differ. The level (scale ticket) is applied in the
  cleaning, never in the decoder.
- **Case IH / New Holland `.cn1`:** validated against SMS on barley (crop 17) of one combine; other crops only against
  the display's own task totals (124 of 132 tasks within 2 %). Crop names other than crop 17 are guesses. A task
  recalibrated after harvest is decoded with its own stored curve, as SMS does (option *Calibration curve*: the
  crop's latest). `Time` is the display clock (local time).
- **John Deere `.jdl`:** timing lags and the 13.5 % wheat standard moisture (Ops Center's) were measured on one harvest
  of four X9 1100; other crops use the monitor's crop record. No GNSS fix-quality filter beyond a 50 km outlier rule.
  Readings below 5 bu/ac, which Ops Center drops, are kept for the cleaning to judge. Time is UTC (the session day is
  the local day). Units are split by season (one JD-Data tree can hold several years); a gap of up to 10 s in the
  moisture channel holds the last value, as Ops Center does.
- **John Deere GreenStar 3:** one display and one S680 combine; the 14 s grain-flow and 18 s moisture delays reproduce
  the SMS processing of those logs (editable in step 2). The receiver-to-header offset is whatever was entered on the
  display. Without the `.fdr` files the loads are named by GUID. Time is UTC. The monitor's crop profile is used unless
  a crop is chosen: the wheat logs of one field carry "Canola P1530 G" (52.01 lb/bu, 10 %) with a median moisture of
  14.3 %; the decoder warns when a unit's median moisture is more than 2 points above the profile's standard.
- **Exports:** the `.prj` is required; a `Time` without time of day falls back to dataset start + record id (sessions
  are then per dataset); an Ops Center export with several combines in one task and no machine column cannot be
  harmonised (a warning says so).
- **Field of interest:** the plan / fields decision is a heuristic (rate or plot column, typed headland, or >= 4
  polygons of similar size); a design of 2-3 plots without a rate column reads as fields (give the rate column or
  `aoi.id_col`), and a farm boundary file of >= 4 similar quarters without a name or rate column would read as a plan
  (choose the field with `--aoi-feature` to override). The unit pre-selection on raw data decodes every latest-season
  unit once with the decoder's default options (cached under `decoded/aoi_cache/`); the Trial 19 card's 32 units take
  28 s.
- **Sessions / combines:** the discontinuity check needs >= 10 paired 30 m cells and >= 3 pass pairs between adjacent
  passes of the two sessions; small tasks that are not adjacent report "too few adjacent cells". The combine gate
  needs >= 30 cells and >= 5 pass pairs of records with <= 2 % overlap, so it is harder to reach than with every kept
  record (Trial 19 pseudo-machines: 40 cells instead of 200; Trial 29 combine C: 26 cells at 30 m, too few); on a trial
  it needs the design (same-plot pairs). The v2.3 F8 reference (the v2.4 fallback) needs >= 500 no-overlap points
  per combine (or 10 % of the combine's records); a combine below that is reported but left out of the pooled curve.
- **Overlap (F8) and flow delay:** the local reference needs >= 30 no-overlap records of the pass interiors with >= 5
  controls each, and the edge distance is that of the processed set (the outer limit of the 50 m buffer counts as an
  edge). The local controls are thin: on the seven trials of the evaluation only 10-42 % of the dose population found
  controls, the scan stopped for lack of matched records in 5 of 7 trials and the 5 % floor set the threshold in 3 of
  7 (section *Evidence for v2.4*), so read `stop_kind` and the matched counts before trusting a threshold. Without a
  machine column the combine comes from the SMS serial or the Ops Center log; an export with neither is one combine.
  The overlap is measured on a 0.25 m raster, so single decisions near a threshold of 5-10 % still depend on the
  raster; the overlap over ground cut in another session is not flagged as low confidence; the harvest order of an SMS
  export is inferred (no time of day). The `Y_Offset` placement was confirmed on the geometry (P4) but not yet on
  yield. The dominant-axis flow-delay scan was chosen after seeing the evaluation's data and is not pre-registered; on
  Trial 29 its +2 records become 0 when the raster origin moves by 0.125 m (fragile; v2.3 applied -5, the opposite
  sign to the crop-edge timing): check the lag figure of a field by hand when the shift matters.

## Files

```
app/app.py                       the Streamlit page
app/brand.py                     the OCCD brand: name, version, palette, logos, page icon, the page's small CSS
assets/brand/                    the Olds College logos and BRAND.md (the palette and where it is used)
engine/fields.py                 saved fields: field.json of every run (list / load / save / rename / delete)
engine/run.py                    the single API (open_input, list_units, decode, clean, read_plan,
                                 units_inside_aoi, recommended_yield_column, ticket_conversion) and the CLI
engine/formats/detect.py         unpack (zip guards) and detection; DECODERS registry
engine/formats/common.py         decoder contract, standard schema, CROPS table
engine/formats/cnh_cn1.py, jd_jdl.py, jd_gs3_rcd.py   the raw decoders
engine/clean/yield_clean.py      the cleaning (settings and LEGACY_V23, cascade, swept strips, lag, level, outputs)
engine/clean/aoi.py              field of interest / trial plan reader, point-in-polygon, plot tagging
engine/clean/sessions.py         standard moisture, shrink, Yld_Dry_Sy, sessions, discontinuity check
engine/clean/machines.py         paired cells, bootstrap factor, per-machine tickets and their validation
engine/clean/references.py       REFERENCES / SOURCES / cite(step) from docs/literature/references_verified.csv
engine/clean/sms3sigma.py        the SMS 3-sigma method (steps S0-S5, grouping, limits)
engine/clean/sms_swath.py        the emulation of SMS Optimize Swath Widths (reverse-engineered)
engine/clean/compare.py          both methods on the same readings and their comparison
engine/report/clean_report.py    the PDF report (both methods)
engine/report/compare_report.py  the PDF of the comparison
docs/METHOD.md                   the cleaning standard;  docs/FORMATS.md  the raw formats
docs/REFERENCES.md               what each cited work supports, per step (tools/build_references.py)
docs/overlap_v24/                the evidence for v2.4: pre-registration (+ SHA-256), evaluation report, synthesis of
                                 the overlap tests A-C (Portuguese) and the key figures; README.md is the index
docs/method_check/               "OCCD, the evidence behind each step": the literature check of every step, PDF in English
                                 (OCCD_method_and_references.pdf) and Portuguese (OCCD_metodo_e_referencias.pdf),
                                 written for v2.3.0 (the v2.4 changes are in docs/METHOD.md);
                                 python docs/method_check/assemble.py rebuilds both from sections/ and sections_pt/
docs/literature/                 the literature review and the verified reference list (finished deliverable)
docs/app_e2e_validation.json     end-to-end numbers of v2.0 (tools/validate_app_e2e.py)
tools/validate_*.py              validation scripts;  tests/  pytest suite (python -m pytest -q; -m "not slow")
examples/trial19_sms/            Trial 19 SMS export, boundary, seed trial design and the v1 reference .dbf
examples/decoded/                one decoded sample per raw format
examples/multi_combine/          the 5-combine barley field (5 combines, 130,847 readings): the grower's-weight reference
                                 (W lb; tests/test_ticket.py, tests/test_app_ticket.py)
_archive/v1_difm_analysis/       the previous version (DIFM chain in R, covariates, extended analysis, v1 app)
_archive/v2.3.0_before_v2.4/     the way back to 2.3.0 (LEIA-ME.txt, files\, manifest.json, the 2.3.0 package)
```

## The previous version

Version 2.3.0, as it was before v2.4, is kept in `_archive/v2.3.0_before_v2.4/`: the 21 files v2.4 replaced (`files/`),
`manifest.json` (their md5 and the 20 files v2.4 added) and the full 2.3.0 install package; `LEIA-ME.txt` (Portuguese)
says how to go back (close the app first) and how to repeat a v2.3 cleaning in v2.4 without going back.

Version 1 (the DIFM chain reproduced in R, raw vs cleaned runs, covariates, extended analysis and the long trial
report) is kept unchanged in `_archive/v1_difm_analysis/` with the same relative paths: `app/app.py`,
`app/app_prototype.py`, `engine/pipeline.py`, `engine/difm_r/`, `engine/covariates/`, `engine/cnh/`,
`engine/report/make_report.py`, `engine/clean/difm_ready_clean.py`, `run_example.bat`, its `README.md`,
`docs/SPEC.md`, `docs/DIFM_*.txt`, `docs/ofe_*.R` and `examples/trial19/`. Its tests (`tests/test_clean.py`,
`tests/test_covariates.py`, `tests/test_pipeline_smoke.py`, `tests/rchain`, `tests/mock_output`) are still in
`tests/` and are excluded in `pytest.ini`; they will move to the archive once the old tests folder has been copied
back from Google Drive. To run v1, copy the archive folder out and run it from there (its paths are relative to its
own root).
