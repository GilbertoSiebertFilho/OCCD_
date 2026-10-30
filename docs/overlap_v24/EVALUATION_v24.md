# OCCD v2.4 evaluation: pre-registered before/after test on seven 2026 trials

Date: 2026-10-29.
Folder: `v24_eval`, the evaluation's working folder (paths below are relative to it). The copy shipped with the app in `docs/overlap_v24/` holds this report, the pre-registration and the figures listed in its `README.md` (in `figs/`); the run tables, results and scripts stay in the working folder.

- **Pre-registration:** `PREREG_v24.txt`, SHA-256 `75687be2520d958a9eb31cd8ff639b8decd972b56efe373975123537e6c46f9b`. It matches `PREREG_v24.sha256`, and every analyst and verifier checked it. The file is dated 18:18; the first engine run started at 18:26.
- **Engine evaluated:** the dev engine (`occd_dev`), as it stood for the batch runs of 18:26-18:30 in `runs/`, plus 7 shifted v2.4 runs made at 18:46-18:49 with the unchanged `scripts/run_one.py`. The engine was modified again after the evaluation (section 6, first limit).
- **Method:** an analyst produced each result, and a verifier then reproduced it independently with its own scripts. Where the verifier corrected a number or a statement, this report uses the corrected one and marks it **(corrected in verification)**.
- **Decision rules** are applied exactly as registered. Anything not in the pre-registration is labelled **EXPLORATORY**.
- **CIs:** 95 % percentile bootstrap over passes (whole passes resampled), B = 2000, `numpy.default_rng(2026)` per trial, unless stated otherwise.

## Verdicts at a glance

| Item | Registered rule (short) | Verdict | Margin and fragility |
|---|---|---|---|
| E0 | v2.3 legacy mode reproduces live v2.3 on every record | **holds** | 0 differences in 7/7 trials |
| P1 | Mean overlap in curves falls in every trial; refuted if it misses the ±2 pp band around test C in >= 2 of 6 | **supported** | Falls in 7/7; inside the band in 6/6 (largest distance 0.49 pp) |
| P2 | Wedge records: CI of yield / own-pass median includes 1 in >= 4 of 7 | **supported** | Exactly 4/7. T25 misses 1 by 0.0004 |
| P3 | Flip share falls >= 36 %; refuted if < 36 % in >= 2 trials | **supported** | 0/7 below. T23 is at 37.8 %, one flip from 36 %. The verdict depends on the denominator |
| P4 | Median overlap lower with Y_Offset; refuted if not lower in >= 2 of 4 | **supported** | Lower in 4/4; share > 5 % falls in 4/4 |
| P5 | D5e <= 0.10 in T22, T23 and T25 | **refuted** | 0.126, 0.133, 0.331 |
| P6 | Placebo within 0.97-1.03 in every trial with >= 30 matched records | **supported** | 7/7 point estimates inside. The CIs of T19, T20 and T30 reach outside |

In short:
- The swept footprint, Y_Offset and the local placebo behave as predicted.
- Moving the flow delay before F7/F8 does not. On T29 the engine's flow-delay scan applies a shift of the wrong sign (-5 records).
- Section 7 gives a recommendation for each change.

## 1. What changed

v2.4 changes F8 (overlap) and the flow-delay step. Each change has a switch. The table names it and the ablation configuration that tests it alone against v2.3 (`scripts/run_one.py`).

| Change | Setting (v2.4 / v2.3) | Ablation config |
|---|---|---|
| Swept-strip footprint: the strip between the header lines of consecutive readings replaces the rectangle back along the chord | `filters.F8.footprint` = `swept` / `chord` | `fp` |
| Y_Offset: the strip is centred `Y_Offset_f` ft to the right of travel | `filters.F8.y_offset` = `true` / `false` | `fp_off` (on top of `fp`) |
| Local edge-matched reference: controls of the same combine, another pass, <= 15 m away, edge distance within 4 m, >= 5 controls. It replaces the field-wide no-overlap band | `filters.F8.reference` = `local` / `field` | `ref` (together with the floor) |
| 5 % floor on the automatic threshold | `filters.F8.min_threshold` = `0.05` / `0` | `ref` (together with the local reference) |
| Flow delay measured after F6 and applied before F7/F8, instead of after the cascade on the output geometry only | `lag_stage` = `before_f7` / `output` | `lag` |
| Maps draw the swept strips | drawing only; no number depends on it | none (maps in section 4) |

Configurations: `v23` = `LEGACY_V23` (all legacy switches); `v24` = all new defaults.

Two changes were never ablated alone:
- The local reference and the 5 % floor are switched on together in `ref`.
- Y_Offset is only tested on top of the swept footprint.

Data: the 7 SMS exports of the overlap tests, with default settings and no AOI.
- Case IH AFS: T19, T20, T25.
- John Deere GS4: T22, T23, T29, T30.

## 2. E0: identity of the legacy mode

**Result: holds.** In LEGACY_V23 mode the dev engine (`dev_v23`) reproduces the untouched v2.3 engine (`v23_v23`) record for record in all 7 trials:
- 0 differences in `_row`, `Keep`, `Rem_By`, `Pass_Id`, `Run_Id`, `Lag_rec` and `_machine`.
- Maximum absolute difference 0 in `Overlap_f`, `_gx`, `_gy`, `_x`, `_y` and `Yld_Vol_Dr`, with 0 NaN mismatches.
- Cascade counts, F8 thresholds, dose tables and lag scans are identical.

The verifier also found that `v23_v23` equals test C's historical live-v2.3 tables record by record (`_row`, `Keep`, `Rem_By`, `Overlap_f`). Because E0 holds, P1-P6 were evaluated.

v2.3 cascade (records removed per filter; F0 = F6 = 0 in every trial):

| Trial | n | F1 | F2 | F3 | F4 | F5 | F7 | F8 | F9 | F10 | F11 | F5b | Kept | F8 threshold | Lag applied |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T19 | 33,017 | 125 | 2,071 | 122 | 35 | 1 | 486 | 3,752 | 28 | 246 | 201 | 3,895 | 22,055 | 5 % | 0 |
| T20 | 68,891 | 251 | 38 | 208 | 20 | 18 | 648 | 3,067 | 12 | 958 | 284 | 663 | 62,724 | 5 % | +2 |
| T25 | 51,181 | 471 | 1,029 | 105 | 100 | 35 | 768 | 2,980 | 11 | 497 | 219 | 1,341 | 43,625 | 10 % | +3 |
| T22 | 33,947 | 207 | 430 | 92 | 18 | 9 | 606 | 601 | 5 | 398 | 125 | 579 | 30,877 | 15 % | +2 |
| T23 | 82,314 | 19,419 | 530 | 304 | 17 | 34 | 1,404 | 862 | 7 | 867 | 620 | 2,136 | 56,114 | 25 % | +2 |
| T29 | 78,887 | 387 | 269 | 409 | 116 | 78 | 2,676 | 7,149 | 221 | 17 | 2,294 | 4,790 | 60,481 | 10 % (fallback; auto 1 %) | -5 |
| T30 | 27,210 | 175 | 24 | 100 | 62 | 29 | 684 | 2,075 | 59 | 31 | 880 | 1,024 | 22,067 | 5 % | 0 |

Sources: `results/E0_P1_P2_P3_geometry_e0.json`, `results/verify_E0_P1_P2_P3_geometry_e0.json`.

## 3. The predictions

### P1: overlap in curves with the swept footprint (ablation `fp` vs `v23`)

**Registered rule.**
- Population: records alive after F7 whose chord direction changes by >= 2 deg from the previous chord. This is test C's definition (`overlap_tests/testC_geometry/scripts/analyse.py`).
- Prediction: the mean `Overlap_f` falls in every trial and lands within ±2 pp of test C's swept-strip value. The values are T19 7.6, T25 13.6, T22 3.5, T23 5.8, T29 5.1 and T30 5.2 %; T20 must fall, with no value given.
- Refuted if it does not fall in some trial, or misses the band in >= 2 trials.
- The rule is judged on point estimates.

The population equals test C's record for record (0 differences in the curve flag and the alive-after-F7 flag).

| Trial | n | v2.3 chord, mean % [CI] | Swept, mean % [CI] | Paired difference, pp [CI] | Test C value | Distance |
|---|---|---|---|---|---|---|
| T19 | 698 | 15.03 [10.61, 29.31] | 7.92 [3.31, 22.58] | -7.11 [-7.82, -5.90] | 7.6 | +0.32 |
| T20 | 351 | 28.09 [20.47, 48.21] | 23.32 [15.38, 44.57] | -4.77 [-5.74, -3.16] | none | n/a |
| T25 | 1,055 | 23.08 [20.54, 26.01] | 13.57 [10.68, 17.07] | -9.51 [-10.56, -8.45] | 13.6 | -0.03 |
| T22 | 1,363 | 12.86 [11.33, 15.49] | 3.99 [2.33, 7.87] | -8.87 [-9.68, -7.08] | 3.5 | +0.49 |
| T23 | 2,244 | 14.40 [12.39, 17.63] | 6.20 [3.88, 10.02] | -8.20 [-9.04, -7.07] | 5.8 | +0.40 |
| T29 | 9,793 | 12.21 [11.31, 13.26] | 5.34 [4.31, 6.55] | -6.88 [-7.27, -6.48] | 5.1 | +0.24 |
| T30 | 1,198 | 10.53 [7.00, 16.49] | 5.47 [1.64, 12.06] | -5.06 [-5.51, -4.36] | 5.2 | +0.27 |

**Verdict: supported.** The mean falls in 7 of 7 trials, and every paired CI excludes 0. It lands inside the band in 6 of 6 trials.

Notes:
- **(corrected in verification)** The analyst wrote that the engine strip reads "0.03-0.49 pp higher" than test C. Against test C's exact swept-strip means (7.626, 13.555, 3.509, 5.824, 5.069, 5.249), it reads 0.01-0.48 pp higher in all 6 trials. The -0.03 for T25 is against the rounded registered value 13.6. The band test is unaffected.
- The CIs of the means are wide because a few passes dominate overlap in curves. The paired differences are tight.
- The engine's strip is perpendicular to the centred chord. Test C used the logged heading plus grid convergence, which explains the small offset from test C.

EXPLORATORY: the same measure for the full v2.4 config:

| Trial | Mean % [CI] |
|---|---|
| T19 | 7.92 [3.31, 22.58] |
| T20 | 17.14 [10.47, 31.87] |
| T25 | 13.56 [10.68, 17.06] |
| T22 | 1.59 [0.97, 2.94] |
| T23 | 1.73 [1.19, 2.58] |
| T29 | 3.24 [2.55, 4.06] |
| T30 | 1.08 [0.44, 1.98] |

- On John Deere, Y_Offset lowers the mean a further 2.1-4.5 pp below `fp`.
- In T20 the +4 flow delay lowers it a further 6.2 pp, because `Overlap_f` is then taken at the source position.

Figure: `figs/E0_P1_P2_P3_geometry_P1_P2_P3.png`, left panel.

### P2: the predecessor wedge (ablation `fp`, threshold held at the v2.3 field threshold)

**Registered rule.**
- Population: records removed by F8 in v2.3 and not above the same threshold with the swept footprint.
- Prediction: the CI of their median yield / own-pass median includes 1 in >= 4 of 7 trials.
- Refuted if the CI lies wholly below 1 in >= 4 trials.
- Own-pass median: the median of the v2.3-kept records of the same pass, as in test C H2b. The pre-registration does not define it.

**(corrected in verification) Population sizes.** The analyst's counts covered only records with a finite ratio. The registered population is larger. The extra records sit in passes with no v2.3-kept record, so they have no own-pass median and drop out of the statistic, as they did in test C. The medians, CIs and verdict are unchanged.

| Trial | Registered population | Share of v2.3 F8 removals | Share of all records | Records with an own-pass median | Median ratio [CI] | CI vs 1 |
|---|---|---|---|---|---|---|
| T19 | 2,068 | 55.1 % | 6.26 % | 2,036 | 0.989 [0.948, 1.027] | includes |
| T20 | 289 | 9.4 % | 0.42 % | 289 | 0.891 [0.829, 0.999] | wholly below |
| T25 | 992 | 33.3 % | 1.94 % | 992 | 0.983 [0.970, 0.9996] | wholly below |
| T22 | 261 | 43.4 % | 0.77 % | 250 | 1.035 [0.985, 1.059] | includes |
| T23 | 112 | 13.0 % | 0.14 % | 107 | 1.024 [0.901, 1.118] | includes |
| T29 | 2,899 | 40.6 % | 3.67 % | 2,775 | 0.902 [0.860, 0.935] | wholly below |
| T30 | 652 | 31.4 % | 2.40 % | 585 | 0.974 [0.887, 1.086] | includes |

**Verdict: supported, at the minimum count.** The CI includes 1 in 4 trials (T19, T22, T23, T30) and lies wholly below 1 in 3 (T20, T25, T29). The refutation condition (>= 4 below) is not met.

Notes:
- **CI method.** The CIs use test C's weighted lower quantile. The verifier's interpolated median gives T20 [0.830, 0.999], T23 [0.901, 1.125] and T30 [0.889, 1.086]. No call changes.
- **Gap to test C.** Like for like, the counts are 2,068 vs 2,088 (T19) and 2,899 vs 3,059 (T29). The strip direction explains 20 and 160 records. The 32 and 124 records without an own-pass median explain the rest **(corrected in verification)**.
- **Sensitivity (not registered).** All of these would still give "supported":
  - Own-pass median of `fp`-kept records: 4 includes.
  - Median of all positive yields in the pass: 6 includes.
  - Resampling only the passes that hold population records: 5 includes, because T25 becomes [0.969, 1.0009].
- **Fragility.** In T20, T25 and T29 the wedge records yield below their pass. Part of what the swept footprint keeps there may be real overlap or the pass-start transient. T29's burn order between its 4 combines is also uncertain.
- At the same threshold, the swept footprint adds a few removals of its own: 13, 5, 38, 38, 37, 121 and 5 records.

EXPLORATORY: with the v2.4 overlap instead of `fp`, the CI includes 1 in the same 4 of 7 trials (T19, T22, T23, T30).

Figure: `figs/E0_P1_P2_P3_geometry_P1_P2_P3.png`, middle panel. Its n labels are the records with an own-pass median, not the registered population.

### P3: raster sensitivity (ablation `fp` vs `v23`, origin moved 0.125 m in x and y)

**Registered rule.**
- Count the records whose F8 decision at the v2.3 field threshold flips when the raster origin moves.
- Prediction: the flip share falls by >= 36 % relative to v2.3 in every trial.
- Refuted if it falls by < 36 % in >= 2 trials.
- The pre-registration does not give the denominator of the "flip share". Before computing, the analyst fixed it as the records alive after F7. That set is identical for both footprints and both origins, so the fall equals the fall in flip counts. This is the basis on which the 36 % was derived (review C: 1 - 29/45 in T23).

| Trial | Flips v2.3 → swept | Flip share, % of alive after F7 | Relative fall [CI] |
|---|---|---|---|
| T19 | 2,738 → 155 | 9.07 [7.32, 11.02] → 0.51 [0.26, 0.83] | 94.3 % [90.7, 96.9] |
| T20 | 346 → 57 | 0.51 → 0.084 | 83.5 % [75.8, 93.7] |
| T25 | 1,217 → 137 | 2.50 → 0.28 | 88.7 % [78.3, 96.6] |
| T22 | 115 → 62 | 0.35 → 0.19 | 46.1 % [20.8, 86.0] |
| T23 | 45 → 28 | 0.074 → 0.046 | 37.8 % [-19.2, 69.1] |
| T29 | 854 → 250 | 1.14 → 0.33 | 70.7 % [61.8, 78.3] |
| T30 | 394 → 31 | 1.51 → 0.12 | 92.1 % [85.3, 97.2] |

**Verdict: supported.** No trial falls short of 36 %.

The margin is thin where it matters:
- T23 clears 36 % by 1.8 pp, which is one flip: 29 flips instead of 28 would give 35.6 %. One trial below 36 % would still not meet the refutation condition, which needs >= 2.
- The CIs of T22 and T23 extend far below 36 %.
- With the other reading of the share (flips over each footprint's own F8 removals), T22 (14.3 %) and T23 (31.8 %) fall short, and P3 would be refuted. That reading is not the one the 36 % was derived from. The verifier agrees with this assessment.

EXPLORATORY (raster):
- **16-origin sweep** (shifts 0, 1/16, 1/8 and 3/16 m in x and y). Range of the fall in flips at the 15 other origins (min / median / max):

  | Trial | Min | Median | Max |
  |---|---|---|---|
  | T19 | 91 % | 94 % | 95 % |
  | T20 | 82 % | 85 % | 88 % |
  | T25 | 81 % | 90 % | 91 % |
  | T22 | 39 % | 50 % | 62 % |
  | T23 | 29 % | 47 % | 65 % |
  | T29 | 69 % | 74 % | 77 % |
  | T30 | 87 % | 92 % | 94 % |

  T23 falls below 36 % at 1 of 15 origins. The registered 0.125 m shift is the worst case for v2.3 flips in T19, T25 and T30.
- **The automatic threshold itself moves with the origin.** Engine runs at origins 0 and 0.125 m:
  - v2.3 T22: 15 → 10 %.
  - v2.3 T23: 25 → 15 %.
  - `fp` T30: 2 → 5 %.
  - v2.4 T23: 5 → 10 %.

  Over 16 origins the thresholds were:
  - v2.3 T22: 10 % at 4 origins, 15 % at 12.
  - v2.3 T23: 10 % at 3, 15 % at 11, 25 % at 1, 100 % at 1. The engine's 25 % for v2.3 T23 appears at only 1 of the 16 origins.
  - `fp` T30: 2 % at 10, 5 % at 5, 10 % at 1.

  The threshold moves whenever the deciding band sits within about 1-2 pp of the -3 % tolerance.
- **Band-value noise.** The SD over the 16 origins is 0.2-0.65 pp per trial (median over bands), up to 1.8 pp. The swept footprint does not reduce this noise, although it removes most of the decision flips.
- **v2.4 flips** at the v2.3 threshold: 154, 50, 137, 60, 10, 235 and 47 records. At v2.4's own thresholds the engine's decisions flip in 38, 50, 361, 85, 244, 621 and 23 records. For T23 the threshold itself moved.

Figures:
- `figs/E0_P1_P2_P3_geometry_P1_P2_P3.png`, right panel.
- `figs/E0_P1_P2_P3_geometry_dose_vs_raster_origin.png`.

Sources: `results/E0_P1_P2_P3_geometry*.json`, `results/verify_E0_P1_P2_P3_geometry*.json`.

### P4: Y_Offset (John Deere T22, T23, T29, T30; ablation `fp_off` vs `fp`)

**Registered rule.**
- Population: records alive after F7 with logged width < 0.95 × the trial's full width and |Y_Offset| > 1 ft.
- Prediction: the median `Overlap_f` is lower with the offset in every JD trial, and the share above 5 % falls.
- Refuted if the median is not lower in >= 2 of the 4.
- The registration gives no refutation clause for the share. Before computing, the analyst fixed this mapping: supported = median lower in 4/4 and share lower in 4/4; refuted = median not lower in >= 2; otherwise inconclusive.

**(corrected in verification) Full width.** The pre-registration does not define "full width". The evidence scripts define it as the machine's maximum logged width (`testA_bias/scripts/burn.py`, `prereg.py`, `testA_review/scripts/run_review_engine.py`), which is 45 / 45 / 50 / 40 ft here.

The analyst instead used the modal width alive after F7 (44.5 / 44.5 / 50 / 39.5 ft) and wrote that this "follows the registration". It is the analyst's own operationalisation. This report gives the evidence-script definition first; both give the same verdict. T29 and T30 have identical populations under both definitions.

| Trial (definition) | n (passes) | Median, fp → fp_off, % [CI] | Paired difference [CI] | Share > 5 %, fp → fp_off [CI] | Paired difference [CI] |
|---|---|---|---|---|---|
| T22 (max width) | 2,106 (35) | 5.64 [4.19, 6.77] → 0.00 [0, 0] | -5.64 [-6.77, -4.19] | 56.7 [39.7, 73.6] → 8.5 [4.7, 15.5] | -48.3 [-66.9, -28.8] |
| T23 (max width) | 2,993 (82) | 7.06 [4.17, 12.01] → 0.00 [0, 0] | -7.06 [-12.01, -4.17] | 58.8 [43.0, 73.0] → 8.8 [5.7, 13.5] | -50.0 [-65.0, -31.7] |
| T29 (both) | 13,666 (332) | 1.77 [0.00, 3.23] → 0.00 [0, 0] | -1.77 [-3.23, 0.00] | 27.6 [22.2, 33.9] → 8.8 [6.9, 11.2] | -18.8 [-24.5, -13.9] |
| T30 (both) | 1,905 (34) | 10.39 [0.00, 22.23] → 0.00 [0, 0] | -10.39 [-22.23, 0.00] | 57.2 [27.3, 79.3] → 7.7 [4.4, 12.6] | -49.4 [-70.2, -20.9] |
| T22 (modal width) | 1,889 (35) | 5.94 [4.59, 7.39] → 0.00 | -5.94 [-7.39, -4.59] | 62.0 [45.6, 77.0] → 8.5 [4.8, 16.2] | -53.5 [-70.8, -33.9] |
| T23 (modal width) | 2,642 (81) | 8.76 [4.88, 13.89] → 0.00 | -8.76 [-13.89, -4.88] | 65.0 [49.3, 77.6] → 9.0 [5.8, 14.1] | -56.0 [-70.1, -38.0] |

**Verdict: supported** under either definition. The median is lower in 4 of 4 trials and the share above 5 % falls in 4 of 4.

Notes:
- With the offset, the median is exactly 0 in all four trials, a degenerate CI.
- In T29 and T30 the CI of the paired median difference reaches 0. There, "median lower" rests on the point estimate; the registered rule uses no CI.
- The share differences exclude 0 in all four trials.
- T22 and T30 carry the population in only 34-35 passes, so their CIs may under-cover.

EXPLORATORY (Y_Offset geometry; `results/P4_y_offset*.json`):
- **Records with |Y_Offset| > 1 ft** (all records): T22 2,659 (7.8 %), T23 5,787 (7.0 %), T29 23,481 (29.8 %), T30 2,449 (9.0 %). Most other records carry ±0.25 ft.
- **Offset vs half the narrowing.** |Y_Offset| is within 1 ft of half the narrowing, (W_full - W) / 2, for 93.1 / 84.8 / 90.3 / 99.1 % of narrowed records. The median residual is +0.25 ft, consistent with the modal width being one 0.5-ft section short of the physical header. Figure: `figs/P4_yoffset_vs_half_narrowing.png`.
- **Sign against the side of already-cut ground**, under the convention "+ = right of travel" (the engine and SMS convention). The share of records whose offset points away from the cut side:

  | Trial | Share away from cut side [CI] | Records classified |
  |---|---|---|
  | T22 | 97.1 % [85.5, 100] | 653 |
  | T23 | 95.4 % [88.4, 99.5] | 1,537 |
  | T29 | 79.1 % [71.3, 85.6] | 3,582 |
  | T30 | 93.2 % [76.0, 99.9] | 1,106 |

  T29 is lowest, consistent with its uncertain burn order: 4 combines share one machine key. The verifier did not re-derive this check.
- **Scale sweep.** Every strip was re-burnt with s × Y_Offset. Mean `Overlap_f` of the P4 population (modal-width population):

  | Trial | s = -1 | s = 0 | s = 0.5 | s = 1 | s = 1.5 |
  |---|---|---|---|---|---|
  | T22 | 21.0 | 13.5 | 8.8 | 2.4 | 6.4 |
  | T23 | 33.0 | 21.3 | 13.0 | 2.0 | 6.1 |
  | T29 | 13.5 | 8.9 | 5.8 | 2.4 | 4.5 |
  | T30 | 33.7 | 22.4 | 13.9 | 1.4 | 3.9 |

  - **(corrected in verification)** T23 at s = 0 is 21.3 %, not 21.4 %.
  - The minimum is at s = 1 in every trial, and the opposite sign raises overlap. So Y_Offset is in feet, positive to the right of travel, and the full offset is the right magnitude.
  - The verifier re-derived s = 0 and s = 1 only.
  - Figures: `figs/P4_offset_scale_sweep.png`, `figs/P4_map_T23_narrowed_pass.png`, `figs/P4_map_T30_narrowed_pass.png`.
- **Fallback.** With the field reference, `fp_off` falls back to the 10 % threshold on T23, T29 and T30, where the auto rule gives 1 %. With `fp` the thresholds were T23 2 %, T29 5 % and T30 2 % **(corrected in verification: the analyst had T29 and T30 swapped)**.

  The 0-2 % band against the 0 band, `fp` → `fp_off`:

  | Trial | fp | fp_off | fp_off pass-bootstrap CI | Resamples failing -3 % |
  |---|---|---|---|---|
  | T22 | -1.90 % | -2.76 % | (not reported) | (not reported) |
  | T23 | -1.82 % | -3.36 % | [-5.32, -1.35] | 65 % |
  | T29 | +3.36 % | -5.75 % | [-9.95, -1.58] | 90 % |
  | T30 | -1.96 % | -4.04 % | [-6.76, -1.03] | 75 % |

  The tolerance is -3 %. Under `fp` the band also straddled -3 % (it fails in 14-27 % of resamples), so the 2 % threshold of `fp` was fragile too.

  Mechanism: the offset moves 72-87 % of the `fp` 0-2 % band into the 0 band. These are full-width interior records whose phantom overlap was a section already shut on the neighbour's side. The band is left with truly overlapped, narrowed records near the harvested edge. Those records read -6 to -14 % against the field reference but 0.97-1.00 of their own pass, which is the edge gradient. Figures: `figs/P4_dose_fp_vs_fp_off.png`, `figs/P4_band02_movers.png`.

  On the same `fp_off` overlaps, the local reference puts the 0-2 % band at -0.02 / +0.52 / +3.65 / -1.62 %. It passes in all four trials, and the auto thresholds become 5 / 2 / 5 / 10 %.

  This is a hypothesis, not a tested result: use Y_Offset with the local reference, not with the field reference.
- **Side effect of the fallback.** `fp_off` removes far fewer records by F8 than `fp`:

  | Trial | F8 removals, fp_off | F8 removals, fp | Note |
  |---|---|---|---|
  | T23 | 166 | 3,329 | fallback threshold |
  | T29 | 1,923 | 7,985 | fallback threshold |
  | T30 | 99 | 2,199 | fallback threshold |
  | T22 | 389 | 2,283 | same 2 % threshold; the overlap itself fell |

Sources: `results/P4_y_offset*.json`, `results/verify_P4_y_offset*.json`.

### P5: flow delay before F7/F8 (ablation `lag`: lag stage only, v2.3 footprint)

**Registered rule.**
- D5e = 1 - the mean of the first 5 values of Q_end.
- Q_end = the median over passes of y / own-pass interior median over the last 15 records alive after F8 (passes with >= 60 such records), divided by the median of the interior ratios (records 20..n-21).
- Measured on the engine's real cascade.
- Prediction: D5e <= 0.10 in T22, T23 and T25. Refuted if > 0.10 in any of them.

The analyst took the interior as in `x_review.py` (0-based 19..n-21). The literal 1-based reading changes D5e by at most 0.0002 (verifier).

| Trial | Shift applied, v23 / lag | D5e v23 [CI] | D5e lag [CI] | D5s v23 [CI] | D5s lag [CI] | Passes |
|---|---|---|---|---|---|---|
| **T22** | +2 / +3 | 0.188 [0.150, 0.218] | **0.126** [0.083, 0.156] | 0.049 [0.009, 0.081] | 0.040 [0.002, 0.077] | 88 / 90 |
| **T23** | +2 / 0 | 0.133 [0.107, 0.169] | **0.133** (identical) | 0.095 [0.064, 0.122] | identical | 184 |
| **T25** | +3 / 0 | 0.331 [0.277, 0.379] | **0.331** (identical) | 0.006 [-0.024, 0.034] | identical | 117 |
| T19 | 0 / 0 | 0.061 [-0.014, 0.144] | identical | -0.044 [-0.091, 0.002] | identical | 75 |
| T20 | +2 / +4 | 0.585 [0.561, 0.613] | 0.270 [0.211, 0.321] | 0.183 [0.144, 0.218] | 0.265 [0.232, 0.298] | 99 |
| T29 | -5 / -5 | 0.277 [0.243, 0.310] | 0.312 [0.270, 0.343] | 0.075 [0.049, 0.101] | 0.049 [0.023, 0.073] | 319 / 316 |
| T30 | 0 / 0 | 0.173 [0.086, 0.257] | identical | 0.142 [0.082, 0.252] | identical | 91 |

**Verdict: refuted.** D5e is above 0.10 in all three registered trials. The CIs of T23 and T25 lie wholly above 0.10, so the verdict does not depend on T22.

Notes:
- **T23 and T25: the auto rule applied no shift.** The before-F7 scan found a best lag of -1, so the rule applied 0, and the `lag` run equals `v23`. In these two trials the refutation tests the implemented change: where and how the lag is measured.
- **The mechanism with the review's lags also misses the bound (EXPLORATORY).** Fixed-shift engine runs (`tmp/p5_runs`):

  | Trial | Shift s | F8 | D5e [CI] |
  |---|---|---|---|
  | T22 | +3 | auto (= config `lag`) | 0.126 |
  | T22 | +3 | held at 15 % | 0.105 [0.064, 0.135] |
  | T22 | +2 | held at 15 % | 0.179 |
  | T22 | +2 | auto | 0.198 |
  | T23 | +2 | auto | 0.129 [0.102, 0.164] |
  | T25 | +3 | auto | 0.1001 [0.063, 0.132] |

  T25 misses the bound by 0.0001. The review's X3 estimate of 0.06-0.07 was optimistic, mainly because X3 also dropped 2 more end yields.
- **(corrected in verification: labelling)** The paired lag-minus-v23 changes were not registered and are EXPLORATORY: T20 -0.315 [-0.361, -0.272] and T29 +0.035 [+0.015, +0.052], which is worse.
- **T22 side effect.** With the lag, T22's F8 threshold goes from 15 % to 100 %, so F8 removes 0 records instead of 601. Section 5 explains why.
- **Orphans in config `lag`** (records whose source lies outside their pass):

  | Trial | Total | Removed by F7 | Already removed by F0-F6 | Removed only because they were orphans |
  |---|---|---|---|---|
  | T20 | 441 | 383 | 58 | 168 |
  | T22 | 311 | 290 | 21 | 92 |
  | T29 | 2,313 | 1,894 | 419 | 213 |
  | Other trials | 0 | 0 | 0 | 0 |

**Registered T29 check (no prediction).**
- The scan's best lag is +5 records both before F7 (config `lag`: r 0.268 at lag 0, 0.442 at the best) and after the cascade (config `v23`: r 0.608 to 0.650).
- The engine applies -5 in both stages (output position of record i = position i - 5). That is the opposite sign to the pass-end analysis, which favoured s = +5.
- D5e in T29 rises from 0.277 to 0.312. Section 5 continues this check.

Figures: `figs/p5_d5.png`, `figs/p5_t29_scan_and_d5.png`.

Sources: `results/p5*.json`, `results/verify_P5_lag_T29*.json`.

### P6: local edge-matched controls (config `v24`)

**Registered rule.**
- Placebo = the median ratio of the no-overlap records (`Overlap_f` = 0, alive after F7) to their own local controls: same combine, another pass, <= 15 m, |edge distance difference| <= 4 m, >= 5 controls.
- Prediction: within 0.97-1.03 in every trial with >= 30 matched no-overlap records. Refuted otherwise.
- Judged on the point estimate.

The analyst and the verifier both re-implemented the edge distance and the controls. Both reproduce the engine's `_edge_m` and `_f8_ratio` exactly.

| Trial | Placebo [CI] | Matched no-overlap records | Passes |
|---|---|---|---|
| T19 | 0.984 [0.931, 1.055] | 449 | 32 |
| T20 | 0.989 [0.948, 1.061] | 821 | 51 |
| T25 | 1.000 [0.988, 1.010] | 9,467 | 104 |
| T22 | 1.000 [0.986, 1.012] | 12,750 | 95 |
| T23 | 1.000 [0.992, 1.006] | 15,504 | 200 |
| T29 | 1.004 [0.979, 1.026] | 2,796 | 187 |
| T30 | 0.982 [0.963, 1.000] | 7,902 | 104 |

**Verdict: supported.** All 7 trials can be evaluated, and all 7 point estimates lie within 0.97-1.03.

Under a stricter, non-registered reading ("CI wholly inside 0.97-1.03"), T19, T20 and T30 would not pass. T19 and T20 have CIs about ±6 points wide, so a 3 % bias there would go undetected.

These T19 numbers come from the engine of the batch runs; see section 6 for the later engine change.

EXPLORATORY (P6 details; `results/P6_overall*.json`, `results/verify_P6_overall*.json`):
- **The placebo set is mostly interior.** Records more than 60 m from the edge make up most of it: T19 290 of 449, T25 8,673 of 9,467, T22 11,285 of 12,750, T23 13,212 of 15,504.
- **Near the edge the placebo is off in both directions:**
  - Low: T23 15-30 m 0.786 [0.687, 0.898] (64 records); T19 15-30 m 0.879 (19); T30 0-15 m 0.825 (278); T20 0-15 m 0.859 (5).
  - High **(corrected in verification: the analyst listed only the low ones)**: T23 0-15 m 1.391 (64 records); T29 0-15 m 1.147 (48); T19 0-15 m 1.149 (7).
- **Distance of the deciding bands from the edge (corrected in verification).** The analyst wrote that the overlapped records in the deciding bands sit 16-30 m from the edge (median). That does not hold for:
  - T29: the 5-10 % band lies 66 m from the edge.
  - T25: 44 m.
  - T22: 33 m for its records above 5 %.
- **Few records have controls.** Matched share of the dose population:

  | Trial | Matched share of dose population |
  |---|---|
  | T19 | 25 % |
  | T20 | 15 % |
  | T25 | 35 % |
  | T22 | 44 % |
  | T23 | 28 % |
  | T29 | 6.8 % |
  | T30 | 34 % |

  - Only 2.3-5 % of the no-overlap records have controls in T19, T20 and T29.
  - **(corrected in verification)** The matched share is 1.5-37 % in the 5-10 % band and 1.5-77 % across the 5-35 % bands.
  - The cause is the 4 m edge tolerance. Within 15 m, the median |edge difference| between a record and its other-pass candidates is 9.9-12.0 m **(corrected in verification; the analyst wrote 8-12 m)**. That is about one header width, so the adjacent parallel pass is usually excluded.
- **What set the v2.4 threshold.**
  - The "< 30 matched records" stop rule decided it in 4 of 7 trials:
    - T19: 5-10 % passes at -0.42 % [-8.7, +14.0] on 45 of 310 records; 10-15 % has 11 of 118; threshold 10 %.
    - T20: 5-10 % has 8 of 538; 5 %.
    - T22: 5-10 % has 19 of 73; 5 %.
    - T30: 5-10 % passes at +21.3 % [-5.7, +35.4] on 38 of 102; 10-15 % has 12 of 45; 10 %.
  - An apparent yield drop decided it in the other 3:
    - T25: 5-10 % at -4.74 % [-10.0, +0.2]; 5 %.
    - T29: 5-10 % at -3.38 % [-11.1, +7.1]; 5 %.
    - T23: 2-5 % at -5.80 % [-11.4, +2.1]; the auto rule gives 2 %, which the floor raises to 5 %.
  - Every deciding band has a CI that spans the -3 % tolerance, with half-widths of 5-25 points.
  - **(corrected in verification)** The analyst's summary "in practice the threshold comes from the < 30 rule and the floor" conflicts with its own finding that a drop decided T25, T29 and T23's auto 2 %. The correct statement: the stop rule decided 4 trials, a drop whose CI spans the tolerance decided 3, and the floor bound in 1 (T23).
- **Same-combine sensitivity.** None of the 7 files has a machine column, so the engine runs every trial as one machine, M1. Only T23 and T29 hold several combines, 4 logs each. Enforcing the same log: T23 1.000 [0.992, 1.006] (15,069 records, 188 passes); T29 1.012 [0.945, 1.114] (381 records, 71 passes). Both are inside the band, but T29 becomes much less precise.
- **Fallback in `ref`.** Config `ref` (chord footprint + local reference) falls back to the field reference in T19 (placebo_n 14) and T29 (20).

Figure: `figs/P6_placebo_and_local_dose_v24.png` (placebo and per-band local dose-response).

## 4. Reported without prediction: thresholds, kept records, mean yield, coverage

Sources: `results/P6_overall_table.json`, reproduced exactly by `results/verify_P6_overall_table.json`.

**4a. F8 threshold used.** Abbreviations: auto = the automatic rule; fb = fallback; floor = the 5 % floor applied; loc = local reference; field = field reference.

| Trial | v23 | fp | fp_off | lag | ref | v24 |
|---|---|---|---|---|---|---|
| T19 | 5 % | 5 % | 5 % | 5 % | 5 % (field: local placebo_n 14) | 10 % loc |
| T20 | 5 % | 5 % | 5 % | 5 % | 10 % loc | 5 % loc |
| T25 | 10 % | 5 % | 5 % | 10 % | 15 % loc | 5 % loc |
| T22 | 15 % | 2 % | 2 % | 100 % (F8 removes 0) | 5 % loc | 5 % loc |
| T23 | 25 % | 2 % | 10 % fb (auto 1 %) | 25 % | 5 % loc | 5 % loc, floor (auto 2 %) |
| T29 | 10 % fb (auto 1 %) | 5 % | 10 % fb (auto 1 %) | 10 % fb (auto 1 %) | 10 % fb (field: placebo_n 20) | 5 % loc |
| T30 | 5 % | 2 % | 10 % fb (auto 1 %) | 5 % | 5 % loc | 10 % loc |

**4b. Kept records (change vs v2.3).**

| Trial | v23 | fp | fp_off | lag | ref | v24 |
|---|---|---|---|---|---|---|
| T19 | 22,055 | 27,111 (+5,056) | 27,112 (+5,057) | 22,055 (0) | 22,055 (0) | 27,461 (+5,406) |
| T20 | 62,724 | 63,289 (+565) | 63,292 (+568) | 62,710 (-14) | 63,580 (+856) | 63,271 (+547) |
| T25 | 43,625 | 44,551 (+926) | 44,538 (+913) | 43,625 (0) | 44,957 (+1,332) | 44,538 (+913) |
| T22 | 30,877 | 29,135 (-1,742) | 31,221 (+344) | 31,588 (+711) | 27,667 (-3,210) | 31,463 (+586) |
| T23 | 56,114 | 53,188 (-2,926) | 56,739 (+625) | 56,114 (0) | 50,944 (-5,170) | 56,516 (+402) |
| T29 | 60,481 | 60,762 (+281) | 67,448 (+6,967) | 59,620 (-861) | 60,481 (0) | 64,045 (+3,564) |
| T30 | 22,067 | 21,044 (-1,023) | 24,544 (+2,477) | 22,067 (0) | 22,067 (0) | 24,544 (+2,477) |

**4c. F8 removals / F5b (short-run) removals, and the share of all records removed.**

| Trial | v23 | fp | fp_off | lag | ref | v24 |
|---|---|---|---|---|---|---|
| T19 | 3,752 / 3,895; 33.2 % | 1,697 / 789; 17.9 % | 1,696 / 789; 17.9 % | 3,752 / 3,895; 33.2 % | 3,752 / 3,895; 33.2 % | 1,386 / 727; 16.8 % |
| T20 | 3,067 / 663; 9.0 % | 2,783 / 358; 8.1 % | 2,782 / 356; 8.1 % | 3,037 / 698; 9.0 % | 2,342 / 535; 7.7 % | 2,764 / 397; 8.2 % |
| T25 | 2,980 / 1,341; 14.8 % | 2,578 / 793; 13.0 % | 2,582 / 802; 13.0 % | 2,980 / 1,341; 14.8 % | 2,146 / 806; 12.2 % | 2,582 / 802; 13.0 % |
| T22 | 601 / 579; 9.0 % | 2,283 / 670; 14.2 % | 389 / 422; 8.0 % | 0 / 320; 6.9 % | 2,540 / 1,874; 18.5 % | 209 / 313; 7.3 % |
| T23 | 862 / 2,136; 31.8 % | 3,329 / 2,699; 35.4 % | 166 / 2,138; 31.1 % | 862 / 2,136; 31.8 % | 4,121 / 4,190; 38.1 % | 396 / 2,167; 31.3 % |
| T29 | 7,149 / 4,790; 23.3 % | 7,985 / 3,580; 23.0 % | 1,923 / 2,473; 14.5 % | 7,634 / 4,818; 24.4 % | 7,149 / 4,790; 23.3 % | 4,826 / 2,913; 18.8 % |
| T30 | 2,075 / 1,024; 18.9 % | 2,199 / 1,918; 22.7 % | 99 / 407; 9.8 % | 2,075 / 1,024; 18.9 % | 2,075 / 1,024; 18.9 % | 99 / 407; 9.8 % |

**4d. Mean kept dry yield.** The v23 column is bu/ac. The other columns give the change vs v2.3 in %, with a paired pass-bootstrap CI. These CIs are descriptive, not registered tests.

| Trial | v23 (bu/ac) | fp | fp_off | lag | ref | v24 |
|---|---|---|---|---|---|---|
| T19 | 72.73 | -0.73 [-1.32, -0.13] | -0.73 [-1.32, -0.13] | 0 | 0 | -0.79 [-1.46, -0.12] |
| T20 | 53.52 | -0.16 [-0.33, -0.03] | -0.16 [-0.34, -0.03] | +0.01 [-0.09, +0.12] | -0.28 [-0.55, -0.08] | -0.14 [-0.26, -0.06] |
| T25 | 66.85 | -0.02 [-0.11, +0.07] | -0.01 [-0.10, +0.08] | 0 | -0.05 [-0.12, +0.03] | -0.01 [-0.10, +0.08] |
| T22 | 68.48 | +0.34 [-0.13, +0.83] | +0.10 [-0.10, +0.29] | +0.07 [-0.13, +0.25] | -0.37 [-1.19, +0.31] | +0.07 [-0.12, +0.23] |
| T23 | 54.63 | +0.24 [-0.08, +0.63] | +0.12 [+0.02, +0.26] | 0 | -0.10 [-0.63, +0.44] | +0.11 [+0.02, +0.22] |
| T29 | 65.92 | -1.04 [-1.55, -0.57] | -1.49 [-1.94, -1.04] | -0.01 [-0.19, +0.17] | 0 | -1.17 [-1.66, -0.68] |
| T30 | 59.36 | -0.65 [-1.55, +0.17] | -1.24 [-2.20, -0.43] | 0 | 0 | -1.24 [-2.20, -0.43] |

**4e. Harvested-area coverage (ac), and the flow-delay shift applied (records).**

Coverage follows the footprint used to burn the raster, not the kept set: it is identical across configs that share a footprint. The shift follows the scan.

| Trial | Coverage v23 = lag = ref | Coverage fp | Coverage fp_off = v24 | Shift v23 | fp | fp_off | lag | ref | v24 |
|---|---|---|---|---|---|---|---|---|---|
| T19 | 101.27 | 102.35 | 102.35 | 0 | 0 | 0 | 0 | 0 | 0 |
| T20 | 305.30 | 306.26 | 306.26 | +2 | +3 | +3 | +4 | +3 | +4 |
| T25 | 152.47 | 153.87 | 153.86 | +3 | +4 | +4 | 0 | +3 | 0 |
| T22 | 154.42 | 155.78 | 156.58 | +2 | +2 | +2 | +3 | +2 | +3 |
| T23 | 398.76 | 401.80 | 404.59 | +2 | 0 | +2 | 0 | 0 | 0 |
| T29 | 426.89 | 433.97 | 440.09 | -5 | -7 | 0 | -5 | -5 | -5 |
| T30 | 138.46 | 139.58 | 141.10 | 0 | 0 | 0 | 0 | 0 | 0 |

`lag` and `v24` apply the shift before F7. All other configs apply it to the output geometry after the cascade.

Not registered, an observation from this table: the after-cascade shift changes with the kept set. For T29 it is -5 in `v23`, -7 in `fp` and 0 in `fp_off`; for T23 it is +2 in `v23` and 0 in `fp`. The scan in its v2.3 stage is itself unstable.

**What drives the changes (EXPLORATORY; `drivers_EXPLORATORY` in `results/P6_overall_table.json`).**

- **Case IH: the swept footprint drives the change.** Records alive after F7 above a common 5 % threshold, chord → swept → swept + Y_Offset:
  - T19: 3,752 → 1,697 → 1,696.
  - T25: 6,194 → 2,578 → 2,582.
  - Case IH logs Y_Offset of about 0 (|Y_Offset| <= 0.005 ft).
- **T19 in detail.**
  - `fp` alone keeps 5,056 more records: 1,743 come back from F8, 3,286 from F5b and 39 from F10/F11, while 12 are lost **(corrected in verification; the analyst's 2,014 / 3,354 are the v2.3 → v2.4 transitions)**.
  - The F5b gain comes about because in v2.3, F8 removals in curves broke runs into pieces shorter than the F5b minimum.
  - The local reference then adds 349 more records through its 10 % threshold.
- **John Deere: Y_Offset drives the change.** Same count, chord → swept → swept + Y_Offset:

  | Trial | Chord | Swept | Swept + Y_Offset |
  |---|---|---|---|
  | T22 | 2,540 | 1,247 | 225 |
  | T23 | 4,121 | 2,012 | 396 |
  | T29 | 17,124 | 7,985 | 3,957 |
  | T30 | 2,075 | 1,428 | 201 |

  - The swept footprint alone, with the field reference, drops the auto threshold to 2 % in T22, T23 and T30 and removes more records.
  - The chord footprint with the local reference (`ref`) is harsher still: T22 -3,210 and T23 -5,170 kept records.
  - In T30, `v24` keeps exactly the `fp_off` set (24,544 records), reaching 10 % by a different route.
  - In T29, `fp_off` keeps 6,967 more records (fallback 10 %) and `v24` keeps 3,564 more (local 5 %).
  - On T22, `lag` alone switches F8 off.
- **The effects are not additive.** v24's kept change minus the sum of the single ablations (`fp_off` + `lag` + `ref`):

  | Trial | Interaction (records) |
  |---|---|
  | T19 | +349 |
  | T20 | -863 |
  | T25 | -1,332 |
  | T22 | +2,741 |
  | T23 | +4,947 |
  | T29 | -2,542 |
  | T30 | 0 |

- **Records newly kept and newly removed, v2.3 → v2.4.** The ratios are median yield / pass median:

  | Trial | Newly kept | Their ratio | Newly removed | Their ratio |
  |---|---|---|---|---|
  | T19 | 5,415 | 1.014 | 9 | 0.79 |
  | T20 | 714 | 0.974 | 167 | 0.78 |
  | T25 | 1,361 | 1.016 | 448 | 1.00 |
  | T22 | 666 | 1.020 | 80 | 0.91 |
  | T23 | 634 | 1.079 | 232 | 1.00 |
  | T29 | 6,064 | 0.977 | 2,500 | 1.00 |
  | T30 | 2,480 | 1.017 | 3 | 0.48 |

- **Why mean kept yield falls 0.8-1.2 % in T19, T29 and T30.** The newly kept records read like their own pass, but they lie near edges and in lower-yield passes:
  - Share within 30 m of the edge: T19 29 % vs 18 % of all v2.4-kept records; T29 30 % vs 17 %; T30 61 % vs 13 %.
  - Mean of their pass means vs records kept by both versions: 69.2 vs 72.9 bu/ac (T19), 59.1 vs 65.8 (T29), 52.6 vs 59.3 (T30) **(corrected in verification: the analyst's comparison mixed v2.3- and v2.4-kept pass means; the conclusion holds)**.
  - So the drop means more edge ground in the map, not low readings being kept. Whether those edge yields are real cannot be decided from these data.

**Maps of the user's places, drawn both ways.** These are the places of test C5 plus one place chosen by a stated rule.

- `figs/P6_T19_turn_and_pass_start_v23_vs_v24.png`:
  - **T19 turn (records 5154-5165):** v2.3 removes all 12 records by F8 (chord overlap 10-17 %). v2.4 keeps all 12 (0 % overlap). Their yield / pass median is 0.72-1.00. The v2.3 W × D rectangles draw 23.3 m² (12.1 %) of consecutive overlap; the strips draw 0.
  - **T19 pass start (pass 74, records 29843-29858):** both versions decide the same way (4 F7 + 12 F8; real overlap 22-99 %). The rectangles draw 31.3 % consecutive overlap and 305 m² of area, against 209 m² for the strips.
- `figs/P6_T30_turn_and_pass_start_v23_vs_v24.png`:
  - **T30 turn (records 6368-6379):** both versions remove all 12 records (v2.3 by F8/F9; v2.4 by F9/F11/F5b at 0 % overlap). Their yield / pass median is 0.16-0.50 **(corrected in verification)**.
  - **T30 pass start (records 18760-18775):** same decisions; 10 of 16 kept.
  - **Extra T30 turn (records 5581-5592, 83 deg):** chosen as the turn with the most records flipped from v2.3-F8 to v2.4-kept. v2.4 keeps all 12 at 0 % overlap, but they read 0.63-0.69 of the pass median **(corrected in verification)**. Some turn records that v2.4 now keeps read about 35 % low for reasons other than overlap.
- `figs/P6_T19_whole_field_before_after_v24.png`: the whole of T19, before and after.

## 5. T29 lag sign and the flow-delay stage

**Registered T29 check (section 3, P5).**
- The scan's best lag is +5 records before F7 and after the cascade. The engine applies -5 in both stages.
- The pass-end analysis of review X3 favoured s = +5, the opposite sign.
- With the -5 applied before F7, T29's D5e worsens from 0.277 to 0.312.

**EXPLORATORY analysis of the sign** (`results/p5_t29.json`, `results/p5_axis.json`; figures `figs/p5_t29_scan_and_d5.png`, `figs/p5_t29_engine_sweep.png`, `figs/p5_axis_scans.png`, `figs/p5_scan_curves.png`):

1. **The scan runs on the minority axis.** The engine takes the E-W passes whenever E and W each have >= 200 core records, but 77 % of T29's core records run N-S. Only 26 E / 34 W passes (before F7) and 18 / 20 (kept) have an opposite-direction neighbour. In the bootstrap the best lag spreads over -8..+8, and the probability that the best lag is +5 is only 0.15-0.18.
2. **The +5 before F7 is a step, not a peak.** r goes from 0.29 at +4 to 0.44 at +5. The engine's pair set changes with the lag (the last "lag" rows of every pass drop out), and the step is driven by an outlier in one log. With a fixed pair set the best lag is -1, with a gain of 0.006.
3. **Combines.** Opposite-direction neighbours are mostly the same combine. Cross-log pairs correlate negatively (-0.25 to -0.46). The export has one date and no time of day, so the burn order between the 4 combines is file order.
4. **The dominant N-S axis gives a small negative best lag.**
   - Before F7, fixed pairs: best -2, gain 0.019, CI of the best lag [-3, 0].
   - After the cascade: best -1, gain 0.008, CI [-3, 0].
   - Per log: 0, -2, -2, 0. Per speed tercile: -2 / -2 / -2 before F7.
   - No combine and no tercile shows a positive best lag.
5. **The pass-end D5 does not identify the shift.** In fixed-shift engine sweeps, each end statistic improves whenever its own end ramp is pushed off the pass.
   - D5e: 0.277 at 0, 0.105 at +5, 0.051 at +8. For s <= -3 it sits on a 0.305-0.312 plateau that peaks at -5.
   - D5s: highest at s = 0 (0.075). It falls on both sides, to 0.061 at +8 and 0.015 at -8.
   - **(corrected in verification)** The analyst described D5e as monotonic and D5s as falling "the other way"; the shapes above are the corrected ones. The conclusion stands: neither statistic identifies s, and +5 was not a minimum of anything.
6. **Independent crop-edge timing** (mass flow against the overlap edge) gives -2.0 [-2.5, -2.0] records. Per log it is -1.5 to -2.5. An along-track offset of the header from the antenna cannot produce +5, and with a 24 % speed range a time lag cannot be told apart from a distance offset.

**Conclusion for T29.**
- The evidence points to a small positive output shift (record i at position i + 1..2) or none.
- In the dominant-axis bootstrap the auto rule applies no shift in 34-61 % of replicates.
- The engine's -5 places T29 yields about 7 records (about 11 m) from where they belong.
- The -5 is applied in v2.3 as well (output geometry), so it is not a v2.4 artefact.
- Any cleaning of this T29 export made with the default scan, in either version, carries it. This evaluation tested only the SMS export.

**Why the before-F7 and after-cascade scans disagree in other trials (EXPLORATORY).** Mostly the axis:
- T20, T25, T23 and T29 are harvested N-S (94, 89, 93 and 77 % of core records), yet the engine scans their minority E-W passes.
- On that axis only a handful of passes have an opposite-direction neighbour at lag 0: T20 4 + 3, T25 6 + 6, T23 1 + 1, T29 26 + 34 **(corrected in verification: the analyst's 5 + 4, 16 + 16 and 12 + 16 were counts of core passes)**.
- On the dominant axis, the best lag after the cascade / before F7 (fixed pairs) is:

  | Trial | After cascade | Before F7 |
  |---|---|---|
  | T19 | 0 | -1 |
  | T20 | -5 | -5 |
  | T25 | -4 | -4 |
  | T22 | -2 | -2 |
  | T23 | -2 | -2 |
  | T29 | -1 | -2 |
  | T30 | +1 | 0 |

- The engine's "gain > 0.01" rule is not meaningful. The gain is >= 0 by construction, its bootstrap spread (0.01-0.05) exceeds 0.01, and the decision flips between replicates.
- A sign-stability rule would shift T20 (+5), T25 (+4) and T22 (+2), and leave T19, T23, T29 and T30 unshifted. The rule: dominant axis, fixed pairs, and >= 90 % of replicates with |best| >= 2 and the same sign. It was devised after seeing the data. The crop-edge timing agrees with it in sign wherever either is non-zero.

**Why T22's F8 threshold went to 100 % under the lag (EXPLORATORY; `results/p5_explain_b.json`).**
- With the +3 shift, records at pass starts take the overlap of the position 3 records further into the crop. John Deere start spikes therefore slide into the 10-25 % bands. In v2.3, the >35 % band had a median logged width of 11 ft against 44.5 ft overall and a mean of 132 bu/ac.
- This lifts the 15-25 % band from -5.6 % to -0.1 %. Every band passes, so F8 removes nothing.
- Without the spikes, the 15-25 % band is -6.1 % under the lag vs -6.8 % in v2.3, both against a spike-free reference band.
- The interior records that moved into the >= 10 % bands yield like their pass (1.01), so they are lateral-overlap noise, not cut ground.

**What the flow-delay stage evidence says.**
- Applying the delay before F7/F8 did not meet its registered bound.
- It moved T22's F8 through relabelled start spikes.
- It removed 311-2,313 orphan records.
- It applied a wrong-sign -5 on T29.
- Even with the review's own lags imposed, the post-F8 end deficit stays at or just above 0.10. The end-of-pass deficit is therefore only partly a misalignment.

## 6. Limits

1. **The engine changed after the evaluation.**
   - `occd_dev/engine/clean/yield_clean.py` was modified at 19:43:31. `runs/dev_v23_T19.*` and `runs/dev_v24_T19.*` were rewritten at 19:43:48-49, after all analyses and verifications. This was outside this evaluation; another team is changing the dev engine.
   - Observed while writing this report, not independently verified:
     - The rewritten `dev_v23_T19` still equals `v23_v23_T19` on `_row`, `Keep`, `Rem_By` and `Overlap_f`.
     - The rewritten `dev_v24_T19` now gives a 5 % threshold: the scan stopped at the 5-10 % band, with 15 of 222 records matched.
     - Its placebo is now 1.012 on 730 matched records, and it keeps 27,112 records, identical record for record to `fp_off`.
     - The evaluated version gave 10 %, 0.984 on 449 records and 27,461 kept records.
   - The T19 v2.4 numbers in P6 and section 4 refer to the earlier engine. The new T19 placebo (1.012) would still lie inside 0.97-1.03.
   - The v2.4 run tables of the other six trials were not rewritten.
   - The evaluation must be re-run (at least E0 and P6 plus the section 4 table) on the engine that will be released.
2. **In-sample.** The predictions come from tests A-C and their reviews on these same 7 trials. P1-P4 therefore check that the implementation reproduces the earlier analyses. They are not out-of-sample tests of the methods.
3. **Small and specific sample.** 7 trials from one season, all SMS exports: 3 Case IH AFS and 4 John Deere GS4.
   - No file has a machine column, so the "same combine" condition of the local controls is not enforced. This matters most in T23 and T29, which hold 4 combines each.
   - T29 has no time of day, so the burn order between its combines is file order.
4. **Decision rules on point estimates.** P1, P3, P4 and P6 are judged on point estimates, as registered. Several margins are thin:
   - P2 passes at exactly 4 of 7.
   - P3 T23 is one flip from 36 %, and the P3 verdict depends on the denominator reading.
   - P6 has wide CIs in T19, T20 and T30.
5. **Coupled resampling units.** Pass-bootstrap CIs treat passes as independent. Neighbouring passes are coupled through overlap and through the scan pairs, so the CIs are somewhat optimistic.
6. **Raster resolution.** The 0.25 m raster moves several automatic thresholds with a 0.125 m shift of its origin (v2.3 T22, v2.3 T23, `fp` T30, v2.4 T23). Individual decisions at thresholds of 10 % or less are not stable.
7. **Thin local reference.** Only 6.8-44 % of the dose population has local controls. The threshold is set by the < 30 stop rule or by a drop whose CI spans the tolerance.
8. **Not isolated.** The 5 % floor was never ablated alone; it bound only in v2.4 T23. Y_Offset was tested only on top of the swept footprint. The configuration this report recommends (section 7) was not run as such.
9. **No yield ground truth.** P2 and the mean-yield changes are ratios against own-pass or field medians. Whether edge yields are real, and whether the records the swept footprint now keeps in turns are good readings, cannot be settled with these data.
10. **Exploratory analyses were devised after seeing the data.** This covers the axis scans, the fixed-pair scan, the sign-stability rule, crop-edge timing, the sign/side check, the scale sweep, the local-reference dose tables and the place maps. They are hypotheses for the next pre-registration.

## 7. What this means for adopting v2.4

v2.4 should not ship with its current defaults. The evidence supports this set of defaults:
- swept footprint;
- Y_Offset;
- local reference;
- 5 % floor;
- flow delay at the v2.3 `output` stage;
- swept-strip maps.

That combination was not run in this evaluation. Inference from the engine's description (with `lag_stage = "output"`, F7 and F8 judge every yield at its logged position): its kept sets should equal v2.4's on T19, T23, T25 and T30, where the before-F7 stage applied no shift. T20, T22 and T29 need new runs. It must also be checked on the final engine (limit 1).

| Change | Recommendation | Evidence | What would overturn it later |
|---|---|---|---|
| Swept-strip footprint | **Adopt as default** | P1, P2 and P3 supported. The wedge caused 9-55 % of v2.3's F8 removals, and in 4 of 7 trials those records yield like their pass. Raster flips fall 38-94 %. Test C: the strips tile the ground. On Case IH it keeps 565-5,056 more records, and mean kept yield changes by -0.02 % (T25), -0.16 % (T20) and -0.73 % (T19). On John Deere it must not be used alone with the field reference: the auto threshold drops to 2 % in T22, T23 and T30 and removes more records. | In a pre-registered test on new fields, wedge-only records (v2.3 F8 removals not above the threshold with the swept strip) whose yield / own-pass median CI lies wholly below 1 in most fields, as in T20, T25 and T29 here. Or a finer overlap measure (vector or 0.05 m raster) showing records the strip calls 0 % that are > 5 % overlapped in turns. Watch turn records that are kept but read low, such as T30 records 5581-5592 at 0.63-0.69; they may need a filter other than F8. |
| Y_Offset | **Adopt as default** for files with `Y_Offset_f` (John Deere), **only with the local reference** | P4 supported in 4/4: the median overlap of narrowed records goes to 0 and the share > 5 % goes to 8-9 %. EXPLORATORY: the offset is about half the narrowing (85-99 % within 1 ft), points away from cut ground (79-97 %), and the scale minimum is at s = 1 in 4/4. With the field reference it pushes the 0-2 % band across the tolerance (fallback to 10 % in T23, T29 and T30). With the local reference that band passes in 4/4. Case IH logs about 0, so it has no effect there. | On new John Deere fields: the side check falling towards 50 %, the scale-sweep minimum away from s = 1, or no fall in the narrowed records' overlap. On yield, not yet tested (synthesis item 3b): records cleared of overlap by the offset reading below their own pass, with a CI wholly below 1. Another monitor whose Y_Offset has a different meaning. |
| Local edge-matched reference | **Adopt as default**, without claiming the threshold is resolved at the 3 % tolerance | P6 supported: the placebo lies in 0.97-1.03 in 7/7 trials. The field reference compares near-edge bands with an interior no-overlap band (test A review) and produces knife-edge fallbacks with Y_Offset. But support is weak in T19, T20 and T30 (the CIs reach outside), and the placebo set is interior; near-edge placebos read 0.79-1.39. Only 6.8-44 % of records have controls. The < 30 stop rule decides 4 of 7 thresholds, and every deciding band's CI spans -3 %. T19's v2.4 threshold already moved from 10 % to 5 % with a later engine change. The run should keep reporting which rule set the threshold and how many records were matched. | A placebo whose CI lies wholly outside 0.97-1.03 in a field with >= 30 matched records. Near-edge placebos (0-30 m, >= 100 records) with CIs excluding 1. Thresholds that change with the raster origin or with minor engine changes in most fields. A pre-registered test of a wider edge tolerance (one that admits the adjacent pass, about one header width) could raise the matched share. Untested. |
| 5 % floor | **Adopt as default** (a resolution limit, not a measured threshold) | Not ablated alone here; it bound only once (v2.4 T23, auto 2 % → 5 %). The support is indirect but consistent. Tests A and C: a 0.3-1 m position error is a 2-9 % overlap, and one raster column is 1.7-2.3 % of the header. Here, a 0.125 m origin shift moves 18-53 % of the records alive after F7 between bands, mostly between 0 and 0-2 %. Thresholds at 2 % move with the origin (`fp` T30 2 → 5 %). Without the floor, `fp` gave 2 % in T22, T23 and T30. | A finer overlap measure that makes 2-5 % decisions stable under origin shifts, together with a local-control yield deficit in the 2-5 % band whose CI lies wholly below -3 %, in a pre-registered test. |
| Flow delay before F7/F8 | **Drop as default** (revert to `lag_stage = "output"`). Keep the switch for research runs only. | P5 refuted: D5e is 0.126, 0.133 and 0.331 in T22, T23 and T25. Even with the review's lags imposed, the end deficit stays at or just above 0.10. Side effects: T22's F8 switched off through relabelled start spikes; 311-2,313 orphans removed; the wrong-sign -5 on T29 makes D5e worse. The scan itself needs fixing in either stage. EXPLORATORY proposal: dominant axis, fixed pair set, after-cascade population, bootstrap sign stability instead of the 0.01 gain. Until then, do not shift T29; it is shifted -5 in both v2.3 and v2.4. The end-of-pass deficit needs a measured F7 end trim, not a delay. | A pre-registered test on fields not used here in which a fixed scan, applied before F7/F8, brings D5e <= 0.10 without moving the F8 threshold through pass-start spikes and without removing more than a few orphans. |
| Swept-strip maps | **Adopt as default** | Drawing only; no number depends on it. Test C: consecutive strips share an edge and tile the swept ground. In the user's T19 turn the v2.3 rectangles draw 12.1 % false overlap, and 31.3 % at the pass start, while the strips draw 0. In shifted trials the strips are drawn at the flow-delay source positions, so a wrong shift (T29 -5) moves the drawn yields; this is a scan problem, not a drawing problem. | Strips drawn with gaps or overlaps that the machine did not have: bow-tie turns drawn wrongly, or strip coverage that disagrees with an independent harvested-area measure such as SMS coverage or the boundary. |

## Files

All paths are relative to the `v24_eval` folder.

- **Pre-registration:** `PREREG_v24.txt`, `PREREG_v24.sha256`.
- **Run tables:** `runs/<engine>_<config>_<trial>[_shift0.125].parquet` and `.json`. Fixed-shift P5 runs are in `tmp/p5_runs`.
- **Analyst results:**
  - `results/E0_P1_P2_P3_geometry.json` (and `_e0`, `_p123`, `_dose_shift`, `_raster`, `_check_v24`).
  - `results/P4_y_offset.json` (and `_confirm`, `_explore`, `_dose`, `_local`, `_side_sens`, `_wfull_sens`).
  - `results/p5.json` (and `p5_d5`, `p5_t29`, `p5_axis`, `p5_explain_a`, `p5_explain_b`, `p5_engine_d5`, `p5_sens`).
  - `results/P6_overall.json` (and `_p6`, `_table`, `_edge`, `_explore`, `_maps`).
- **Verifications:** `results/verify_E0_P1_P2_P3_geometry*.json`, `results/verify_P4_y_offset*.json`, `results/verify_P5_lag_T29*.json`, `results/verify_P6_overall*.json`.
- **Scripts:** `scripts/E0_P1_P2_P3_geometry_*.py`, `scripts/P4_y_offset_*.py`, `scripts/p5_*.py`, `scripts/P6_overall_*.py`, `scripts/verify_*.py`, `scripts/run_one.py`.
- **Figures** (`figs/`):
  - `E0_P1_P2_P3_geometry_P1_P2_P3.png`, `E0_P1_P2_P3_geometry_dose_vs_raster_origin.png`.
  - `P4_yoffset_vs_half_narrowing.png`, `P4_offset_scale_sweep.png`, `P4_dose_fp_vs_fp_off.png`, `P4_band02_movers.png`, `P4_map_T23_narrowed_pass.png`, `P4_map_T30_narrowed_pass.png`.
  - `p5_d5.png`, `p5_scan_curves.png`, `p5_axis_scans.png`, `p5_t29_scan_and_d5.png`, `p5_t29_engine_sweep.png`.
  - `P6_placebo_and_local_dose_v24.png`, `P6_T19_turn_and_pass_start_v23_vs_v24.png`, `P6_T30_turn_and_pass_start_v23_vs_v24.png`, `P6_T19_whole_field_before_after_v24.png`.
