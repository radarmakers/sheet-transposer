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
