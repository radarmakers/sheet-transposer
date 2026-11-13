# Benchmark notes

Limits from the design: ≤ 180 s and ≤ 2200 MB peak per page, pinned to 2 CPUs
(`taskset -c 0,1`) to imitate Streamlit Community Cloud.

## Checkpoint (Task 2) — 2026-11-13

Page: Mozart K545 bars 1–12, Verovio-engraved, 2480 × 3508 px (A4 @ 300 dpi), white background.

| run | seconds | peak RSS (MB) | ok |
|---|---|---|---|
| homr 0.7.1, 2 CPUs, models already present | 13.8 | 1560 | yes |

- First run fetched homr's ~150 MB of ONNX models into the installed package in a few seconds.
- A transparent-background PNG made homr find zero noteheads: images must be flattened onto white
  (fixed in `render_png`; `prepare_image` must do the same for uploads).
- homr can fail ("No noteheads or clefs found") without producing output; `omr.recognise` treats a
  missing output file as failure.

Verdict: well inside limits; continue.

## Baseline (Task 7) — 2026-11-13

`python -m bench.run --subset full --jobs 2` (each job pinned to its own 2 CPUs), `MAX_SIDE = 3000`,
17 pages × 3 variants. Results: `bench/results/20261113T110959Z.csv` (organ rows re-run after fixing
the organ truth file, which had lost its key signature on the top staff).

| kind | variant | n | ok | note_f1 | duration_acc | key_sig_ok | key_ok | bars_ok | full_bars_frac | max s | max MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| piano | clean | 14 | 14 | 0.95 | 0.99 | 1.00 | 1.00 | 0.79 | 0.98 | 43.1 | 1918 |
| piano | scan | 14 | 14 | 0.95 | 0.99 | 1.00 | 1.00 | 0.79 | 0.97 | 44.7 | 1722 |
| piano | phone | 14 | 14 | 0.94 | 1.00 | 1.00 | 1.00 | 0.79 | 0.96 | 47.4 | 1881 |
| vocal | clean | 2 | 2 | 0.95 | 0.82 | 1.00 | 1.00 | 1.00 | 0.97 | 34.8 | 1599 |
| vocal | scan | 2 | 2 | 0.95 | 0.82 | 1.00 | 1.00 | 1.00 | 0.97 | 40.1 | 1668 |
| vocal | phone | 2 | 2 | 0.94 | 0.82 | 1.00 | 1.00 | 1.00 | 0.95 | 26.5 | 1769 |
| organ | clean | 1 | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 21.1 | 1641 |
| organ | scan | 1 | 1 | 0.98 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 32.3 | 1652 |
| organ | phone | 1 | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 18.4 | 1799 |

Notes:
- Every page is well inside the limits (slowest 47 s, peak 1.92 GB).
- `bars_ok` 0.79 on piano: homr adds an empty bar at some repeat signs (e.g. Joplin bar 1). The note
  metric aligns bars by content, so this doesn't distort note accuracy.
- Vocal `duration_acc` 0.82: rhythms under lyrics are the weak spot, as expected.
- These are synthetic pages from engraved music; real photos will be harder. Add real photos when friends share them.

Regression floor (`bench/thresholds.toml`): smoke piano pages (Mozart C major, Joplin D major),
clean + phone means minus 0.05 → note_f1 ≥ 0.92, key_ok ≥ 0.95, full_bars_frac ≥ 0.92.

## Tuning (Task 9) — 2026-11-13

### `MAX_SIDE` sweep (phone variant, full set)

| MAX_SIDE | piano note_f1 | organ note_f1 | vocal note_f1 | max s | max MB |
|---|---|---|---|---|---|
| 2000 | 0.95 | **0.25** | 0.94 | 47.8 | 1841 |
| 2500 | 0.94 | 1.00 | 0.94 | 47.6 | 1820 |
| 3000 (baseline) | 0.94 | 1.00 | 0.94 | 47.4 | 1881 |
| 4000 | 0.93 | 1.00 | 0.94 | 46.3 | 1858 |

Decision: keep **3000**. Piano differences are within ±0.01 (noise on 14 pages); 2000 px wrecks
the three-staff organ page; time and memory are flat (homr appears to resize internally).

### Autocontrast (clean + phone, MAX_SIDE 3000)

| | piano clean | piano phone |
|---|---|---|
| off (baseline) | 0.95 | 0.94 |
| on | 0.95 | 0.93 |

Decision: stays **off** (rule was ≥ +0.02 on phone without hurting clean). Real dim phone photos
may behave differently; revisit when real photos exist.

### Post-processing candidates (measured, not built)

From the baseline run:
- Piano rows whose bars don't add up (`full_bars_frac < 0.8`): **3 of 42**.
- Key signature misread: **0 of 48** piano/vocal rows.
- Wrong bar count: 3 piano pages (homr turns some repeat signs into an extra empty bar — Joplin ×2,
  Clara Schumann Polonaise 2).
- Weakest piano piece: Schoenberg Op. 19 No. 6 (note_f1 0.72–0.74) — sparse, atonal, many accidentals.

Conclusion: bar repair and crossed-hand repair aren't justified by synthetic pages. Revisit with
real photos. Thresholds unchanged.
