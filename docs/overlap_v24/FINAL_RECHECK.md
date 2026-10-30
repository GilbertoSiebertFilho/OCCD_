# OCCD v2.4: re-check on the final engine (29 Oct 2026)

`EVALUATION_v24.md` evaluated the pre-registered predictions on the engine as it stood during the evaluation. Three
things changed after it:

- The code review changed the local F8 reference. It now uses the pass interiors and a combine key (machine column,
  else the SMS serial, else the Ops Center log), and its radius is max(15 m, 1.5 header widths).
- P5 was refuted, so the flow delay went back to the output stage (`lag_stage = "output"`).
- The scan now compares the passes of the axis the field was harvested in (`lag_axis = "dominant"`).

This page re-checks the final engine. Every number was recomputed by an independent verifier with its own code.

## E0: the v2.3 model is reproduced

`LEGACY_V23` on the final engine equals the untouched v2.3 engine record for record in all 7 trials: same row order,
and 0 differences in Keep, Rem_By, Pass_Id, Run_Id, Lag_rec, Overlap_f and the output positions.

## P6 on the final engine: supported

Placebo = median ratio of the no-overlap records of the local population to their local controls. The CI is a 95 %
pass bootstrap (B 2000, seed 2026). The registered rule judges the point estimate against 0.97-1.03.

**Deviation to state.** The population (pass interiors), the combine key and the radius were changed after the code
review and before this re-check.

| Trial | Placebo [95 % CI] | Placebo records / passes | Combine key |
|---|---|---|---|
| T19 | 1.012 [0.932, 1.065] | 730 / 12 | SMS serial |
| T20 | 0.997 [0.948, 1.066] | 726 / 42 | SMS serial |
| T25 | 1.000 [0.989, 1.011] | 8,535 / 81 | SMS serial |
| T22 | 0.998 [0.985, 1.010] | 11,453 / 76 | one combine |
| T23 | 1.000 [0.992, 1.007] | 14,684 / 151 | Ops Center log (4) |
| T29 | 0.994 [0.974, 1.014] | 5,155 / 131 | Ops Center log (4) |
| T30 | 0.984 [0.963, 1.002] | 6,508 / 88 | one combine |

Under the stricter reading "CI wholly inside 0.97-1.03", which was not registered, T19, T20 and T30 fail. T19's
placebo comes from 12 passes.

## v2.3 against the final v2.4

| Trial | Kept v2.3 -> v2.4 | F8 removed | F5b removed | F8 threshold v2.3 -> v2.4 (what decided it) | Mean kept dry yield, change [paired CI] | Lag applied v2.3 -> v2.4 |
|---|---|---|---|---|---|---|
| T19 | 22,055 -> 27,112 | 3,752 -> 1,696 | 3,895 -> 789 | 5 -> 5 % (5-10 %: 15 of 222 matched) | 72.73 -> 72.20, -0.73 % [-1.32, -0.13] | 0 -> 0 |
| T20 | 62,724 -> 63,292 | 3,067 -> 2,782 | 663 -> 356 | 5 -> 5 % (5-10 %: 0 of 496 matched) | 53.52 -> 53.44, -0.16 % [-0.34, -0.03] | +2 -> +5 |
| T25 | 43,625 -> 44,538 | 2,980 -> 2,582 | 1,341 -> 802 | 10 -> 5 % (5-10 % at -3.62 %) | 66.85 -> 66.84, -0.01 % [-0.10, +0.08] | +3 -> +4 |
| T22 | 30,877 -> 31,485 | 601 -> 225 | 579 -> 317 | 15 -> 5 % (floor; 2-5 %: 8 of 103 matched) | 68.48 -> 68.52, +0.06 % [-0.13, +0.24] | +2 -> +2 |
| T23 | 56,114 -> 56,516 | 862 -> 396 | 2,136 -> 2,167 | 25 -> 5 % (floor; 2-5 %: 28 of 252 matched) | 54.63 -> 54.69, +0.11 % [+0.02, +0.22] | +2 -> +2 |
| T29 | 60,481 -> 65,189 | 7,149 -> 3,957 | 4,790 -> 2,837 | 10 % fallback -> 5 % (floor; 2-5 % at -12.04 %) | 65.92 -> 65.06, -1.31 % [-1.80, -0.84] | -5 -> +2 |
| T30 | 22,067 -> 24,459 | 2,075 -> 201 | 1,024 -> 408 | 5 -> 5 % (5-10 %: 19 of 73 matched) | 59.36 -> 58.66, -1.19 % [-2.14, -0.42] | 0 -> 0 |

F0-F7 remove the same records in both versions. Records newly kept by v2.4 and newly removed by it:

| Trial | Newly kept | Newly removed |
|---|---|---|
| T19 | 5,069 | 12 |
| T20 | 569 | 1 |
| T25 | 1,361 | 448 |
| T22 | 657 | 49 |
| T23 | 634 | 232 |
| T29 | 6,202 | 1,494 |
| T30 | 2,395 | 3 |

**What decides the threshold.** The local dose-response stops for too few matched records in 5 of 7 trials (T19,
T20, T22, T23, T30) and on a yield drop in 2 (T25, T29).
- The 5 % floor sets the final value in T22, T23 and T29.
- A measured drop sets it only in T25.
- In the other three the threshold is the last band with enough evidence.

**Raster origin moved 0.125 m.**
- The v2.4 threshold stays at 5 % in all 7 trials.
- The kept set changes by 0.06-1.14 % of the kept records, against 0.85-20.6 % in v2.3.
- The T29 lag goes from +2 to 0, so it is fragile.

## The places the user asked about (figures in `figs/final_*`)

"Drawn twice" = ground covered by two or more drawn polygons ÷ ground covered by them. It corrects the first version,
which divided by the summed polygon areas.

| Place | Drawn twice: v2.3 rectangles -> v2.4 strips | F8 overlap with earlier ground: v2.3 -> v2.4 | Kept: v2.3 -> v2.4 |
|---|---|---|---|
| T19 turn | 13.3 % -> 0 % | 13.6 % -> 0 % | 0 -> 12 of 12 |
| T19 pass start | 45.3 % -> 0 % | 51.2 % -> 52.6 % | 0 -> 0 of 16 |
| T30 turn | 9.8 % -> 0 % | 11.3 % -> 0 % | 0 -> 0 of 12 |
| T30 pass start | 0.4 % -> 0 % | 8.5 % -> 8.1 % | 10 -> 10 of 16 |

- **The fan at a turn is a drawing artefact.**
  - The swept strips tile the turn.
  - The 12 T19 turn records that v2.3 removed (the predecessor wedge counted as overlap) yield 0.72-1.00 of their pass median, and v2.4 keeps them.
  - The T30 turn records yield only 0.16-0.50 of their pass median, and v2.4 still removes them, now by F9, F11 and F5b.
- **The T19 pass start is real overlap.** The pass begins on ground cut earlier, and both versions remove the 16 records (4 by F7, 12 by F8).
- **The T30 red-to-green stack is a time transient.**
  - The yield climbs from 0.18 to 1.0 of the pass median over records 1-9.
  - After record 2 the overlap stays below 1.3 %.
  - F1, F7 and F11 remove records 1-6.
