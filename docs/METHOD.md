# OCCD — Olds College Cleaning Data: the DIFM-ready cleaning standard

Olds College Smart Farm, on-farm precision experimentation (OFPE). This is the standard that OCCD
applies to every trial before the data goes to the DIFM platform. The code that implements it is
`engine/clean/yield_clean.py` with `aoi.py`, `sessions.py`, `machines.py` and `references.py` (the SMS 3-sigma
method of section 10: `sms3sigma.py`, `sms_swath.py`, `compare.py`); the numbers of a
trial are in its `<tag>_cleaning.json` and its report. Every literature source named here is in
`docs/literature/references_verified.csv`; what each supports is in `docs/REFERENCES.md` (built from
`engine/clean/references.py`). Numbers that are house conventions are labelled "house rule".

Version 2.4 (29 October 2026) changed the overlap filter F8, the flow-delay scan and the maps after the house's
pre-registered overlap tests A, B and C, their reviews and a pre-registered before/after evaluation (section 13): the
F8 footprint is the strip the header swept between two readings, placed `Y_Offset` to the right of travel; the
dose-response compares every record of the pass interiors with local no-overlap controls of the same combine at the
same distance from the harvested edge, and the automatic threshold never goes below 5 %; the flow-delay scan compares
the passes of the direction the field was harvested in and, as in v2.3, moves the output geometry only (applying the
delay before F7 and F8 failed its pre-registered test and stays an option); the maps draw the swept strips (sections
3, 3.1, 4 and 8). A cleaning delivered before v2.4 is reproduced with the settings of section 12. The evidence is in
`docs/overlap_v24/`.

## 1. Principles

1. **Clean the file that goes to DIFM.** Work on the yield export that is uploaded (Ag Leader SMS or John Deere
   Operations Center points), or on the raw monitor readings decoded into the same schema. Never recompute yield
   from a raw card when the export exists. The cleaning only **removes points**, **moves geometry** when a residual
   flow delay is proven, and **adds columns**. Every original column and value is kept, so the DIFM column mapping is
   identical with and without cleaning, and two DIFM runs differ only by the cleaning.
2. **Only the field of interest.** The grower's export often holds several fields; the cleaning works on the field
   of the trial (section 2) and the DIFM file holds only its points.
3. **Thresholds are measured on the field.** The overlap threshold comes from the field's own dose-response, on the
   interior (in-plot) ground when a design is given, against local no-overlap controls at the same distance from the
   harvested edge and never below the 5 % resolution of the overlap measure; the 30 % convention is never used.
4. **Shift for flow delay only when it is proven** (section 4), and move the output geometry only: F7 and F8 judge
   each yield at its logged position (tying the yields to their source positions before F7 and F8 failed its
   pre-registered test).
5. **Sessions and the moisture basis are diagnosed, never corrected** (section 5): the run says on which basis the
   yield should be mapped and which column is the block.
6. **Several combines are harmonised only when the difference is proven** (section 6); the factor goes to a new
   column `Yld_Harm`, which is then the column to map in DIFM (DIFM has no machine term). Per-combine weighed totals
   replace the paired estimate when they exist; the paired estimate then validates them.
7. **Level.** When the grower's weight (scale or cart total, in lb / kg / bu / t) exists, `L = weight / monitor
   total of the processed set` and the leveled columns `Yld_Level = mapped dry yield x factor x L` and `Yld_Lvl_Sy =
   Yld_Dry_Sy x factor x L` are written; the leveled column is then the one to map in DIFM. The total must belong to
   the processed set (section 7). The file keeps the monitor's columns, so both levels stay available.
8. **Rates.** Map the **applied** rate column (SMS: `Rt_Apd_Ms_`), not the target column (`Tgt_Rate_l`); the
   target hides the ramps of the metering system between plots. `Tgt_Rate` from the design is added to the yield file
   to check the design against the harvest, not to replace the as-applied file.
9. **Two-factor trials.** The platform fits one causal forest per input with field covariates only. When the design
   correlates the inputs this is confounded, so every two-factor trial is also analysed in `cross` mode and with a
   plot-level model with cluster-bootstrap confidence intervals and an interaction test (v1 analysis chain).
10. **Covariates are optional** (platform rule: present on >= 90 % of the observation units and not constant).

## 2. Field of interest (pre-step)

The field of interest (AOI) is a polygon file (`.shp`, `.geojson`, `.gpkg`, `.kml`, `.kmz`, any CRS): a boundary
(one polygon, or several boundaries whose union is the AOI) or the trial design (one polygon per plot plus the
headland / border polygon). It is a **pre-step, not a filter**:

- Records farther than 50 m from the AOI are set aside before the cascade and logged as
  `{"step": "AOI", "criterion": "outside the field of interest + 50 m", "removed": n}`. The 50 m buffer keeps the
  headland context that the pass structure, the overlap raster, the flow-delay scan and F7 need (Menegatti & Molin
  2004 delete the points outside the field boundary first, 0.1-7.8 % in 5 of the 6 monitors, none on GreenStar; Owen
  et al. 2024: out-of-boundary blocks bias every automatically computed filter value; the buffer width is a house
  rule). The cascade's 100 % is the processed set (`n_in`); the file's record count is `n_read`. The edge distance of
  the F8 controls (section 3) is measured on the processed set, so the outer limit of the buffer counts as an edge;
  the controls are matched on that same distance, and with a trial design the in-plot dose population lies at least
  50 m inside it.
- The DIFM-ready file keeps only the kept points inside the AOI itself (0 m); the flagged file keeps every processed
  point with `In_AOI` (1 inside, 0 in the buffer).
- A file with more than one polygon is a trial plan **only when it looks like one** (house rule, `aoi.is_plan_like`):
  a rate column (first column starting with `tgt` / `Tgt`, or `rate` / `Rate_l` / `Tgt_Rate_l`), an explicit `plot` /
  `Plot_Id` column, a polygon typed headland / border, or at least 4 polygons of similar size (the largest, the
  headland excepted, below 5 x the median). Each polygon is then a plot unless its `type` / `Type` is a headland
  type (`headland`, `border`) or it is the single polygon without a type (blank, null or no type column) larger than
  5 x the median area of the others (a design exported with the plots typed and the border left blank; a warning
  says the border was taken by area). The plot id comes from `plot` / `Plot_Id` / `id` / `Obj__Id` (else the row
  number 1..n). `Plot_Id` (C 16) and `Tgt_Rate` (N 12.3) are added by point-in-polygon (empty outside the plots). The
  F8 dose-response is then measured on the in-plot records only (section 3; Edge et al. 2024: DIFM drops the
  design's headland polygon and analyses 12-20 m units of pass within one rate) and the combine pairs compare the
  same plot.
- Otherwise the polygons are **several field boundaries** (a farm's boundary file: three quarters of one farm of 93,
  121 and 135 ac with a `Field` column). The run does not union them: it lists the polygons (index, name, area) and
  needs the field of interest (`aoi.feature`, 1-based; CLI `--aoi-feature N`; a selector in the app) before it runs
  on that polygon alone. No `Plot_Id` is written from a boundary file. A field drawn in several parts is one
  MultiPolygon feature and needs no choice. The old `boundary` setting never tags plots, whatever the file holds.
- The level reports the integral of the processed set (the ticket's denominator) and the integral inside the AOI
  (0 m); when the records set aside carry more than 5 % of the grain of the processed set, a warning gives the L the
  whole file would imply (section 7).

The old `boundary` setting (level diagnostics inside a polygon, nothing dropped or clipped) is kept as
`aoi.buffer_m = null, clip_output = false`.

Trial 19 (SMS export, 33,017 points) with the field A boundary: one whole task (592 records, 8.7 % moisture) lies
50-302 m outside the field and is set aside; the 29 records within 0-50 m all fall to the cascade, so the output clip
removes none. With the 83-polygon seed design (82 plots + 1 headland, `tgt_seed` 90 / 100 / 110 / 130): 17,791
records inside the plots, 26,694 kept, 26,679 in the DIFM file; the same design with the headland's `type` left blank
gives the same result (area rule, warning). GreenStar 3 canola with the farm's 3-field boundary file: refused
until `--aoi-feature 2` names the East quarter, which then selects the one unit inside it (9,576 readings, 4,948
kept, F8 5 %); the earlier behaviour read the file as 3 "plots" and decoded the two canola fields into one file. Trial 29 (four X9, 79,984 decoded readings) with the
152-polygon design (151 plots + border): 34,620 readings set aside (the design covers 272.8 of the 451.6 ac of the
section), 45,364 processed. On raw monitor data the AOI also chooses the units: every latest-season unit with >= 20 %
of its readings inside the AOI + 50 m (Trial 19 card: the four field A tasks at 100 %; the task logged under field A
but 63 m outside the boundary at 0 %).

## 3. The cascade

Points are put in chronological order (per-record time when the time column has a time of day; otherwise the task
start time in the dataset name, then the record id) and split into passes (a new pass at a task, log or machine
change, a jump of more than 15 m, or a heading change of more than 60 deg). The filters run in this order; each point
is counted once, by the first filter that removes it. The residual flow-delay scan (section 4) runs after the
cascade (`lag_stage` "output", the default, as in v2.3; the `"before_f7"` option runs it between F6 and F7). The
sources are the works of `references.cite(step)` (at most three per step: the ones that give the method, the
parameter or the key evidence); what each work gives is under every filter in the app and in `docs/REFERENCES.md`.

| Filter | Removes a point when | Sources |
|---|---|---|
| F0 | yield missing or zero, distance zero, or no / implausible position (none, (0,0), outside lon/lat ranges, > 50 km from the median position) | Menegatti & Molin 2004; Menegatti & Molin 2003; Alves et al. 2026; position checks: house rule |
| F1 | grain moisture outside the crop window or missing: barley / wheat / durum / oats / rye 8-20 %, canola / flax 4-16 %, peas 8-24 %, lentils 8-22 %, corn 10-33 %, soybeans 8-25 %; no crop -> 8-20 % with a note (an unknown crop name: a warning) | Luck & Fulton 2014; Menegatti & Molin 2003; crop windows other than corn 10-33 %: house rule |
| F2 | speed outside 1.5-6.5 mph | Sudduth & Drummond 2007; Luck et al. 2015; Griffin et al. 2008; 1.5-6.5 mph window: house rule |
| F3 | speed changes by more than 20 % per second | Sudduth & Drummond 2007; Griffin et al. 2008; Luck et al. 2015; SMV ratio per second and over the current speed: house form |
| F4 | the GNSS step differs from the logged distance by more than 50 % | Lyle et al. 2014; Damiano & Niemi 2022; Menegatti & Molin 2003; GNSS step vs logged distance test and its 50 % tolerance: house method |
| F5 | the pass has fewer than 10 surviving points | Ping & Dobermann 2005; Clarke et al. 2024; Arslan & Colvin 2002a; 10 points per pass: house value within the published 3-12 points |
| F6 | heading changes by more than 30 deg per second | Clarke et al. 2024; Drummond et al. 1999; Marchant et al. 2019; 30 deg/s removal and the 60 deg and 15 m pass breaks: house values |
| F7 | it is one of the first 4 or last 2 points of a pass (flow fill and empty-out); with the `lag_stage` "before_f7" option also when its flow-delay source lies beyond its pass (section 4) | Sudduth & Drummond 2007; Griffin et al. 2008; Simbahan et al. 2004; first 4 / last 2 surviving records, one setting for all fields: house values, inside the 3-8 s / 2-4 s of the cited works |
| F8 | more than the **measured** share of its swept strip was already cut (overlap) | Drummond et al. 1999; Han et al. 1997; Alves et al. 2026; dose-response threshold: house method - no paper derives an overlap threshold from yield |
| F9 | wet mass yield outside 500-10,000 lb/ac | Arizo-García et al. 2026; Ping & Dobermann 2005; Menegatti & Molin 2003; 500-10,000 lb/ac wet for every crop: house window |
| F10 | yield outside the mean +/- 3 SD of the surviving points | dos Santos & Miguez 2025; Sudduth & Drummond 2007; Ping & Dobermann 2005; all combines pooled in one mean and SD: house rule |
| F11 | yield more than 30 % from the median of its +/-10 in-pass neighbours | Maldaner & Molin 2020; da Silva et al. 2024; Lyle et al. 2014; +/- 10 records window and a minimum of 6 surviving records in it: house values |
| F5b | the surviving run it belongs to has fewer than 10 points | Ping & Dobermann 2005; Clarke et al. 2024; Marchant et al. 2019; 10-record minimum re-applied to runs broken by any removal: house extension |

A removal share of 10-50 % is expected for a monitor export; above 60 % the app flags the run.

**F8 footprint.** Every reading's footprint is the strip its header swept since the previous reading of the same
pass (`yield_clean.swept_strips`, `filters.F8.footprint = "swept"`): the quadrilateral between the header line at the
previous reading and the header line at this one. Each line lies across the direction of travel at its reading (the
centred chord of the positions, `travel_direction`; one-sided at the ends of a sequence; the logged heading only where
no step is usable, because the John Deere Track is a smoothed heading), spans the reading's logged width and is
centred `Y_Offset_f` ft to the right of travel when the file has that column (`filters.F8.y_offset`, as SMS places a
reading; John Deere logs the offset of the active sections of a narrowed header, Case IH logs about 0). Consecutive
strips share an edge, so a reading never counts its own predecessor as overlap. A reading without a usable step from
its predecessor (the first of a pass, a step of 0, or a step longer than 3 x Distance + 1 m) gets the v2.3 footprint,
a rectangle Distance back along the travel; where the two header lines cross (a turn tighter than half the header) the
strip is the two triangles of the bow tie. The strips of every combine are burnt in chronological order on a 0.25 m
raster (removed points still cut the ground they were logged on); the overlap of a position is the share of its strip
already cut, and a record's `Overlap_f` is the overlap F8 judged: that of its logged position by default, that of
its flow-delay source only with the `lag_stage` "before_f7" option (section 4). The strips are stored on the
processed table (internal columns `_qx0`.. `_qy3`) and are the ones the maps draw (section 8). `R["f8"]["footprint"]` and `R["f8"]["y_offset"]`
(the column used and whether it was applied) record the choice.

**F8 threshold.** The points that survive F0-F7 are binned by overlap (0, 0-2, 2-5, 5-10, 10-15, 15-25, 25-35 and
over 35 %). With `filters.F8.reference = "local"` (the default) the dose population is **the pass interiors**: the
records alive after F7 with at least 15 alive records before and after them in their pass (inside the plots when a
trial design is given), because the ramps at the pass ends are a machine transient longer than F7 (overlap test B),
not overlap (`R["f8"]["local"]["population"]`). Every record of it is compared with its **local no-overlap controls**
(`yield_clean.local_control_ratio`): the records of the same population without overlap, of the same combine, of
another pass, within max(15 m, 1.5 header widths) of it (`local_radius_m` is the 15 m; the header width is the 90th
percentile of the logged widths, so 16-23 m for 35-50 ft headers: the radius reaches the next pass of the same
combine; `R["f8"]["local"]["radius_m"]`) and within 4 m of the same distance from the edge of the harvested area
(`edge_tol_m`), at least 5 of them (`min_controls`); its ratio is its yield over the median yield of the controls.
**The combine** (`yield_clean.combine_key`, `R["f8"]["local"]["combine_key"]`) is the machine column; without one, the
source SMS writes in parentheses at the end of the dataset names when every name has one and two or more differ (a
display serial, or the maker of the monitor: '(CNH Industrial N.V.)', '(Trimble Navigation)'; `machines.from_dataset`,
the same combines as the harmonisation and the sessions); else the display serial SMS writes at the end of Case IH /
Ag Leader dataset names; else the Ops Center log (a record-id restart inside a dataset: one log per combine and task);
else one combine for the whole file, with a note. The edge
distance (`yield_clean.edge_distance`) is the distance to the edge of the harvested area: the processed positions on a
2 m grid, grown by half a header + 2 m, holes filled. A band's dose-response is the median ratio of its records over
the **placebo**, the median ratio of the no-overlap records themselves against their own controls (`R["f8"]["local"]`:
`placebo_ratio`, `placebo_n`, `matched_n`, `dose_n`). A band counts only with >= 30 records that have controls, and
the band sizes in the F8 figure read "records with controls / all records". The threshold is the upper edge of the
last band, counting from zero, within 3 % of the reference (`auto_tolerance_pct`), and **never below 5 %**
(`min_threshold`): when the scan stops lower, F8 removes above 5 % and the run says so (`R["f8"]["floor_applied"]`, a
note and the F8 rule in the cascade). The floor applies to the automatic threshold only, not to a fixed threshold or
to the fallback. Because the controls belong to the same combine, a calibration offset between combines cannot move
the threshold; the per-combine curves are listed in `R["f8"]["by_machine"]`. `R["f8"]["reference_mode"]` says which
reference was used. When fewer than 30 no-overlap records have controls (a small field, one where nearly every pass
overlaps, or interleaved combines whose own next pass lies out of reach), the run falls back to the v2.3 reference
below, with a warning. The threshold still applies to every record, not only to the pass interiors.

**The v2.3 reference (`reference = "field"`, and the fallback).** Each band's mean yield is compared with the
no-overlap band of the same combine, and the comparisons are pooled with the band sizes as weights. A combine's own
no-overlap band is its reference only when it can carry one: **>= 500 points or >= 10 % of the combine's records** in
the dose population (house rule); a combine below that is left out of the pooled curve and reported
(`R["f8"]["excluded_machines"]`, its bands in `by_machine` with `in_pooled` false), because a small, noisy 0-band
moves the combine's whole curve by several percent and drags the pooled curve across the tolerance although no yield
changed: the same Trial 19 records with every 4th pass labelled A / B / C / D gave 2 % and 7,962 kept points (A: 214
no-overlap points, -6.4 % at 2-5 %) against the single-machine 10 % and 26,694; with the rule, A and C are left out
and the 4-way split gives 10 % and 26,694 again (v2.3 model, tests/test_aoi_sessions_machines.py). With one combine
its 0-band is the field's and is always used. The v2.3 reference compares overlap bands that lie near the edges with
a no-overlap band that lies mostly inside the field, which is why v2.4 replaced it (section 3.1).

With either reference `R["f8"]` records the band that set the threshold (`last_pass_band`), its margin above the
tolerance (`margin_pct`) and size, and the band that stopped the scan with its reason (`stop_band`, `stop_reason`), so
a reader sees when the automatic threshold sits at the edge. With the local reference `stop_kind` says what stopped
it: `too_few` (the next band has fewer than 30 records with controls: the threshold then reflects how many records
found controls, not a measured yield drop) or `tolerance` (the next band reads more than 3 % below its controls). On
the seven trials of section 13 the scan stopped for lack of matched records in 5 of 7. **With a trial design the dose population is the in-plot records**
(`R["f8"]["dose_population"] = "in-plot"`; >= 200 in-plot points alive after F7, else all records with a warning):
the headland and the border carry the turns, the fill and the empty-out, and the review's interior figure is the one
that measures the overlap effect alone. The threshold still applies to every record.

The worked figures below are those of the v2.3 model (chord footprint, the v2.3 reference, no floor, flow delay on
the output: section 12), with which the delivered cleanings were made; the v2.4 defaults change the thresholds and
the kept counts.

Trial 19: all records -> 5 % (the 5-10 % band is -5.4 %, the 10-15 % band -19.8 %); in-plot records (17,453 points)
-> 10 % (the 5-10 % band, 824 points, is -2.44 %, 0.56 points above the -3 % tolerance; the 10-15 % band, 30 points,
is -18.4 % and stops the scan). The review's interior figure (-1.8 % at 5-10 %) is measured on another population
and reference (records travelling within 20 deg of the 90 / 270 deg passes, bands against the 0-2.5 % band) and is
not directly comparable with the engine's -2.4 % (in-plot records against the 0 % band); both give 10 %, and the
margin is reported because it is small. Trial 29 (four X9): all records -> the 0-2 % band is already -8.7 %,
the dose-response cannot set the threshold and F8 uses `fallback_threshold` (10 %, the value of the delivered Trial 29
cleaning) with a warning; in-plot records (23,149 points) -> 0-2 % -1.4 %, 2-5 % -3.5 % -> 2 %, because combine
combine B reads -7.6 % as soon as it overlaps (2-5 % band; -6 to -8 % in every band above) while combine C stays within
-1 %. A 2 % threshold removes 16,199 points and leaves 13,719 of 45,364 (69.8 % removed): the run flags it, and the
decision (accept, or set a manual threshold after checking the swath widths and header offsets of the combines,
`docs/formats/jd_jdl.md` section 8) is the user's. With F8 fixed at 10 % the same run keeps 34,674.

When already the 0-2 % band fails (or holds fewer than 30 points) the reference cannot set the threshold (with either
reference) and F8 uses the fallback threshold (10 %) with a warning. The overlap raster covers the points with a
plausible position (removed points still cut the ground they were logged on); a field larger than 1e9 cells of 0.25 m
(7.9 x 7.9 km) is refused as several fields. F8 removes records; it corrects no yield (section 3.1).

### 3.1 Why the overlap model changed in v2.4 (overlap tests A, B and C, 29 October 2026)

Three pre-registered tests on the SMS exports of seven 2026 trials (Case IH AFS: T19, T20, T25; John Deere GreenStar 4:
T22, T23, T29, T30) froze their hypotheses, predictions and decision rules (with a SHA-256 hash) before any number was
computed; an adversarial review then redid each test from scratch. Test C asked whether what the map shows is overlap
(geometry), test A whether overlap lowers the logged yield and whether an effective-width correction works (bias),
test B whether the colour ramp at the pass ends follows time or distance (transient). The synthesis of the three
tests and their reviews is `docs/overlap_v24/SINTESE_testes_ABC_pt.md` (Portuguese). The v2.4 engine built from them
was then put to its own pre-registered evaluation (section 13). Where a review
corrected a number, the corrected one is given here; intervals are 95 % bootstraps over passes (the pass is the
resampled unit). "Exploratory" marks an analysis made after seeing the results.

- **The v2.3 footprint counted the reading's own predecessor (test C, H2b, sustained).** The v2.3 footprint was the
  rectangle along the chord from the previous point of the pass. In a turn it overlaps the previous reading's
  rectangle on the inside by a wedge of about (W² / 8) tan |Δβ| (W the header width, Δβ the change of chord
  direction), and F8 counted that wedge as ground already cut. The wedge alone caused 9-64 % of the v2.3 F8 removals,
  depending on the field and on the orientation of the raster (engine raster; review's numbers):

  | Trial | Records removed by the wedge alone | Share of the F8 removals [95 % CI] | Their yield / own-pass median |
  |---|---|---|---|
  | T19 | 2,091 | 55.7 % [42.3; 70.4] | 1.00 |
  | T20 | 287 | 9.4 % [3.8; 21.9] | 0.94 [0.87; 1.00] |
  | T25 | 931 | 31.2 % [22.7; 42.3] | 1.00 |
  | T22 | 242 | 40.3 % [21.6; 60.2] | 1.01 |
  | T23 | 122 | 14.2 % [7.6; 26.4] | 1.00 |
  | T29 | 2,923 | 40.9 % [35.1; 46.6] | 0.95 [0.91; 0.97] |
  | T30 | 656 | 31.6 % [18.8; 55.7] | 0.96 [0.92; 1.00] |

  In 6 of 7 trials these records yield like their pass (only on T29 does the CI exclude 1), consistent with "not
  harvested twice". The pre-registered evaluation of the engine's swept strip (section 13, P2: 9.4-55.1 % of the v2.3
  F8 removals) found the CI including 1 in 4 of 7 trials and wholly
  below 1 in T20 (0.891), T25 (0.983) and T29 (0.902): enough for the registered rule, but part of what the swept
  strip keeps there may be real overlap or the pass-start transient. The strip between consecutive header lines tiles the swept ground: 0 m² of overlap in 372,435
  consecutive pairs of the seven trials once the header lines do not cross and both header ends move forward (H1 and
  the corrected H2; the 2 exceptions, a collapsing section and a 51 deg heading jump, were already removed by F1), and
  its area over W x step has a median of 1.0000. Real clipping in a turn needs a radius below half the header:
  0.002-0.020 % of the records, none of them in a final map (H5). The wedge is also what makes F8 sensitive to the raster:
  leaving out the predecessor, or using the swept strip, cut the share of decisions that flip when the raster origin
  moves by 36-98 %, and with the swept strip 2-16 % of them still depend on the raster (exploratory, review C).
- **Y_Offset (test C and its review).** The John Deere logged width is already narrowed by section control (the
  exported yield is flow / (logged width x speed); mass over that area has a median of 1.000), and |Y_Offset| > 1 ft
  on 7-30 % of the John Deere readings, but v2.3 centred the narrowed strip on the header. SMS moves every reading
  `Y_Offset_f` to the right of travel (`sms_swath.py`), and v2.4 places the F8 strip the same way. The evaluation
  confirmed the geometry (section 13, P4: the median overlap of the narrowed John Deere records falls to 0 in 4 of 4
  trials, the offset is within 1 ft of half the narrowing on 85-99 % of them, and scaling the offset by s gives the
  least overlap at s = 1); whether it puts the strip on the active sections has not yet been tested on yield
  (synthesis, item 3b).
- **The field-wide no-overlap band is a biased reference (review of test A, P3).** The records with more than 5 %
  overlap lie a median 9-32 m from the field edge, the no-overlap records 60-160 m, and near the edge the yield is not
  the interior's: no-overlap records against no-overlap controls read 0.78 (T19, 0-15 m from the edge), 1.23 (T19,
  15-30 m), 1.15 (T25, 0-15 m), 0.93 (T25, 15-30 m) and 0.90 (T30, 15-30 m), while the placebo passes in the interior.
  The v2.3 dose-response compared near-edge overlap bands with the interior and inherited that gradient. With controls
  matched on the edge distance (+/- 4 m) the John Deere 5-15 % bands read 1.007 and 1.004 (on only 22-28 records of
  2-12 passes), while the Case IH effect stays (b = 0.62 [0.38; 0.90] in ratio = a (1 - b f)). The v2.4 reference is
  the control set of test A (same combine, another pass, >= 5 controls) with the review's edge match, on the pass
  interiors and with the radius widened to max(15 m, 1.5 header widths), as the review used for the 50 ft headers of
  T29. Its placebo lies within 0.97-1.03 on all seven trials (section 13, P6).
- **A 5 % floor (tests A and C).** Below about 5 % the overlap of one record is not resolved. A position error of
  0.3-1 m is an overlap of 2.0-9.4 % on a 10.7-15.2 m header; one raster column is 1.7-2.3 % of the header and
  `Overlap_f` piles up at 2-2.5 % (one column: 12,622 records on T20, 19 % of those alive after F7); moving the raster
  origin by 0.125 m changed 59-73 % of the T19 F8 decisions at the 5 % threshold (14-41 % on T25, 4-19 % on the other
  trials; the total removed changed by at most 1.5 %). The floor is the resolution, not an absence of bias: the review
  measured +2.5 % [1.1; 3.7] in the John Deere 2-5 % band and -2.0 % [-3.6; -0.3] in the Case IH 5-10 % band. In the
  evaluation, automatic thresholds of 2 % moved with the raster origin (swept strip alone on T30: 2 -> 5 %), and the
  swept strip with the field reference gave 2 % on T22, T23 and T30; the floor was never ablated alone. The v2.3
  thresholds of 2026 were T19 5 %, T20 5 %, T25 10 %, T22 15 %, T23 25 %, T29 10 % (fallback; the rule gave 1 %) and
  T30 5 %.
- **Removal, not correction (test A).** Overlap lowers the Case IH yield (H0 refuted: b between 0.62 and 0.76 in
  every control variant, lower limits 0.36-0.46), but the effective-width correction y / (1 - f) does not flatten the
  curve: 1.051 [1.033; 1.068] at 5-10 % and 1.114 [1.074; 1.156] at 10-15 % overlap; and the logged width is the right
  area basis (spacing of adjacent parallel passes / W = 0.992-0.9996). F8 therefore still removes records and corrects
  none.
- **What v2.4 does not change.** F7 stays 4 / 2: test B found the end ramp longer than 2 records in 7 of 7 trials and
  the start ramp longer than 4 in 5 of 7, but the per-field table it proposed was measured after the old F7, moves with
  the bootstrap seed, and would remove 8-10 % of the kept John Deere records to raise the field mean by 0.2-0.7 %; a
  per-field count waits for the v2.4 F8 and flow delay (synthesis, item 6). No edge filter (the edge gradients of T20
  and T25 are real yield) and no John Deere minimum-width rule (synthesis, item 8). Not yet done (synthesis, items
  3d-3f): flagging the overlap over ground cut in another session as low confidence (a GNSS shift between sessions
  measures the overlap of a whole pass wrongly); the harvest order of an SMS export stays inferred, because its Time has
  no time of day (a decoded card carries the time of every record); and the overlap is still measured on the 0.25 m
  raster, not in vector or on a 0.05 m raster, which individual decisions at thresholds of 10 % or less would need.

## 4. Flow delay

**The scan.** By default (`lag_stage = "output"`, as in v2.3) the scan runs on the kept records after the whole
cascade: the pass interiors are smoothed (5-point rolling median; the first 14 and the last 16 alive records of each
pass are left out). The records are split by heading into E (45-135 deg), W (225-315 deg), N and S, and the scan
compares the two directions of **the axis the field was harvested in** (`lag_axis = "dominant"`, v2.4: the axis whose
smaller direction holds more records). For every lag from -8 to +8 records, each point of the passes in one direction
is paired with its nearest neighbour (within 1.2 median header widths) in the passes of the opposite direction (>= 100
points per direction), and the correlation r of the two smoothed yields is computed. A shift is applied only when
**the best lag is 2 to 7 records from zero and it raises r by more than 0.01 over lag 0** (a best lag of +/-8, the
edge of the scan, is not resolved and nothing is moved). A fixed correction is given in the same convention as the
scan. v2.3 (`lag_axis = "ew_first"`) took the E-W passes whenever E and W both held >= 200 records, which on a field
harvested N-S scanned its few E-W headland passes (T20: 2,432 E-W core records against 57,259 N-S).

**What the shift does.** The shift is minus the best lag (`Lag_rec`, `R["lag"]["applied_records"]`): record k of a
pass belongs to position k + shift of the same pass, the ground its grain came from (`yield_clean.lag_source_index`).
In the default stage the shift **moves the output geometry only**: F7 has trimmed the pass ends and F8 has judged the
overlap at the logged positions (`Overlap_f` is the overlap there), and the DIFM-ready and flagged files carry each
kept record at its shifted position (the logged one in `X_log`, `Y_log`); the maps draw the strip of that position.
`R["lag"]` records `stage`, `axis`, `measured_on`, the scan, the best lag, r at 0 and the rule.

**The option `lag_stage = "before_f7"` (not the default).** The scan runs after F6, on the records still alive then,
and every yield is tied to its source position before F7 and F8: F7 trims and F8 measures the overlap at the source
positions, and a record whose source lies beyond its pass ends (its grain came from before the pass started or after
it ended, an orphan: `R["lag"]["n_orphans"]`) is removed with F7, whose criterion counts them (with F7 switched off they
stay, with the overlap of the nearest pass end and a note). The review of overlap test B (X3, exploratory) had
suggested it: shifting the yield 2-5 records against the positions before F8 cut the end-of-pass deficit D5 (1 - the
mean of the last five records over the pass interior) from 0.33 to 0.07 (T25), 0.19 to 0.06 (T22) and 0.13 to 0.07
(T23). **It failed its pre-registered test** (section 13, P5): D5e after F8 stayed at 0.126 (T22), 0.133 (T23) and
0.331 (T25) against the registered bound of 0.10. On T23 and T25 the before-F7 scan found a best lag of -1, so nothing
was shifted; with the review's own lags imposed D5e was still 0.105 (T22, F8 held at 15 %), 0.129 (T23) and 0.1001
(T25), because the review's X3 had also dropped two more end yields. Side effects: on T22 the +3 shift moved John
Deere pass-start spikes into the 10-25 % bands, every band passed and F8 removed nothing (threshold 15 % -> 100 %,
601 -> 0 records); 311-2,313 orphan records were removed on T20, T22 and T29; on T29 the scan applied -5, a shift of
the wrong sign, and D5e worsened from 0.277 to 0.312. The end-of-pass deficit is therefore only partly a misalignment
of yield and position; it needs a measured F7 end trim (synthesis, item 6), not a delay. The option is kept for
research runs.

**Why the dominant axis (exploratory, section 5 of the evaluation).** T20, T25, T23 and T29 were harvested N-S (94,
89, 93 and 77 % of the core records), yet the v2.3 rule scanned their minority E-W passes, on which only a handful of
passes have an opposite-direction neighbour at lag 0 (T20 4 + 3, T25 6 + 6, T23 1 + 1, T29 26 + 34). On the dominant
axis the best lag after the v2.3 cascade was T19 0, T20 -5, T25 -4, T22 -2, T23 -2, T29 -1, T30 +1. On T29 the v2.3
scan's -5 placed the yields about 7 records (11 m) from their ground: the crop-edge timing (mass flow against the
overlap edge) gives -2.0 [-2.5; -2.0] records, -1.5 to -2.5 per combine, and no combine or speed tercile shows a
positive best lag. With the final v2.4 engine the applied shifts are T19 0, T20 +5, T25 +4, T22 +2, T23 +2, T29 +2,
T30 0 records (v2.3: 0, +2, +3, +2, +2, -5, 0). Limits: the dominant-axis rule was chosen after seeing these data and
was not tested in a pre-registration; the r-gain > 0.01 gate is not a meaningful test (the gain is >= 0 by
construction and its bootstrap spread, 0.01-0.05, exceeds 0.01); and the T29 shift is fragile: with the raster origin
moved by 0.125 m (which changes the kept set the scan runs on) it is 0 instead of +2. A sign-stability rule (dominant
axis, a fixed pair set, >= 90 % of bootstrap replicates with |best| >= 2 and the same sign; exploratory) would shift
T20, T25 and T22 and leave T23 and T29 unshifted: a candidate for the next pre-registration.

The ramp itself is the machine, not the field edge: at the same headland the end of a pass reads deeper than the start
in 5 of 7 trials (review of test B, R3), which a field-edge effect cannot do.

Sources: Marchant et al. 2019 (the shift maximising the correlation of opposite-direction neighbours); Lee et al. 2012
(delays scanned -8..+18 s); Chung et al. 2002 (pass-end lows bias the delay); the gates, the axis and the stage are
house rules. (v2.3 model: Trial 19 best lag 0, no shift; Trial 29 decoded `.jdl` with the design: best -2 at 2 %,
applied 2; at 10 % the best lag sits at the edge (+8) and nothing is moved, with a warning.)

## 5. Harvest sessions and the moisture basis (diagnostics)

Monitors map a *dry* yield from the wet flow and the moisture sensor. SMS and the three raw formats shrink
**one-sided**: readings below the standard moisture Ms are not raised, so the dry part of a field is mapped at its
wet yield while the wet part is shrunk, and two days at different moistures are not on one basis (Luck & Fulton 2014:
dry yield = wet x (100 - M) / (100 - Ms); Lee et al. 2012: a field cut on two dates at very different moisture).

- **Standard moisture Ms**: settings `moisture.standard_pct` > the decoder report > inferred from the export (where
  `Yld_Vol_Dr / Yld_Vol_We < 0.999`: Ms = 100 - (100 - M) / ratio, median over >= 200 such records) > the crop
  table. **Shrink**: one-sided when dry == wet on >= 95 % of the records with M < Ms, else symmetric.
  `R["moisture"] = {standard_pct, source, shrink, n_below_standard, share_below_standard, ...}`.
- **`Yld_Dry_Sy`** (N 15.4) = wet yield x (100 - M) / (100 - Ms): the symmetric dry-matter basis, written to the
  flagged file always and to the DIFM-ready file in a v2 run (crop, standard moisture or AOI given). It equals the
  mapped dry yield above Ms under one-sided shrink.
- **Sessions** = machine x calendar day of the record (the dataset when the records carry no time of day, as in SMS
  exports). UTC records (John Deere) take the local day: the decoder's time-zone offset, else round(longitude / 15) h
  (house rule; Trial 29: UTC -7 h, one session per combine on 22 Sep instead of a 27-minute "23 Sep" tail). Columns
  `Harv_Day` (C 10) and `Session` (C 32, `<machine>|<day>`; a long machine id keeps its tail). The offset is applied
  only when the decoder reports `time_basis` UTC: the John Deere and CNH decoders shift the timestamps themselves when
  a time-zone offset is given and then report local times, which are left alone. Without a time of day the day comes
  from the dataset name (SMS `YY/MM/DD-HH:MM:SS`, Ops Center `TaskName M/D/YYYY`: the Trial 29 Ops Center export gets
  2026-09-22) or from the date-only time column. Per session: machine, day, dataset(s), start, end, readings, kept,
  area, wet bu, moisture (mean, SD, `share_below_standard_kept` = share of the KEPT readings below Ms; the field-level
  `R["moisture"]["share_below_standard"]` counts every processed record: the 8.7 % task of Trial 19 has 549 of its 592
  records below 14.5 %, share 0.927, and all of its 218 kept records, share 1.0), mean yield wet / dry as mapped / dry
  symmetric. Field level: the mean of mass per area over **every processed reading** (the field's integral over its
  swept area), which is not the mean of the cleaned map (Trial 19: 69.8 vs 72.2 bu/ac).
- **Discontinuity check**: consecutive sessions of one machine, paired 30 m cells between adjacent passes of the two
  sessions (same plot / rate with a design; >= 10 cells and >= 3 pass pairs): yield ratio (geometric mean, block
  bootstrap over pass pairs) and moisture difference. The pairs use the records with <= 2 % overlap first (the later
  session follows the earlier one and carries the sub-threshold overlap, which reads 2-3 % low); when those are too
  few for the gate every kept record is paired and the row says so (`pairs`). Diagnostic only.
- **Recommendation (house rule)**: sessions differing by > 2 moisture points, or > 20 % of the readings below Ms
  under one-sided shrink -> "map `Yld_Dry_Sy` as the yield in DIFM and keep `Harv_Day` as a block". When no
  `Yld_Dry_Sy` could be computed (Ms unknown: no crop, no decoder value, too few shrunk records; or no wet yield /
  moisture) no column is named: the text says what is missing and `Harv_Day` stays the block.
  Figure `fig_clean_sessions.png` (moisture and dry yield vs time by session, Ms as a line).

Trial 19 SMS export: Ms 14.5 % inferred from 2,419 records; one-sided (dry == wet on 100 % of the 29,407 records
below Ms); 90.7 % of the readings below Ms; sessions = the datasets (SMS `Time` has no time of day), 4 on 20-21 Sep
after the AOI pre-step; `Yld_Dry_Sy` recommended. Trial 29: Ms 13.5 % (decoder, Ops Center's wheat standard),
78 % below. A canola field: Ms 10 %, 100 % below (moisture 6.9 %).

## 6. Several combines

The reference is the combine with the most kept points (`machines.reference` "auto", or an id; an id whose records
the cascade removed falls back to "auto" with a warning). **The factor is applied to the non-reference combines**: a
reference that reads 5 % high appears as a factor of about 1.05 on the other combine, never as 0.95 on the reference.
Every other combine is compared with it on paired cells of 30 m and of 50 m that both harvested (>= 5 kept points of
each **with <= 2 % of the footprint already cut**, `machines.pair_max_overlap`, house rule from the 0-2 % band of the
dose-response, which reads within 0.2 % of the no-overlap band on Trial 19; split by `Plot_Id` when a design exists
and `same_plot_only`, so the pairs compare the same treatment): f = exp(mean(log(ref / m))) per cell size, CI by block
bootstrap over pass pairs (1,000 reps, seed 2026). The overlap rule is what keeps two combines working side by side
from getting a factor they do not deserve: the pass that follows another carries the sub-threshold overlap and its
kept records read 2-3 % low, so pairing every kept record measures the overlap, not the machine (Trial 19 with alternate
passes labelled A / B and no yield change: 1.029 with CI 1.008-1.049, "applied", on every kept record; 1.009, CI
includes 1, with the rule; 20 random pass splits: 1 applied either way). The price is fewer pairs (Trial 19
pseudo-machines: 40 cells / 8 pass pairs instead of 200 / 28) and a noisier estimate. The 30 m factor is **applied**
(`Yld_Harm` = y x f on that combine, 1 elsewhere) only when >= 30 cells and >= 5 pass pairs exist at both sizes, both
95 % CIs exclude 1, the two factors agree within 2 % and 1 % < |f - 1| <= 10 %. Above 10 % nothing is applied and
the run asks for per-machine weights. The paired t-test p (the v1 test) and the moisture difference on the same pairs
are diagnostics. Means per combine (points, kept, area, wet bu, mass per area, moisture, cleaned-map mean) are
reported. Sources: Maldaner et al. 2016 (one factor per combine against a reference combine); Chiocco & Wuestefeld
2019 (gain searched within +/- 10 %, the cap); Gauci et al. 2023 (calibrated monitors within 1.7 % of the weigh
wagon: a step under the 1 % floor is noise); the gates are a house method.

**Per-combine weighed totals** (`machines.totals_bu`, CLI `--machine-total VIN=BU`) are applied whenever they are
given, with or without the relative harmonisation and also for a single combine: L_m = ticket_m / wet integral_m;
`Yld_Level` = y x L_m; `Yld_Harm` = y x L_m / L_ref. The paired estimate becomes a validation: agreement =
(L_m / L_ref) / f_paired - 1, and whether the ticket ratio falls inside the paired CI, **only where the paired estimate
passes its own gate** (>= 30 cells, >= 5 pass pairs, a CI); otherwise the validation says "no paired estimate: too few
pairs" and no disagreement is claimed. A gated disagreement above 5 % is a warning (check the tickets' coverage and the
calibration). A combine without a ticket is leveled with the reference's L (warning), and the level's ticket is then
the implied field total (own tickets + integral x L_ref for the rest); a `scale_ticket_bu` given beside the tickets is
compared with that total (warning above 1 %) and the set-aside warning of section 7 still applies. Tickets that name
combines when the file names none (no machine column, no differing sources in the dataset names) are refused with a
warning (give the field total as `scale_ticket_bu`).
With only a field total: relative harmonisation first, then L on the harmonised integral.

Trial 19 pseudo-machines (every third pass x 1.08, with the design, pairs on the <= 2 % overlap records): f30 0.9105
(CI 0.876-0.937, 40 cells / 8 pass pairs), f50 0.917, applied; x 1.15 -> 0.855, not applied ("request per-machine
weights"); x 1.00 -> 0.983, CI includes 1, not applied; alternate passes A / B x 1.00 -> 1.009, not applied; 1 of 20
random pass splits applied a factor. Without the design the pairs compare different seed rates: 125 cells, f 0.874,
above max_factor, not applied: on a trial, give the design. Trial 29 (F8 10 %, design, **reference combine A** with
11,022 kept points): combine B f 1.043 at 30 m (86 cells, 14 pass pairs, CI 0.972-1.128) and 1.055 at 50 m (151 cells,
CI 1.006-1.096) -> not applied (the 30 m CI includes 1); combine C 26 cells at 30 m -> too few pairs (1.076; 1.100 at
50 m on 102 cells); combine D too few pairs. Means (wet mass per area): combine A 64.1, combine C 62.8, combine B 58.7, combine D
59.1 bu/ac. With synthetic tickets combine A = 4,970 and combine B = 4,980 bu: L 1.0098 and 1.0700, L_m / L_ref 1.0596 on
combine B (x 1.0596 on its records; combine A keeps 1) vs the paired 1.043 (inside its CI, agreement +1.6 %); the two
combines without a ticket take the reference's L and read "no paired estimate: too few pairs" (the ungated estimates,
1.076 and 0.991, are kept in the JSON as `paired_factor_ungated` only).

## 7. Level

Processed-set total = the sum over **every processed record** (inside the AOI + 50 m when one is given, else the whole
export) of yield x distance x width / 43,560: the scale ticket weighs every load, including the grain cut on the
headland, so the denominator must be the whole processed set, not the cleaned map. The yield column of the integral
follows the basis of the ticket (`scale_ticket_basis`): "wet" (default; a weighed total is wet grain / test weight)
uses the wet yield column, "dry" the mapped dry column. `L = scale_ticket_bu / processed-set integral`;
`Yld_Level = mapped yield x L` (x the harmonisation factor) - L is a calibration factor of the mass flow, so a
wet-basis L also applies to the dry column. The integral inside the AOI itself (0 m) and the integral of the records
set aside by the AOI are recorded as diagnostics; **when the set-aside records carry more than 5 % of the processed
grain the run warns and gives the L the whole file would imply** (also when the level comes from per-combine tickets):
a total that covers the whole export (the grower's field total) must not be divided by the integral of the trial area.
A `scale_ticket_bu` given together with per-combine tickets is compared with the total they imply and a difference
above 1 % is a warning; the per-combine tickets are used. The pattern, the cleaning and the ranking of
treatments do not depend on L; the economics do. Sources: Clarke et al. 2024 (each map rescaled to the weighed
yield); Luck & Fulton 2014 (agreement 1-3 % expected; recalibrate at >= 3 %); Gauci et al. 2023 (calibrated monitors
within 1.7 % of the weigh wagon, 15.8-17.2 % off outside the calibrated flow range); the bands on |L - 1| are a house
rule.

Trial 19: the ticket on the scale against the export integral of 7,622.3 bu over 109.23 ac (L = 1.110; the export is
9.9 % below the scale); with the design as AOI the processed set integrates 7,495.2 bu (L 1.1287) and the field itself
7,491.8 bu over 107.33 ac, which is what SMS displays for the layer (7,493.5 bu). Trial 29: the field total
over the design area + 50 m gives L 1.7669 (warning); over the whole file (27,461 bu) L 1.0072.

### 7.1 Grower's weight as the real level

The weight the grower got for the field is the only absolute total there is; the monitor's mass flow is a calibrated
sensor that drifts by crop, moisture and season (Luck & Fulton 2014: 1-3 % agreement when calibrated, recalibrate
at >= 3 %). The weight is entered as the ticket gives it (`scale_ticket = {value, unit, basis, moisture_pct, note}`;
unit lb | kg | bu | t with t = 1,000 kg; `scale_ticket_bu` remains the alias in bushels) and converted to bushels
with the test weight: `test_weight_lb_bu` when given, else the file's own ratio median(`Yld_Mass_W` / `Yld_Vol_We`),
else the crop table, else the run stops and asks for `test_weight_lb_bu`. The run records the ticket in its unit, in
lb and in bu, the test weight used and where it came from, the monitor total in bu and lb, L, and a closure
(monitor vs scale, before and after the combine harmonisation).

- **What L does.** It multiplies every yield by one number, so the map's pattern, the cleaning and the ranking of
  the treatments are untouched; the bu/ac of the leveled columns sum to the scale, and the dollar figures of the
  analysis sit at the grower's level. The file keeps the monitor's values and adds `Yld_Level` (mapped dry yield x
  combine factor x L) and `Yld_Lvl_Sy` (`Yld_Dry_Sy` x factor x L, when the symmetric column exists). The column to
  map is the leveled one: `Yld_Lvl_Sy` when the sessions diagnostic recommends the symmetric basis, else `Yld_Level`.
  A legacy `scale_ticket_bu` run writes `Yld_Level` only and the Trial 19 file stays byte-identical.
- **Basis.** A wet ticket (default: the scale weighs wet grain) is compared with the wet integral; a dry ticket
  (already at the standard moisture) with the dry integral; a wet ticket with its moisture is shrunk to the
  standard moisture symmetric-wise and compared with the `Yld_Dry_Sy` integral, and every caption then names that
  figure as the scale ("monitor 7,749 bu vs scale S bu (+12.4 %; the ticket at 12 % = S bu at 14.5 %)"), the
  same L divides by. A ticket moisture on the dry basis is refused (settings and CLI): it would have been ignored.
- **The closure verdict.** Monitor total vs the weight before and after the combine harmonisation (the "after"
  figures only when a factor changed the total), banded on |L - 1| - the same quantity the "> 10 %" advice checks:
  <= 1 % a small level correction; 1-3 % the agreement expected after a field calibration (Luck & Fulton 2014);
  3-10 % the monitor's calibration should be checked; > 10 % check the ticket coverage before trusting L. Both
  directions are named: Trial 19 "the monitor total is -9.9 % from the grower's weight (L = 1.1099 is +11.0 % from
  1, > 10 %)". With per-combine tickets the verdict bands the field-level gap (sum of the tickets / integral) and
  states that each combine is leveled to its own ticket, so the leveled map integrates to the tickets. The level
  shown first in the app and the report is the one applied to the columns (after a confirmed combine factor).
- **What the leveled column integrates to.** L is derived on the comparison column (the wet yield for a wet ticket)
  and applied to the mapped dry yield, so `Yld_Level` integrates to the ticket on the comparison basis
  (`leveled_export_integral_bu`); its own integral (`yld_level_integral_bu`) differs by the gap between the mapped
  dry and the comparison column (one-sided shrink above the standard moisture; 0.007 % on the 5-combine field). `Yld_Lvl_Sy` is
  written only when `Yld_Dry_Sy` itself is (`moisture.add_symmetric_column`).
- **The closure test for combines.** A paired factor proven at 30 m and 50 m but above `machines.max_factor` is not
  applied by itself (a > 10 % step is more than a relative factor should repair). With a grower's weight the run
  computes the monitor total with that factor applied: when it closes with the weight within
  `machines.ticket_close_tol` (1 %) while the unharmonised total is more than 3 x that away, the weight confirms the
  factor and it is applied; the decision says so, and `R["machines"]["ticket_test"]` keeps both totals. When it does
  not close, nothing is applied and the result says so. A factor above the gate whose CI includes 1 at one cell size
  or whose 30 m / 50 m estimates disagree by more than 2 % is not a candidate: the decision names the reason ("and
  the 30 m and 50 m factors disagree (1.2135 vs 1.2803), so a grower's weight is not used to confirm it") and the
  ticket test repeats it ("candidate A rejected: ..."), adding "try machines.reference = A" when the weight sits
  nearer that combine's level than the reference's (the closure can only scale the non-reference combines). The 5-combine field
  barley 2026 (5 combines, 130,847 readings, 47.99 lb/bu,
  W lb = V bu): monitor M bu, L 0.9481; combine E at 0.7825 (CI 0.762-0.803, 396 cells)
  was beyond the 10 % gate; with its factor the harmonised total is V' bu, 0.07 % from the scale, so the
  factor is applied and the final L is 1.0007; the four other combines, whose CIs include 1, are unchanged.
- **When NOT to trust L.** The ticket covers several fields, or only part of this one (the run asks to check the
  coverage when |L - 1| > 10 %); the weight is net of dockage while the monitor is gross (or the reverse); the ticket
  is on another moisture basis than the comparison; loads were lost, double-counted or weighed elsewhere; the field
  of interest set aside records the ticket weighed (warning above 5 % of the grain). In those cases keep the monitor
  level (map `Yld_Harm` / `Yld_Dry_Sy` / `Yld_Vol_Dr`) and report both.

## 8. What is delivered and how it is used

- `<tag>_difm_ready.zip` (shp, shx, dbf, prj, cpg): the kept points inside the field of interest, original columns
  and values, plus `Yld_Harm` (several combines), `Yld_Level` (scale ticket or per-combine totals) and, in a v2 run,
  `Yld_Lvl_Sy` (grower's weight with the symmetric column), `Yld_Dry_Sy`, `Harv_Day`, `Session`, `Plot_Id`,
  `Tgt_Rate` (the last two with a design). This is the upload.
- `<tag>_flagged.shp`: every processed point with `Pass_Id`, `Run_Id`, `Keep`, `Rem_By`, `Overlap_f`, `Lag_rec`,
  `Yld_Harm`, `Yld_Level`, `X_log`, `Y_log`, `Yld_Dry_Sy`, `Harv_Day`, `Session` and, with an AOI, `In_AOI`,
  `Plot_Id`, `Tgt_Rate`, so every removal can be audited. `Overlap_f` is the overlap F8 judged (at the logged
  position by default; at the flow-delay source with the `lag_stage` "before_f7" option; section 4) and `Lag_rec`
  the shift in records.
- `<tag>_cleaning.json` (`pre_steps`, `cascade`, `f8`, `lag`, `aoi`, `moisture`, `sessions`, `machines`, `level`,
  `warnings`, `advice`), five figures (map, cascade, F8 dose-response, lag scan, sessions) and the report PDF with
  the references of the steps that ran. Since v2.4 `f8` also holds `footprint`, `y_offset`, `reference_mode`,
  `floor_applied`, `stop_kind` and `local` (`radius_m`, `radius_setting_m`, `full_width_m`, `edge_tol_m`,
  `min_controls`, `population`, `combine_key`, `n_combines`, `dose_n`, `matched_n`, `placebo_n`, `placebo_ratio`), and
  `lag` holds `stage`, `axis`, `measured_on` and `n_orphans`; the report reads them with defaults, so an older JSON
  still renders.
- **The maps.** The map draws each reading as the strip its header swept since the previous reading (the swept strip
  of section 3, stored on the processed table; consecutive strips tile, so a turn shows no fan of overlapping
  rectangles and a Case IH pass start no stack of strips): before the cleaning every reading at its logged position,
  after it the strip of each kept record's output position, the ground its grain came from after the flow-delay shift
  (the logged position when no shift is applied; a record whose source lies beyond its pass is drawn as a point), so
  a wrong shift moves the drawn yields: a scan problem, not a drawing one. The SMS 3-sigma map draws the swept strips before and SMS's own
  rectangles after: the point on the front edge, the optimised width across, the optimised Distance back along the
  heading, as SMS draws a yield map (`yield_clean.swath_quads`). The app's maps build the same strips from the point
  file (`engine.run.preview_swaths`: a sequence breaks at a change of `Run_Id` / `Pass_Id`, dataset or machine, at a
  step longer than 1.5 x Distance + 0.3 m, so a removed reading between two kept ones is not bridged, and at a heading
  change above 60 deg; the file's `Y_Offset` is applied), except that an SMS 3-sigma output (it holds `Swath_Scl`)
  keeps the SMS rectangles; the comparison's agreement map (section 11) uses the stored strips. Up to v2.3 every map
  drew the W x D rectangle back along the logged heading, which fans out in a turn and stacks at a Case IH pass start
  (test C, H3). **The strips are for display only**: on Case IH the logged Distance is speed x duration while the
  GNSS positions come in 0.2 s epochs, so W x step differs from W x D, the area of the logged yield, by about +/- 20 %
  per reading (test C, H4), and no mass or total is ever computed over the drawn polygons.

**Which yield column to map in DIFM** (`engine.run.recommended_yield_column`; the app and the CLI print it):

| Situation | Yield column | Block / also |
|---|---|---|
| one combine, one session, no ticket | `Yld_Vol_Dr` | - |
| sessions differ (> 2 moisture points) or > 20 % of the readings below Ms under one-sided shrink | `Yld_Dry_Sy` | `Harv_Day` as a block |
| several combines, factor applied (paired or per-combine tickets) | `Yld_Harm` (wins over `Yld_Dry_Sy`, which carries no combine factor) | `Harv_Day` as a block when the sessions asked for it; `Yld_Level` for scale-level economics |
| several combines, nothing applied | `Yld_Vol_Dr` or `Yld_Dry_Sy` as above; get the per-combine weights | `Machine` as a block if the platform allows |
| scale ticket given | the column above; `Yld_Level` only for the dollar figures at the scale level | - |
| trial design given | the column above | `Plot_Id`, `Tgt_Rate` to check the design against the harvest |

DIFM mapping: distance, width, speed and heading unchanged; input rate = the applied column of each as-applied file.

## 9. Trial design rules that follow from the standard

- Plot width = a common multiple of the combine header and the drill/spreader width (39 ft and 65 ft -> 195 ft,
  59.4 m: 5 combine passes, 3 drill passes), so no harvest pass straddles two plots.
- Two inputs: an orthogonal factorial (every rate of one input with every rate of the other, equally often), so that
  the correlation between the rates is zero by construction.
- Plots long enough for at least three 20 m observation units after the rate ramps at both ends.
- Deliver the design polygon file (plots + headland with `type`, plot id, target rate) with the harvest data: it is
  the field of interest of the cleaning and the source of `Plot_Id` / `Tgt_Rate`.
- Ask for the weighed total **per combine** when several combines harvest a trial: it is the only way to level each
  combine without relying on the paired estimate.

## 10. The SMS 3-sigma method (alternative)

The OFPE team also cleans yield maps by hand in Ag Leader SMS Advanced with a fixed sequence of *Add Simple
Analysis* steps (the team's guide "Limpeza 3 sigma no SMS", Trial 19, 9 Oct 2026; the per-trial limits are in the
SMS project "OFPE 2026 - Oct 9 - 3 SIGMA CLEAN"). OCCD reproduces that sequence as a second method
(`settings["method"] = "sms3sigma"`, CLI `--method sms3sigma`, the app's *Cleaning method* selector;
`engine/clean/sms3sigma.py` and `engine/clean/sms_swath.py`), so a field can be cleaned "as in SMS" without SMS, and
both methods can be run on the same readings and compared (section 11). The OCCD cascade stays the house standard.

| Step | Removes / changes | Limits | Scope | Source |
|---|---|---|---|---|
| S0 SMS import check | no position or no yield; dry yield below 5 bu/ac | the SMS import minimum (`sms3sigma.min_yield`) | every reading | SMS import of a monitor file: every SMS raw export starts at 5.00 bu/ac |
| S1 Clip To Field Boundary | the logged point outside the field of interest | a point on the edge counts as inside (1 cm) | the operation | SMS help; Trial 19: 33,017 -> 32,397 exactly |
| S2 Optimize Swath Widths | fully overlapped readings removed; partly overlapped ones narrowed to the uncovered strip, moved to its centre; readings overlapped at the back by their predecessor shortened; per-area values x old / new area (W x D) / (W' x D') | reverse-engineered (`sms_swath.DEFAULTS`) | the operation, harvest time order across every task and combine | SMS help ("individual swath rectangles", "Scale Per Area"); raw vs cleaned SMS exports |
| S3 Speed | outside mean +/- 3 SD | recomputed on the points still alive | group | SMS Filter Data on Edit Legend statistics; house procedure |
| S4 Moisture | outside mean +/- 3 SD | recomputed | group | idem |
| S5a Dry yield, pass 1 | outside mean +/- 3 SD of the **scaled** yield, lower limit floored at 0 | recomputed | group | idem; dos Santos & Miguez 2025 (field mean +/- 3 SD of dry yield, one pass) and the F10 literature |
| S5b, S5c ... | another pass only while the previous one cut the SD by **more than 25 %** | recomputed | group | house procedure (a large drop means gross errors were inflating the SD) |

Rules that make the numbers the ones typed in SMS:

- **Mean and SD** are the plain point mean and SD of SMS *Edit Legend* (not the area-weighted *Statistics* average),
  recomputed on the points still alive before every step; SD with ddof 0 (no visible difference at field sizes).
- **Limits** = mean +/- k SD rounded half up to 2 decimals (what the user types), inclusive; the dry-yield lower
  limit is floored at 0, so a pass-1 window often reads 0-260.45; a negative speed or moisture lower limit is typed
  as 0 too (Trial 23 log: moisture 0.00-21.72), which keeps the same points.
- **Grouping** (S3-S5). SMS applies a filter to the task it is added on, or with one pooled mean and SD to every task
  when it is added on the operation. `sms3sigma.group_by = "auto"` follows the team's practice: one pooled group when
  one combine cut the field (machine column, else the sources of the SMS dataset names, else one display serial in
  them: Trial 19, 20, 25),
  one group per task otherwise (Trial 22, 23, 28, 29, 30, 41, 50). A task is the dataset (with the Ops Center `#log`
  split when the record id restarts) for SMS / Ops Center exports and Case IH task logs, machine x day for decoded
  John Deere logs. `task`, `machine` and `field` force a grouping.
- **Order**: clip and swath run once over the whole operation, in harvest time order: per-record time when the file
  has it (decoded logs); for SMS exports, whose `Time` is a date only, the datasets in the order of the start time
  (`YY/MM/DD-HH:MM:SS`) or date (`M/D/YYYY`, GreenStar 4) in their names, then record id. An SMS export of
  John Deere GreenStar 4 data lists each combine's ~17-minute log files in file-name order, not in time order, so for
  those (`sms3sigma.swath_order = "auto"`, dataset names `... (GreenStar 4 Monitor)`; in a mixed export only those
  datasets) the file blocks - a new block
  at every `Pass_Num` decrease - are put back in time order by where one ends and the next begins (minimum-cost
  chaining; 68 of 70 real successors on Trial 29). With several combines in one task the true interleaving is still
  unknown (SMS has the real time), which is the largest remaining difference on John Deere fields.
- **Optimize Swath Widths** (`engine/clean/sms_swath.py`). SMS does not document the rule; it was reverse-engineered
  from SMS's own output (raw vs 3-sigma clean exports of six 2026 trials, every clean point matched to its raw
  reading, plus the SMS log counts of Trial 30, which has no clean export; the module docstring gives the evidence
  of each rule):
  - the rectangles are built in a plane whose north is true north (a local transverse Mercator on the field; in UTM
    they would be rotated by the grid convergence, up to 1.9 deg), from the point moved `Y_Offset_f` ft to the right
    of travel - SMS moves every reading so and writes 0 in the export;
  - a reading is a rectangle with the point on its front edge, Distance long and Swath Width wide, tested in time
    order against a coverage raster (0.25 ft) of the strips already kept;
  - across the track only OLDER readings narrow it (its own predecessor is ignored, so the wedges of a turn are
    never cut); a column is covered above 60 %, seams of up to 2.75 ft in older passes count as covered, covered runs
    under 2.75 ft from an edge are not cut (5 ft for a reading narrower than the full header: sections already off),
    and the cut is whole feet from the edge;
  - along the track only the predecessor trims it: an overlap of 2.5 ft or more at the back shortens Distance, and
    SMS recomputes Speed = Distance / Duration (the speed limits of S3 are computed on that speed);
  - a reading is removed when every column is covered, or 95 % of it; a narrowed or shortened reading's per-area
    values are multiplied by (W x D) / (W' x D') and its point moved to the centre of the kept strip.
- **No flow-delay shift, no combine harmonisation**: neither is part of the SMS sequence (SMS applies the monitor's
  flow delay at import). The grower's weight still levels the map (`Yld_Level` on the SMS yield, as SMS *Adjust
  Yield* would) and the moisture basis and sessions are still reported.

**What is written.** The DIFM-ready file is what SMS exports after the swath step (checked cell by cell against
the Trial 19 SMS clean export):
- on the narrowed points the swath width column holds the new width, and the point sits at the centre of its kept
  strip;
- on the shortened points `Distance_f` holds the new distance, `Speed_mph_` is recomputed as Distance / Duration and
  the distance per fuel (`Fuel_Eff_m`) is multiplied by new / old distance;
- on both, the per-area columns (`Yld_Vol_Dr`, `Yld_Vol_We`, `Yld_Mass_W`, `Yld_Mass_D`, `Fuel_Con_A`, and the mapped
  yield / wet yield / wet mass columns) are multiplied by `Swath_Scl` = old / new area (W x D) / (W' x D'), and
  `Prod_ac_h_` and the area per fuel (`Fuel_Eff__`) are divided by it;
- `Y_Offset_f` is written as 0 and every point sits where SMS moved it (its offset to the right of travel);
- every other cell is the export's, byte for byte, and `Wdth_Raw` (original width) and `Swath_Scl` (the factor) are
  added for the audit. This departs from principle 1 on
purpose: the method is the SMS one, and DIFM rebuilds its polygons from the width, so the narrowed width must be in
the width column. The flagged file keeps the export's values with `Wdth_Opt`, `Dist_Opt`, `Swath_Scl` and the usual audit
columns (`Rem_By` = S0, S1, S2, S3, S4, S5a ...). Files are named `<tag>_sms3s_*`; the report has the per-group limits
table that is compared with Edit Legend, the figures map / cascade (the S0-S5 steps) / limits / sessions.

Integrals are not changed by the swath scaling (mass is conserved: scaled yield x narrowed area = yield x swept
area), so the level factor L of a grower's weight, the session and the per-machine totals are the same as with the
OCCD cascade on the same processed set; the cleaned-map means are the SMS map's.

### 10.1 Validation against SMS (October 2026)

The engine ran the method on the raw SMS exports of seven 2026 trials, which were then compared with the team's own
SMS 3-sigma runs. The limits and counts come from the SMS logs; the kept readings come from the SMS clean exports.
The runs used the default settings, with the SMS field boundary as the field of interest wherever the SMS chain
clipped, and two clip + swath passes on Trial 22, as in SMS.

| Trial | Monitor, combines | 3-sigma groups | Swath removed, OCCD / SMS | Final points, OCCD / SMS | Same readings kept |
|---|---|---|---|---|---|
| 19 | Case IH, 1 | pooled | 299 / 351 | 30,961 / 31,089 (-0.41 %) | 98.8 % |
| 20 | Case IH, 1 | pooled | 838 / 834 | 65,714 / 65,786 (-0.11 %) | 99.7 % |
| 22 | JD GS4, 3 tasks | per task | - | 32,781 / 32,755 (+0.08 %) | 99.9 % (9/9, 9/17) |
| 23 Brown | JD GS4, 2 combines | per task | 174 / 226 | 77,862 / 77,899 (-0.05 %) | 99.7 % |
| 25 | Case IH, 1 | pooled | 584 / 605 (a) | 48,602 / 48,515 (+0.18 %) | 99.5 % |
| 29 | JD GS4, 4 combines | per task | 365 / 438 | 76,759 / 76,715 (+0.06 %) | - (b) |
| 30 | JD GS4, 2 tasks | per task | 55 / 47 | 26,782 / 26,788 (-0.02 %) | - (no clean export) |

**Same readings kept** is the number of readings kept by both runs divided by the number kept by either. Readings are
matched on dataset, track, moisture, duration, crop flow and elevation, because SMS renumbers the record id.
- (a) SMS's 605 includes a greyed-out dataset of 232 readings that is in neither export.
- (b) The clean export of Trial 29 comes from a chain clipped to a boundary we do not have.
- Trial 22: someone else cleaned task 9/16 in SMS with other limits. It is left out of the agreement, and its final
  count (8,939 here, 8,927 in SMS) is not comparable.

Final points per task, OCCD / SMS:

| Trial | Tasks |
|---|---|
| 22 | 9/9 5,039 / 5,030; 9/17 18,803 / 18,798 |
| 23 | 8/31 B 2,396 / 2,396; 8/31 C 10,958 / 10,884; 9/1 A 33,596 / 33,611; 9/1 B 30,912 / 31,008 |
| 29 | tasks 1-4: 20,757 / 20,708; 21,772 / 21,711; 21,962 / 21,957; 12,268 / 12,339 |
| 30 | 9/20 25,172 / 25,164; 9/21 1,610 / 1,624 |

**What matches and what does not:**
- **Clip:** Trial 19 goes from 33,017 to 32,397 readings, exactly as in SMS.
- **Speed and moisture limits:**
  - exact on Trial 19 (0.90-3.96 mph, 10.65-15.71 %);
  - exact on Trial 25 except one value (1.23-3.58 mph, 12.81-20.44 % against 20.45);
  - within 0.02 mph and 0.01 % on Trial 20;
  - within about 0.1 on the John Deere tasks.
- **Dry-yield limits differ more.** The first pass's SD depends on how many narrow slivers the swath step leaves, and
  their scaled yields reach thousands of bu/ac.
  - Trial 19: pass 1 is 0-155.16 here against 0-260.45 in SMS; pass 2 is 16.05-130.79 against 10.81-137.11.
  - SMS keeps more slivers on some fields and fewer on others. Their number depends on the phase of SMS's internal
    1-ft grid, which the exports do not show.
  - On three John Deere tasks (Trial 23 8/31 C, Trial 29 tasks 1 and 2) the first pass cut the SD by 18-23 % here,
    against more than 25 % in SMS. The second yield pass therefore did not run here, and those tasks end with 49-74
    more points than SMS kept.
- **Processing order on John Deere fields:** SMS processes the readings in real time order, but the export carries
  dates only.
  - With the file blocks re-chained, the swath step removes 365 readings on Trial 29, against 438 in SMS.
  - The real timestamps of the decoded logs would give 448.
  - OCCD processes decoded .jdl logs, which carry the time, in true time order.
- **Widths:** on 97-99.9 % of the readings SMS kept, the width is within 0.5 ft of the SMS width. The sub-foot part
  of an oblique cut needs SMS's grid phase, so it is not reproduced exactly.
- **The written cells:** on the 30,834 readings both runs kept on Trial 19, the DIFM-ready cells equal SMS's within
  0.5 % on 97.3 % of the widths, 99.0 % of the distances, speeds and distances per fuel, 96.4 % of the dry yields
  and other per-area values, and 100 % of the offsets (written as 0).
- **Run time:** 16-50 s per field, including every output.

## 11. Comparing the two methods

`settings["method"] = "both"` (CLI `--method both`, the app's *Both, and compare*) cleans the same processed set
twice - the OCCD cascade into `output/` (the same records and cells as an OCCD-only run: the DIFM-ready and
flagged shapefiles are byte-identical; its cleaning JSON additionally carries `method = both` and `R["methods"]`, the
summaries of the other two runs), and the SMS 3-sigma
sequence into `output/sms3sigma/` - and compares them record by record (joined on the record's row in the file) into
`output/compare/` (`engine/clean/compare.py`, report `engine/report/compare_report.py`):

- the classes of the DIFM-ready points: kept by both, OCCD only, SMS 3-sigma only, removed by both; the agreement
  (kept by both / kept by either) and the share of readings with the same decision;
- side by side: points, area (distance x width; the optimised distance and width for SMS), point mean and area-weighted mean of
  each method's mapped dry yield (the export's for OCCD, the scaled one for SMS), median, SD, CV, P5 / P95, dry
  bushels on the kept points, mean moisture and speed, the leveled yield when a weight was given;
- where they disagree: the SMS step that removed the points OCCD keeps and the OCCD filter that removed the points SMS
  keeps, and the full cross table;
- by combine, by harvest session, by plot of a trial design (plot means, r and rank r, mean and largest difference)
  and by target rate (the treatment means DIFM fits);
- the agreement map, the yield distributions, the steps of each method and the plot means figure;
- `<tag>_methods_comparison.json` / `.csv`, `<tag>_methods_by_plot.csv`, `<tag>_methods_points.zip` (every processed
  point with both decisions and both yields) and `<tag>_methods_comparison_report.pdf`.

Both DIFM-ready files are complete uploads; the comparison says where the choice matters for the trial.

## 12. Reproducing a cleaning delivered before v2.4

Every cleaning delivered up to v2.3 used the v2.3 overlap and flow-delay model. `yield_clean.LEGACY_V23` restores it:

```json
{"filters": {"F8": {"footprint": "chord", "y_offset": false, "reference": "field", "min_threshold": 0}},
 "lag_stage": "output", "lag_axis": "ew_first"}
```

In the app every switch is in step 3: the F8 choices marked (v2.3) with Y_Offset off and the floor 0, and *Passes the
delay scan compares* = *east-west first (v2.3)* under *Flow-delay correction*. From the command line, save it as a
file and pass it with `--settings` (merged into the defaults like any settings file; put the other settings of the
delivered run in the same file); from Python,
`yield_clean.run(shp, out, settings=yield_clean.LEGACY_V23)` or the same keys merged into the run's settings. With it
the engine reproduces v2.3 record for record: on the seven trials of the overlap tests (T19, T20, T25, T22, T23, T29,
T30) the final engine in this mode and the untouched v2.3 engine give 0 differences in `Keep`, `Rem_By`, `Pass_Id`,
`Lag_rec`, `Overlap_f` and the output positions (E0 of section 13, re-checked on the final engine). Only the drawing
differs: the maps show the swept strips whatever the footprint (section 8), and no number depends on the drawing. The
switches can also be set one at a time:

| Setting | v2.4 default | v2.3 value | What it does |
|---|---|---|---|
| `filters.F8.footprint` | `"swept"` | `"chord"` | the strip between the header lines of consecutive readings, or the rectangle along the chord from the previous point (section 3) |
| `filters.F8.y_offset` | `true` | `false` | centre the strip `Y_Offset_f` ft to the right of travel (John Deere; Case IH logs about 0) |
| `filters.F8.reference` | `"local"` | `"field"` | every record of the pass interiors against local no-overlap controls of the same combine at the same edge distance, or each combine's whole no-overlap band (>= 500 points or >= 10 % of its records) |
| `filters.F8.min_threshold` | `0.05` | `0` | floor of the automatic threshold (not applied to a fixed threshold or to the fallback) |
| `filters.F8.local_radius_m` | `15` | not used | minimum radius of the local controls (m); the radius used is max(this, 1.5 header widths) |
| `filters.F8.edge_tol_m` | `4` | not used | largest difference of edge distance between a record and its controls (m) |
| `filters.F8.min_controls` | `5` | not used | fewest controls a record needs to enter the dose-response |
| `lag_stage` | `"output"` | `"output"` | where the flow delay is measured and applied: on the kept records after the cascade, moving the output geometry only; `"before_f7"` is the option that failed its pre-registered test (P5): after F6, every yield tied to its source position before F7 and F8 |
| `lag_axis` | `"dominant"` | `"ew_first"` | the passes the flow-delay scan compares: those of the axis the field was harvested in, or the E-W passes whenever E and W both hold >= 200 records |

The pass-interior rule (>= 15 alive records on both sides), the >= 30 matched records per band and the >= 30
no-overlap records with controls that the local reference needs are constants of the engine, not settings. A
settings file or a saved field (`field.json`) written before v2.4 holds none of these keys, so a run made from it now
cleans with the v2.4 defaults: add the keys above to reproduce what was delivered. The app opens such a field
with its result marked as the previous run and says why (the result's settings hold no `lag_axis`, a key every v2.4
run writes). The cleaning JSON of a v2.4 run
records what was used (`R["settings"]`, `R["f8"]["footprint"]`, `y_offset`, `reference_mode`, `floor_applied`,
`stop_kind`, `local`; `R["lag"]["stage"]`, `axis`, `n_orphans`), and the report states it in its F8 and flow-delay
lines.

## 13. Evidence for v2.4

The evidence ships with the app in `docs/overlap_v24/` (`README.md` there is the index): the pre-registration
`PREREG_v24.txt` with its SHA-256 (`PREREG_v24.sha256`), the evaluation report `EVALUATION_v24.md`, the synthesis of
overlap tests A-C in Portuguese (`SINTESE_testes_ABC_pt.md`) and the key figures.

**Design.** The pre-registration was written on 29 October 2026 before the v2.4 code existed and before any
after-number was computed (file 18:18, first engine run 18:26). Data: the SMS exports of the seven trials of the
overlap tests (Case IH AFS T19, T20, T25; John Deere GreenStar 4 T22, T23, T29, T30), default settings, no field of
interest. Configurations: `v23` = the new engine with the legacy switches, the v2.4 defaults, and one ablation per
change (`fp` swept footprint, `fp_off` + `Y_Offset`, `ref` local reference + floor together, `lag` flow delay before
F7/F8). An analyst produced each result and an independent verifier reproduced it with its own scripts; where the
verifier corrected a number, the corrected one is used. Intervals: 95 % percentile bootstrap over whole passes,
B = 2000, seed 2026.

| Item | Registered rule | Verdict | Key numbers |
|---|---|---|---|
| E0 | the legacy mode reproduces the live v2.3 engine on every record | **holds** | 0 differences in 7 of 7 trials (`_row`, `Keep`, `Rem_By`, `Pass_Id`, `Run_Id`, `Lag_rec`, positions; max difference 0 in `Overlap_f`) |
| P1 | swept footprint: the mean `Overlap_f` of the records in curves (chord direction changes >= 2 deg) falls in every trial and lands within +/- 2 pp of test C's value; refuted if it misses the band in >= 2 | **supported** | falls in 7 of 7 (paired -4.77 to -9.51 pp, every CI excludes 0); inside the band in 6 of 6 (largest distance +0.49 pp, T22) |
| P2 | the records only the chord wedge removed (v2.3 F8 removals not above the same threshold with the swept strip): CI of median yield / own-pass median includes 1 in >= 4 of 7 | **supported, at the minimum** | includes 1 in 4 of 7: T19 0.989 [0.948, 1.027], T22 1.035, T23 1.024, T30 0.974; wholly below in T20 0.891, T25 0.983 [0.970, 0.9996], T29 0.902; the wedge was 9.4-55.1 % of the v2.3 F8 removals |
| P3 | raster sensitivity: the F8 decisions that flip when the raster origin moves 0.125 m fall by >= 36 % in every trial; refuted if < 36 % in >= 2 | **supported** | 37.8-94.3 % fewer flips; T23 (45 -> 28 flips) is one flip from 36 %, and with the other reading of the share (flips over each footprint's own F8 removals) T22 and T23 would fall short and P3 would be refuted |
| P4 | `Y_Offset` (John Deere): the median `Overlap_f` of the narrowed records is lower with the offset; refuted if not lower in >= 2 of 4 | **supported** | lower in 4 of 4: T22 5.64 -> 0, T23 7.06 -> 0, T29 1.77 -> 0, T30 10.39 -> 0 %; the share above 5 % falls from 27.6-58.8 % to 7.7-8.8 % |
| P5 | flow delay before F7/F8: the end-of-pass deficit D5e <= 0.10 in T22, T23 and T25 | **refuted** | 0.126, 0.133, 0.331 (the CIs of T23 and T25 lie wholly above 0.10); T22's F8 threshold went 15 % -> 100 %; T29 shifted -5 (wrong sign), D5e 0.277 -> 0.312 |
| P6 | local edge-matched controls: the placebo (no-overlap records against their own controls) within 0.97-1.03 in every trial with >= 30 matched records | **supported** | 7 of 7 point estimates: T19 0.984, T20 0.989, T25 1.000, T22 1.000, T23 1.000, T29 1.004, T30 0.982 (evaluated engine); the CIs of T19, T20 and T30 reach outside the band. Re-checked on the final engine: 1.012, 0.997, 1.000, 0.998, 1.000, 0.994, 0.984, the same three CIs reaching outside |

**From the evaluated engine to the final one.** The evaluated v2.4 defaults had the flow delay before F7 and F8 and
local controls within 15 m on every record alive after F7, one combine per file. The final defaults follow the
evaluation's recommendation (its section 7: swept footprint, `Y_Offset`, local reference, 5 % floor and swept-strip
maps adopted; the flow delay back on the output) and add four things decided after it: the pass interiors as the dose
population, the combine key (machine column, SMS serial, Ops Center log), the radius max(15 m, 1.5 header widths) and
the dominant-axis flow-delay scan (an exploratory finding of the evaluation's section 5). The final engine was run on
the same seven exports with its defaults and with `LEGACY_V23`, and E0 and P6 were re-checked on those runs
(`results/final_recheck.json` in the evaluation's working folder): E0 holds (0 differences in 7 of 7), and P6 is
supported with the final controls (placebo inside 0.97-1.03 in 7 of 7; the 95 % CIs of T19 [0.932, 1.065], T20
[0.948, 1.066] and T30 [0.963, 1.002] reach outside the band, those of T25, T22, T23 and T29 lie inside). The table
itself is a set of runs, not a registered test. Mean = kept `Yld_Vol_Dr`; its change has a paired pass-bootstrap
CI that excludes 0 on T19 [-1.32, -0.13 %], T20 [-0.34, -0.03 %], T23 [+0.02, +0.22 %], T29 [-1.80, -0.84 %] and T30
[-2.14, -0.42 %] (descriptive). Figures `final_*` in `docs/overlap_v24/figs/`.

| Trial | Monitor | Records | Kept v2.3 -> v2.4 | Removed | F8 removed | F8 threshold v2.3 -> v2.4 | What set the v2.4 threshold (`stop_kind`) | Placebo (records) | Matched / dose population | Mean yield v2.3 -> v2.4 (bu/ac) | Shift v2.3 -> v2.4 (records) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T19 | Case IH | 33,017 | 22,055 -> 27,112 (+5,057) | 33.2 -> 17.9 % | 3,752 -> 1,696 | 5 % -> 5 % | 5-10 % band: 15 of 222 matched (`too_few`) | 1.012 (730) | 28.7 % | 72.73 -> 72.20 (-0.73 %) | 0 -> 0 |
| T20 | Case IH | 68,891 | 62,724 -> 63,292 (+568) | 9.0 -> 8.1 % | 3,067 -> 2,782 | 5 % -> 5 % | 5-10 % band: 0 of 496 matched (`too_few`) | 0.997 (726) | 13.8 % | 53.52 -> 53.44 (-0.16 %) | +2 -> +5 |
| T25 | Case IH | 51,181 | 43,625 -> 44,538 (+913) | 14.8 -> 13.0 % | 2,980 -> 2,582 | 10 % -> 5 % | 5-10 % band -3.62 % (`tolerance`) | 1.000 (8,535) | 33.6 % | 66.85 -> 66.84 (-0.01 %) | +3 -> +4 |
| T22 | John Deere | 33,947 | 30,877 -> 31,485 (+608) | 9.0 -> 7.3 % | 601 -> 225 | 15 % -> 5 % | floor; auto 2 %, 2-5 % band: 8 of 103 matched (`too_few`) | 0.998 (11,453) | 42.3 % | 68.48 -> 68.52 (+0.06 %) | +2 -> +2 |
| T23 | John Deere | 82,314 | 56,114 -> 56,516 (+402) | 31.8 -> 31.3 % | 862 -> 396 | 25 % -> 5 % | floor; auto 2 %, 2-5 % band: 28 of 252 matched (`too_few`) | 1.000 (14,684) | 29.3 % | 54.63 -> 54.69 (+0.11 %) | +2 -> +2 |
| T29 | John Deere | 78,887 | 60,481 -> 65,189 (+4,708) | 23.3 -> 17.4 % | 7,149 -> 3,957 | 10 % (fallback; auto 1 %) -> 5 % | floor; auto 2 %, 2-5 % band -12.0 % (`tolerance`) | 0.994 (5,155) | 9.6 % | 65.92 -> 65.06 (-1.31 %) | -5 -> +2 |
| T30 | John Deere | 27,210 | 22,067 -> 24,459 (+2,392) | 18.9 -> 10.1 % | 2,075 -> 201 | 5 % -> 5 % | 5-10 % band: 19 of 73 matched (`too_few`) | 0.984 (6,508) | 32.2 % | 59.36 -> 58.66 (-1.19 %) | 0 -> 0 |

Combine key and radius of the local controls: T19, T20 and T25 the display serial in the SMS dataset names (one
combine each; radius 17.8, 16.0 and 17.8 m); T23 and T29 the Ops Center log (4 combines each; 20.6 and 22.9 m); T22
and T30 neither (one combine; 20.6 and 18.3 m). With the raster origin moved by 0.125 m the final engine keeps 27,074
/ 63,297 / 44,599 / 31,495 / 56,495 / 65,233 / 24,426 records, the thresholds stay at 5 % (on T23 the scan then stops
on a -10.8 % drop instead of too few matched records) and the shifts stay the same except T29 (+2 -> 0); the F8
decisions that flip are 47-595 per trial (0.1-0.8 % of the records alive after F7), against 346-2,738 in v2.3.

**Limits, plainly.**

1. **In-sample.** The predictions came from tests A-C and their reviews on these same seven trials, so P1-P4 check
   that the engine reproduces the earlier analyses; they are not out-of-sample tests of the methods. One season, SMS
   exports only, 3 Case IH and 4 John Deere fields.
2. **The final configuration was not the one evaluated.** The pass interiors, the combine key, the radius and the
   dominant axis were decided after the pre-registration; only E0 and P6 were re-checked on the final engine (both
   hold, P6 with wide CIs on T19, T20 and T30). P1-P5 were not re-run on it, and the final-engine table is a set of
   runs, not a registered test.
3. **No machine column in any of the files.** The combine comes from the SMS serial or the Ops Center log, and T22 and
   T30 carry neither. **T29 has no time of day**, so the burn order between its 4 combines is file order (its
   `Y_Offset` side check was also the weakest: 79 % of the offsets point away from cut ground against 93-97 % on the
   other John Deere trials).
4. **Thin local controls.** Only 9.6-42.3 % of the dose population found controls (the 4 m edge tolerance usually
   excludes the adjacent parallel pass). The scan stopped because the next band had fewer than 30 matched records in 5
   of 7 trials (T19, T20, T22, T23, T30) and on a yield drop in 2 (T25, T29); the 5 % floor decided the threshold in 3
   of 7 (T22, T23, T29). So the 5 % threshold of T19, T20 and T30 is set by the 30-record rule, only T25's by a
   measured drop, and on the evaluated engine every deciding band's CI spanned the -3 % tolerance with half-widths of
   5-25 points. A 5 % threshold on every trial says more about the floor and the matched counts than about a measured
   dose-response; read `stop_kind` and the matched counts in the JSON or the report before trusting it.
5. **The flow-delay shift is fragile.** The dominant-axis rule was chosen after seeing these data; the r-gain > 0.01
   gate is not a meaningful test; on T29 the +2 records become 0 when the raster origin moves by 0.125 m (the
   evaluation's evidence for T29 points to +1..2 records or none; v2.3's -5 had the wrong sign).
6. **Raster resolution.** The 0.25 m raster still moves single decisions at thresholds of 10 % or less; the floor was
   never ablated alone, and `Y_Offset` was only tested on top of the swept footprint.
7. **No yield ground truth.** P2 and the mean-yield changes are ratios against own-pass or field medians. The mean
   kept yield falls 0.7-1.3 % on T19, T29 and T30; in the evaluation the newly kept records read like their own pass
   but lay nearer the edges and in lower-yield passes. Whether those edge yields are real cannot be settled with these
   data.
