# Evidence for OCCD v2.4 (overlap filter F8, flow delay, maps)

This folder ships the evidence behind the v2.4 overlap model with the app. The method itself is in
`docs/METHOD.md` (sections 3, 3.1, 4, 8, 12 and 13); the short version is in the main `README.md` (sections *The
overlap model of v2.4* and *Evidence for v2.4*).

## Files

| File | What it is |
|---|---|
| `PREREG_v24.txt` | The pre-registration of the before/after evaluation: data, configurations, predictions P1-P6 and their decision rules, written on 29 October 2026 before the v2.4 code existed and before any after-number was computed. It is kept byte for byte (its paths, such as `scratchpad/overlap_tests/...`, refer to the working folder of the tests and are not shipped). |
| `PREREG_v24.sha256` | Its SHA-256 (`75687be2...6c46f9b`). Check it from this folder with `sha256sum -c PREREG_v24.sha256` (Git Bash) or `certutil -hashfile PREREG_v24.txt SHA256` (Windows). |
| `EVALUATION_v24.md` | The evaluation report: E0 and P1-P6 with their verdicts (E0 held; P1, P2, P3, P4 and P6 supported; P5 refuted), the exploratory analyses, the limits and the recommendation for each change. Its paths are relative to the evaluation's working folder; of those, only the figures below are shipped (in `figs/`). |
| `FINAL_RECHECK.md` | The re-check on the released engine: E0 and P6 again, the v2.3 -> v2.4 table on the seven trials (kept records, thresholds and what set them, mean yield with paired CIs, flow-delay shift), the raster-origin stability and the four places drawn both ways, all recomputed by an independent verifier. |
| `SINTESE_testes_ABC_pt.md` | The synthesis, in Portuguese, of the pre-registered overlap tests A (bias), B (pass-end ramp) and C (geometry) and their adversarial reviews, which motivated v2.4. Its figure and folder paths are relative to the tests' working folder and are not shipped. |
| `figs/` | The key figures of the evaluation (below). |

The evaluation tested the v2.4 engine as it stood at 18:26-18:30 on 29 October 2026, whose defaults applied the flow
delay before F7 and F8 and read the local controls within 15 m on every record alive after F7. The released defaults
differ (flow delay back on the output geometry after P5 was refuted; local controls on the pass interiors, by combine,
within max(15 m, 1.5 header widths); the flow-delay scan on the dominant pass axis). The runs of the released engine on
the same seven trials, the re-check of E0 and P6 on it, and the limits of the evidence, are in `docs/METHOD.md`
section 13; the `final_*` figures below come from those runs.

## Figures

| Figure | Shows |
|---|---|
| `figs/E0_P1_P2_P3_geometry_P1_P2_P3.png` | P1 (mean overlap in curves, chord vs swept strip), P2 (yield of the records only the chord wedge removed, against their own pass) and P3 (F8 decisions that flip when the raster origin moves 0.125 m). |
| `figs/P4_yoffset_vs_half_narrowing.png` | John Deere: the logged `Y_Offset` against half the narrowing of the header, (W_full - W) / 2. |
| `figs/P4_dose_fp_vs_fp_off.png` | John Deere (exploratory): the F8 dose-response of the swept strip without `Y_Offset` and with it against the whole-field reference, and with it against the local edge-matched controls: with the offset the 0-2 % band fails only against the field reference. |
| `figs/p5_d5.png` | P5: the end-of-pass (D5e) and start-of-pass (D5s) deficits after F8 with the flow delay on the output (config v23) and before F7 / F8 (config lag), against the registered 0.10 bound. |
| `figs/p5_axis_scans.png` | Exploratory: the flow-delay scan of each trial on its dominant pass axis, measured before F7 and after the cascade (also with a balanced pair set), with the best lag of each: the basis of `lag_axis` "dominant". |
| `figs/P6_placebo_and_local_dose_v24.png` | P6: the placebo of the local edge-matched controls per trial, and the per-band local dose-response with the matched / alive counts and the band that stopped the scan (evaluated engine: 15 m, all records alive after F7, one combine per file). |

Figures of the released engine (runs with the final defaults and with `LEGACY_V23`; numbers in `FINAL_RECHECK.md`):

| Figure | Shows |
|---|---|
| `figs/final_P6_placebo_and_local_dose.png` | P6 re-checked on the final engine (pass interiors, combine key, radius max(15 m, 1.5 header widths)): the placebo with its 95 % pass-bootstrap CI per trial (7 of 7 inside 0.97-1.03; the CIs of T19, T20 and T30 reach outside), and the per-band local dose-response with the records with controls, the band that stopped the scan and the threshold used (floor on T22, T23, T29). |
| `figs/final_T19_turn_v23_vs_v24.png` | T19, a turn inside pass 7 (12 records): v2.3 rectangles and decisions (all 12 removed by F8 at 10-17 % chord overlap) against the v2.4 swept strips (0 % overlap, all kept), with each record's overlap and yield / own-pass median. |
| `figs/final_T19_pass_start_v23_vs_v24.png` | T19, the start of pass 74 (16 records) drawn both ways: the same decisions (4 by F7, 12 by F8 on real overlap of 22-100 %); the rectangles draw 31 % of their area twice, the strips none. |
| `figs/final_T19_whole_field_before_after_v24.png` | T19, the whole field before and after the final v2.4 cleaning (swept strips), the removals by filter group and the records v2.3 and v2.4 decide differently (5,069 newly kept, 12 newly removed). |
| `figs/final_T30_turn_v23_vs_v24.png` | T30 (John Deere), a turn inside pass 30: removed by both versions (v2.4 by F9 / F11 / F5b at 0 % overlap; the records read 0.16-0.50 of their pass). |
| `figs/final_T30_pass_start_v23_vs_v24.png` | T30, the start of pass 94 (16 records) drawn both ways: the same decisions in both versions (F1, F7, F11; 10 of 16 kept). |
