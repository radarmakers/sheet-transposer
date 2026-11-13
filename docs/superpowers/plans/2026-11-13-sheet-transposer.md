# Sheet Transposer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A single-page Streamlit app that reads a photo of printed sheet music with homr, detects its key, transposes it to a chosen key, shows it engraved on screen, and offers MusicXML and PDF downloads. A synthetic benchmark measures recognition quality, time and memory.

**Architecture:** There are small pure-Python modules under `src/sheet_transposer/`:
- image prep
- the homr wrapper
- MusicXML I/O
- key detection
- transposition
- rendering

`app.py` is a thin Streamlit layer over a `workflow` module. A separate `bench/` package builds degraded test pages from public-domain pieces in music21's bundled corpus, then runs homr on them under a 2-CPU limit and scores the results.

**Tech Stack:**
- Python 3.12 and uv
- Streamlit
- homr[cpu] (ONNX)
- music21
- Verovio (MusicXML → SVG)
- resvg-py (SVG → PNG; a pure wheel, no system libraries)
- Pillow (EXIF, resizing, PNG → PDF)
- albumentations (page degradation)
- pytest

**Spec:** `docs/superpowers/specs/2026-11-13-sheet-transposer-design.md`

## Global Constraints

- Python 3.12. Environment is managed with uv only: `pyproject.toml` plus a committed `uv.lock`, from public PyPI. No `requirements.txt` or other dependency file, because Community Cloud uses the first one it finds.
- homr is the only recognition engine. Never add or mention oemer as a dependency.
- One page per upload (v1). Keep "recognise one page" (`omr`) separate from "work on a score" (`workflow`) so multi-page can be added later.
- Nothing is persisted server-side: no files outside temp dirs, no accounts, no history.
- Recognising one page must take **≤ 180 s**, with peak memory **≤ 2.2 GB**, when pinned to 2 CPUs (`taskset -c 0,1`).
- Only one homr run at a time per process (shared lock).
- Licence: AGPL-3.0 (homr is AGPL). The app footer links to the source.
- Do not push to GitHub and do not deploy. The owner will do both from another account using the README steps.
- Prefer well-known library calls over hand-rolled code. Write readable Python.
- Key names shown to users use ♯/♭ characters, e.g. "E♭ major", "F♯ minor".

## Review Focus

1. **Phone photo stored sideways with an EXIF rotation tag.** It must reach homr upright. → Task 3 `test_exif_rotation_is_applied`.
2. **A non-music or blank photo, or homr crashing or producing no file.** The user sees a plain-English message, not a traceback. → Task 2 `test_nonzero_exit_raises_omr_error`, `test_missing_output_raises_omr_error`; Task 8 `test_read_page_wraps_unparseable_xml`.
3. **Very large uploads (e.g. 48 MP, 20 MB photos).** They are downscaled before homr, so memory stays in budget. → Task 3 `test_large_image_is_downscaled`.
4. **A detected key outside the conventional dropdown list** (e.g. C♯ major, 7 sharps). It must still appear and be selectable as the original. → Task 4 `test_choices_include_unconventional_detected_key`.
5. **Two friends uploading at once.** The second run waits instead of running in parallel. → Task 2 `test_runs_are_serialised`.

---

## File Structure

```
sheet-transposer/
├── pyproject.toml, uv.lock, .python-version   # uv project, Python 3.12
├── LICENSE                                    # AGPL-3.0 text
├── README.md                                  # usage + deploy steps (Task 10)
├── app.py                                     # Streamlit UI only (Task 8)
├── .streamlit/config.toml                     # upload limit, theme (Task 10)
├── src/sheet_transposer/
│   ├── __init__.py
│   ├── scoreio.py     # MusicXML text <-> music21 Score            (Task 1)
│   ├── render.py      # Score XML -> SVG pages / PNG / PDF          (Task 1)
│   ├── omr.py         # homr subprocess wrapper + lock              (Task 2)
│   ├── images.py      # upload bytes -> upright, bounded PNG        (Task 3)
│   ├── keys.py        # key detection, labels, dropdown choices     (Task 4)
│   ├── transpose.py   # transposition + interval wording            (Task 5)
│   └── workflow.py    # read_page / build_outputs glue for the app  (Task 8)
├── bench/
│   ├── __init__.py
│   ├── pieces.py      # benchmark piece list                        (Task 6)
│   ├── degrade.py     # albumentations "scan"/"phone" variants      (Task 6)
│   ├── build.py       # python -m bench.build                       (Task 6)
│   ├── metrics.py     # truth vs recognised scoring                 (Task 7)
│   ├── measure_one.py # one homr run -> JSON time + peak RSS        (Task 2)
│   ├── run.py         # python -m bench.run                         (Task 7)
│   ├── thresholds.toml                                              (Task 7)
│   └── data/, results/  # generated, git-ignored
├── docs/benchmark.md  # measured timings, baseline, tuning log      (Tasks 2, 7, 9)
└── tests/
```

---

### Task 1: Project skeleton, MusicXML I/O and rendering

**Files:**
- Create: `pyproject.toml`, `.python-version`, `LICENSE`, `src/sheet_transposer/__init__.py`, `src/sheet_transposer/scoreio.py`, `src/sheet_transposer/render.py`
- Modify: `.gitignore` (add `.venv/`, `bench/data/`, `bench/results/`, `__pycache__/`)
- Test: `tests/test_scoreio.py`, `tests/test_render.py`

**Interfaces:**
- Produces:
  - `scoreio.parse_musicxml(text: str) -> music21.stream.Score`. Raises `ValueError` on unparseable input.
  - `scoreio.to_musicxml(score: music21.stream.Score) -> str`
  - `render.render_svg_pages(musicxml: str, *, page_width: int = 2100, page_height: int = 2970, scale: int = 40, fit_height: bool = False) -> list[str]` (`fit_height` maps to Verovio's `adjustPageHeight`, for on-screen scrolling)
  - `render.render_png(svg: str, *, width_px: int) -> bytes`
  - `render.render_pdf(musicxml: str) -> bytes`

- [ ] **Step 1: Initialise the project**

Run in `~/sheet-transposer`:
```bash
uv init --lib --python 3.12 --name sheet-transposer .
uv add "homr[cpu]>=0.7.1" streamlit music21 verovio resvg-py pillow
uv add --dev pytest albumentations
```
- Set `[tool.pytest.ini_options]` with `addopts = "-m 'not slow'"`, `markers = ["slow: runs real homr"]` and `testpaths = ["tests"]`.
- Copy the AGPL-3.0 text from https://www.gnu.org/licenses/agpl-3.0.txt into `LICENSE`, and set `license = "AGPL-3.0-or-later"`.

Expected: `uv run python -c "import homr, music21, verovio, resvg_py"` exits 0.

- [ ] **Step 2: Write failing tests**

```python
# tests/test_scoreio.py
from music21 import corpus
from sheet_transposer.scoreio import parse_musicxml, to_musicxml

def test_round_trip_preserves_notes():
    s = corpus.parse("mozart/k545/movement1_exposition.mxl").measures(1, 4)
    again = parse_musicxml(to_musicxml(s))
    assert [p.nameWithOctave for p in again.pitches] == [p.nameWithOctave for p in s.pitches]

def test_garbage_raises_value_error():
    with pytest.raises(ValueError):
        parse_musicxml("not music")
```
```python
# tests/test_render.py
def test_svg_pages_for_twelve_bars(k545_xml):            # fixture: first 12 bars as MusicXML text
    pages = render_svg_pages(k545_xml)
    assert len(pages) == 1 and pages[0].lstrip().startswith("<svg")
    assert "Verovio" not in pages[0]                      # no engraving footer

def test_png_is_png(k545_xml):
    png = render_png(render_svg_pages(k545_xml)[0], width_px=1240)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"

def test_pdf_has_one_page_per_svg(k545_xml):
    pdf = render_pdf(k545_xml)
    assert pdf.startswith(b"%PDF") and b"/Count 1" in pdf
```
Put the `k545_xml` fixture in `tests/conftest.py`.

- [ ] **Step 3: Run tests, verify they fail**

Run: `uv run pytest tests/test_scoreio.py tests/test_render.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 4: Implement `scoreio.py` and `render.py`**

- `scoreio`:
  - Use `music21.converter.parseData(text, format="musicxml")`, wrapping any parse exception as `ValueError`.
  - Export with `music21.musicxml.m21ToXml.GeneralObjectExporter(score).parse().decode()`.
- `render`:
  - Use one `verovio.toolkit()` per call.
  - Options: `{"pageWidth": page_width, "pageHeight": page_height, "scale": scale, "footer": "none", "adjustPageHeight": fit_height}`. Call `loadData(musicxml)`, then `renderToSVG(i)` for `i in 1..getPageCount()`.
  - `render_png`: `resvg_py.svg_to_bytes(svg_string=svg, width=width_px)` wrapped in `bytes(...)`.
  - `render_pdf`:
    - Render each page to PNG at 1654 px wide (A4 at 200 dpi).
    - Open each with Pillow and convert to RGB.
    - Save with `save(buf, "PDF", save_all=True, append_images=rest, resolution=200)`.

- [ ] **Step 5: Run tests, verify they pass**

Run: `uv run pytest -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: project skeleton, MusicXML I/O and Verovio rendering"
```

---

### Task 2: homr wrapper and the resource checkpoint

**Files:**
- Create: `src/sheet_transposer/omr.py`, `bench/__init__.py`, `bench/measure_one.py`, `docs/benchmark.md`
- Test: `tests/test_omr.py`

**Interfaces:**
- Consumes: `render.render_svg_pages`, `render.render_png` (Task 1), used to make the checkpoint page.
- Produces:
  - `omr.OmrError(Exception)`, carrying a user-facing message.
  - `omr.recognise(png: bytes, *, runner: Callable[[Path, int], None] | None = None, timeout_s: int = 600) -> str`. Returns MusicXML text.
  - `omr.homr_command(image: Path) -> list[str]` = `[str(Path(sys.executable).parent / "homr"), str(image)]`
  - `bench.measure_one`: CLI `python -m bench.measure_one IMAGE`. It prints a JSON line `{"seconds": float, "peak_rss_mb": float, "ok": bool, "musicxml_path": str|null}`.

- [ ] **Step 1: Find out how homr names its output**

Run homr once by hand on `/tmp/plancheck/k545.png`, or regenerate it via `render_png`:
```bash
cp /tmp/plancheck/k545.png /tmp/homrprobe/ && uv run homr /tmp/homrprobe/k545.png; ls /tmp/homrprobe
```
- Record the output file name pattern (expected `k545.musicxml` beside the input) and where models are downloaded on first run.
- Note both facts at the top of `omr.py` as a comment.
- Note the first-run model download time in `docs/benchmark.md`.

- [ ] **Step 2: Write failing tests**

The default runner calls `subprocess.run(homr_command(path), timeout=timeout_s, check=True, capture_output=True)`. Tests inject fake runners:

```python
def test_returns_musicxml_written_beside_image():
    def fake(image: Path, timeout_s: int):
        image.with_suffix(".musicxml").write_text("<score-partwise/>")
    assert recognise(b"png", runner=fake) == "<score-partwise/>"

def test_nonzero_exit_raises_omr_error():
    def fake(image, timeout_s): raise subprocess.CalledProcessError(1, "homr")
    with pytest.raises(OmrError, match="couldn't read"): recognise(b"png", runner=fake)

def test_missing_output_raises_omr_error():
    with pytest.raises(OmrError): recognise(b"png", runner=lambda i, t: None)

def test_timeout_raises_omr_error():
    def fake(image, timeout_s): raise subprocess.TimeoutExpired("homr", timeout_s)
    with pytest.raises(OmrError, match="too long"): recognise(b"png", runner=fake)

def test_runs_are_serialised():
    # two threads call recognise with a fake that records (enter, exit) times and sleeps 0.2 s;
    # assert the intervals do not overlap.

def test_temp_files_are_removed():
    # capture image path inside fake; after recognise returns, assert image.parent does not exist.
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `uv run pytest tests/test_omr.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 4: Implement `omr.py`**

- Use a module-level `threading.Lock`, and hold it for the whole run.
- Write the PNG to a `tempfile.TemporaryDirectory()`, run the runner, then read the expected output name (from Step 1). If that name is absent, fall back to the only `*.musicxml` in the dir.
- Error messages:
  - Failure: `OmrError("Sorry — we couldn't read any music in that image. Try a flatter, brighter photo of printed music.")`
  - Timeout: `OmrError("Reading the music took too long. Try a smaller or clearer photo.")`

- [ ] **Step 5: Run tests, verify they pass**

Run: `uv run pytest tests/test_omr.py -v`
Expected: PASS.

- [ ] **Step 6: Implement `bench/measure_one.py`**

- Run `homr_command(image)` via `subprocess.run`.
- Time it with `time.perf_counter()`.
- Take peak memory from `resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024`. This is valid because this process starts exactly one child.
- Print the JSON line.

- [ ] **Step 7: CHECKPOINT: measure one page under Community-Cloud-like limits**

Run (after a warm-up run so models are already downloaded):
```bash
taskset -c 0,1 uv run python -m bench.measure_one /tmp/homrprobe/k545.png
```
- Record the seconds and peak MB in `docs/benchmark.md` under "Checkpoint (Task 2)".
- **If seconds > 180 or peak_rss_mb > 2200: stop and report to the owner** with the numbers before continuing. The spec says to trade quality for fit; Task 9's `MAX_SIDE` sweep is the first lever.
- Otherwise continue.

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: homr wrapper with lock and resource measurement"
```

---

### Task 3: Upload image preparation

**Files:**
- Create: `src/sheet_transposer/images.py`
- Test: `tests/test_images.py`

**Interfaces:**
- Produces:
  - `images.MAX_SIDE: int = 3000` (Task 9 may tune this)
  - `images.ImageError(Exception)`
  - `images.prepare_image(data: bytes, *, max_side: int = MAX_SIDE) -> bytes`: returns PNG bytes, upright, RGB, longest side ≤ max_side.

- [ ] **Step 1: Write failing tests**

```python
def test_exif_rotation_is_applied():
    # 400x200 JPEG with EXIF Orientation=6 (rotate 90° CW) -> output size (200, 400)
def test_large_image_is_downscaled():
    # 8000x6000 -> longest side == 3000, aspect preserved within 1 px
def test_small_image_is_not_upscaled():
    # 1000x800 -> unchanged size
def test_greyscale_and_rgba_become_rgb():
    # modes "L" and "RGBA" -> output mode "RGB"
def test_non_image_raises_image_error():
    with pytest.raises(ImageError, match="photo or scan"): prepare_image(b"%PDF-1.4 ...")
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_images.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `prepare_image`**

- Pillow: `Image.open` → `ImageOps.exif_transpose` → `convert("RGB")` → `thumbnail((max_side, max_side), Image.LANCZOS)` → save PNG.
- Wrap `UnidentifiedImageError` as `ImageError("That file isn't a photo or scan we can read — please upload a JPG or PNG.")`.

- [ ] **Step 4: Run tests, verify they pass**

Run: `uv run pytest tests/test_images.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: upright, bounded image preparation"
```

---

### Task 4: Key detection, labels and choices

**Files:**
- Create: `src/sheet_transposer/keys.py`
- Test: `tests/test_keys.py`

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class KeyResult:
      key: music21.key.Key              # best guess
      sharps: int                       # from the first key signature; flats negative; 0 if none
      confident: bool
      alternative: music21.key.Key | None   # the relative major/minor, set only when not confident
  def detect_key(score: Score) -> KeyResult
  def key_label(k: music21.key.Key) -> str          # "E♭ major", "F♯ minor"
  def key_from_label(label: str) -> music21.key.Key
  def signature_label(sharps: int) -> str           # "3 flats", "1 sharp", "no sharps or flats"
  CONVENTIONAL_MAJORS = ["C","D♭","D","E♭","E","F","F♯","G","A♭","A","B♭","B"]
  CONVENTIONAL_MINORS = ["C","C♯","D","E♭","E","F","F♯","G","G♯","A","B♭","B"]
  def key_choices(mode: str, include: music21.key.Key | None = None) -> list[str]
      # 12 labels of that mode, in circle-of-semitones order from C; `include` is added if absent
  ```

- [ ] **Step 1: Write failing tests**

Build small scores in a `tests/conftest.py` helper `make_score(key_sig_sharps, notes: list[str])`, which makes a single-part 4/4 score with quarter notes.

```python
def test_c_major_scale_is_c_major_confident():
    r = detect_key(make_score(0, "C4 D4 E4 F4 G4 A4 B4 C5 G4 E4 C4".split()))
    assert key_label(r.key) == "C major" and r.confident and r.sharps == 0

def test_a_minor_with_leading_tone_is_a_minor():
    r = detect_key(make_score(0, "A3 C4 E4 G#4 A4 E4 C4 B3 G#3 A3".split()))
    assert key_label(r.key) == "A minor"

def test_major_minor_tie_is_not_confident():
    r = detect_key(make_score(-3, "E-4 G4 B-4 C5".split()))
    assert not r.confident and r.alternative is not None

def test_missing_key_signature_means_zero_sharps():
    # score with no KeySignature object -> sharps == 0

def test_real_chorale_is_f_sharp_minor():
    r = detect_key(corpus.parse("bach/bwv66.6"))
    assert key_label(r.key) == "F♯ minor" and r.sharps == 3

def test_labels_round_trip():
    for name in CONVENTIONAL_MAJORS:
        assert key_label(key_from_label(f"{name} major")) == f"{name} major"

def test_choices_include_unconventional_detected_key():
    cs = key_choices("major", include=music21.key.Key("C#"))
    assert "C♯ major" in cs and len(cs) == 13

def test_signature_label():
    assert signature_label(-3) == "3 flats" and signature_label(1) == "1 sharp" and signature_label(0) == "no sharps or flats"
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_keys.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `keys.py`**

- `sharps` = first `KeySignature` in `score.recurse()`, or 0 if there is none.
- Candidates: `KeySignature(sharps).asKey("major")` and `.asKey("minor")`.
- Score each candidate using `score.analyze("key")`: look it up among `[k] + k.alternateInterpretations` by tonic name and mode, and take its `correlationCoefficient`.
- Choose the higher-scoring candidate.
- `confident = (chosen_corr - other_corr) >= 0.1`, and the analyser's top key equals the chosen key. When not confident, `alternative` is the other candidate.
- Labels: replace music21's `-` with `♭` and `#` with `♯` in `tonic.name`; parse back the reverse way.

- [ ] **Step 4: Run tests, verify they pass**

Run: `uv run pytest tests/test_keys.py -v`
Expected: PASS. If `test_major_minor_tie_is_not_confident` is borderline, adjust that test's notes, not the 0.1 margin.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: key detection with major/relative-minor confidence"
```

---

### Task 5: Transposition

**Files:**
- Create: `src/sheet_transposer/transpose.py`
- Test: `tests/test_transpose.py`

**Interfaces:**
- Consumes: `keys.key_from_label`, `keys.key_label` (Task 4); `scoreio` (Task 1).
- Produces:
  - `semitone_shift(src: Key, dst: Key) -> int`: the nearest move, in `-6..5` (a tritone goes down).
  - `shift_label(semitones: int) -> str`: `"no change"`, `"up 1 semitone"`, `"down 3 semitones"`.
  - `transpose_score(score: Score, src: Key, dst: Key) -> Score`: returns a new score; the input is untouched.
- The design limits "change to" to keys of the **same mode** as the original key (major→major, minor→minor). Changing mode is not transposition. The app only offers `key_choices(original.mode, ...)`.

- [ ] **Step 1: Write failing tests**

```python
def test_shift_eflat_to_d_is_down_one():
    assert semitone_shift(Key("E-"), Key("D")) == -1 and shift_label(-1) == "down 1 semitone"

def test_tritone_goes_down():
    assert semitone_shift(Key("C"), Key("F#")) == -6

def test_same_key_is_identity():
    s = make_score(0, "C4 E4 G4".split())
    assert [p.nameWithOctave for p in transpose_score(s, Key("C"), Key("C")).pitches] == ["C4","E4","G4"]

def test_c_to_dflat_spells_in_flats_and_updates_signature():
    out = transpose_score(make_score(0, "C4 F#4 G4".split()), Key("C"), Key("D-"))
    assert [p.name for p in out.pitches] == ["D-", "G", "A-"]
    assert out.recurse().getElementsByClass("KeySignature").first().sharps == -5

def test_all_key_signatures_are_replaced():
    # score with a key signature in bar 1 and another in bar 3 -> both become dst's sharps

def test_round_trip_restores_original():
    s = corpus.parse("mozart/k545/movement1_exposition.mxl").measures(1, 12)
    there = transpose_score(s, Key("C"), Key("E-"))
    back = transpose_score(there, Key("E-"), Key("C"))
    assert [p.nameWithOctave for p in back.pitches] == [p.nameWithOctave for p in s.pitches]

def test_input_score_is_not_modified():
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `uv run pytest tests/test_transpose.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `transpose.py`**

- Build the spelled interval with `music21.interval.Interval(noteStart=Pitch(src.tonic.name + "4"), noteEnd=Pitch(...))`. Choose the end pitch's octave so the semitone distance equals `semitone_shift(src, dst)`.
- Apply it with `score.transpose(interval, inPlace=False)`.
- Then set every `KeySignature` in the result to `dst.sharps`, since music21's own key-signature transposition can choose enharmonic equivalents.
- Do not simplify double accidentals. With conventional target spellings they are musically correct, e.g. F𝄪 in C♯ minor.

- [ ] **Step 4: Run tests, verify they pass**

Run: `uv run pytest tests/test_transpose.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: nearest-direction transposition with conventional spelling"
```

---

### Task 6: Benchmark pages

**Files:**
- Create: `bench/pieces.py`, `bench/degrade.py`, `bench/build.py`
- Test: `tests/test_bench_build.py`

**Interfaces:**
- Consumes: `scoreio.to_musicxml`, `render.render_svg_pages`, `render.render_png` (Task 1); `transpose.transpose_score`, `keys.key_label`/`key_from_label` (Tasks 4–5).
- Produces:
  - `pieces.Piece(id: str, corpus_path: str, bars: tuple[int, int], kind: Literal["piano","vocal","organ"], extra_keys: tuple[str, ...])`
  - `pieces.PIECES: list[Piece]`
  - `pieces.SMOKE_IDS: list[str]`
  - `degrade.VARIANTS = ("clean", "scan", "phone")`
  - `degrade.degrade(png: bytes, variant: str, seed: int) -> bytes`
  - `python -m bench.build [--only ID ...]` writes `bench/data/<page_id>/truth.musicxml`, `bench/data/<page_id>/<variant>.png`, and `bench/data/manifest.json`. Each manifest entry is `{"page_id", "piece_id", "kind", "truth_key": "E♭ major", "variants": [...]}`. `page_id` = `f"{piece.id}__{key-slug}"`.

- [ ] **Step 1: Fill in `PIECES`**

Take the first 12 bars from the music21 bundled corpus. No downloads.

| id | corpus_path | kind | extra_keys |
|---|---|---|---|
| mozart_k545 | mozart/k545/movement1_exposition.mxl | piano | E♭ major, A major |
| joplin_maple | joplin/maple_leaf_rag.mxl | piano | D major |
| clara_pol1 | schumann_clara/polonaise_op1n1.mxl | piano | B major |
| clara_pol2 | schumann_clara/polonaise_op1n2.mxl | piano | F♯ major |
| clara_pol3 | schumann_clara/polonaise_op1n3.mxl | piano | — |
| clara_pol4 | schumann_clara/polonaise_op1n4.mxl | piano | — |
| cpebach_h186 | cpebach/h186.mxl | piano | — |
| schoenberg_19_2 | schoenberg/opus19/movement2.mxl | piano | — |
| schoenberg_19_6 | schoenberg/opus19/movement6.mxl | piano | — |
| schubert_linden | schubert/Lindenbaum.xml | vocal | — |
| schumann_dl2 | schumann_robert/dichterliebe_no2.xml | vocal | — |
| bach_organlike | bach/bwv66.6 | organ | — (S+A on staff 1, T on staff 2, B as a third "pedal" staff) |

- Each piece produces one page in its original key plus one page per `extra_keys` entry. Extra keys apply to the same mode as the piece. If a listed extra key's mode doesn't match, use the same tonic in the piece's mode.
- After building, assert that the piano pages cover key signatures from at least 4 flats to 5 sharps. Add extra keys if not.
- `SMOKE_IDS` = `["mozart_k545__c-major", "joplin_maple__d-major", "schubert_linden__<orig>"]`.

- [ ] **Step 2: Write failing tests**

```python
def test_degrade_is_deterministic_and_changes_pixels(k545_png):
    a = degrade(k545_png, "phone", seed=1); b = degrade(k545_png, "phone", seed=1)
    assert a == b and a != k545_png

def test_clean_variant_is_unchanged(k545_png):
    assert degrade(k545_png, "clean", seed=1) == k545_png

def test_build_one_piece(tmp_path):
    build(out_dir=tmp_path, only=["mozart_k545"])
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert {e["truth_key"] for e in m} == {"C major", "E♭ major", "A major"}
    assert all((tmp_path / e["page_id"] / f"{v}.png").exists() for e in m for v in VARIANTS)
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `uv run pytest tests/test_bench_build.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement**

- `degrade` uses `albumentations.Compose`, with a fixed seed set via `A.Compose(..., seed=seed)`:
  - **scan:** `Rotate(limit=2, border_mode=cv2.BORDER_CONSTANT, fill=255)`, `GaussNoise` (light), `ImageCompression(quality_range=(70, 85))`.
  - **phone:** `Perspective(scale=(0.02, 0.05), fill=255)`, `Rotate(limit=4, fill=255)`, `RandomShadow`, `RandomBrightnessContrast`, `GaussianBlur(blur_limit=(3, 5))`, `Downscale(scale_range=(0.6, 0.8))`, `ImageCompression(quality_range=(50, 70))`.
  - **clean:** returns the input bytes unchanged.
- Pages render at `width_px=2480` (A4 at 300 dpi).
- `build`:
  - Parse via `music21.corpus.parse`, then take `.measures(*bars)`.
  - For extra keys, use `transpose_score`.
  - Truth key = `detect_key` on the clean truth score; for transposed pages, the target key.
  - Write all files.

- [ ] **Step 5: Run tests, verify they pass; then build the full set**

Run: `uv run pytest tests/test_bench_build.py -v && uv run python -m bench.build`
Expected: PASS. `bench/data/manifest.json` has ≥ 18 pages × 3 variants.

- Open 3 `phone.png` files to eyeball that they look like plausible phone photos, not destroyed.

- [ ] **Step 6: Commit**

```bash
git add bench tests && git commit -m "feat: synthetic benchmark pages from music21 corpus"
```

---

### Task 7: Benchmark scoring, runner, baseline and regression test

**Files:**
- Create: `bench/metrics.py`, `bench/run.py`, `bench/thresholds.toml`, `tests/test_metrics.py`, `tests/test_benchmark_slow.py`
- Modify: `docs/benchmark.md`

**Interfaces:**
- Consumes: Task 2 `bench.measure_one`; Task 6 manifest; `keys.detect_key`.
- Produces:
  ```python
  @dataclass
  class PageScore:
      key_sig_ok: bool; key_ok: bool
      note_precision: float; note_recall: float; note_f1: float
      duration_acc: float          # among matched notes
      bars_ok: bool                # same measure count
      full_bars_frac: float        # measures (excl. first and last) whose content fills the time signature
  def compare(truth: Score, got: Score, truth_key: str) -> PageScore
  ```
  - `python -m bench.run [--subset smoke|full] [--cpus 0,1] [--jobs 1] [--max-side N]` writes `bench/results/<UTC timestamp>.csv` (one row per page×variant: ids, seconds, peak_rss_mb, ok, PageScore fields) and prints a summary table of means by variant and kind.

- [ ] **Step 1: Write failing tests for `compare`**

```python
def test_identical_scores_are_perfect(k545_score):
    s = compare(k545_score, k545_score, "C major")
    assert s.note_f1 == 1.0 and s.duration_acc == 1.0 and s.bars_ok and s.key_ok

def test_one_wrong_pitch_lowers_f1(k545_score):
    # copy, raise first note a semitone -> 0.9 < note_f1 < 1.0

def test_missing_bar_breaks_bars_ok(k545_score):
    # remove last measure from got -> bars_ok False
```

- Note matching: build a `collections.Counter` of `(measure_number, round(offset_in_measure * 12) / 12, midi)` over every note, expanding chords, across all parts.
- Matched notes = Counter intersection. Precision, recall and F1 follow from the counts.
- `duration_acc` compares `quarterLength` for matched keys.

- [ ] **Step 2: Run tests, verify fail → implement `metrics.py` → verify pass**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: FAIL first, then PASS after implementing.

- [ ] **Step 3: Implement `bench/run.py`**

- For each manifest page and variant:
  - `subprocess.run(["taskset", "-c", cpus, sys.executable, "-m", "bench.measure_one", png])`.
  - Pass `--max-side` by preprocessing the PNG with `images.prepare_image(max_side=N)` into a temp file first. The default is `images.MAX_SIDE`.
  - Parse the output, then score with `compare`. Parse failures count as `ok=False` with zeros.
- With `--jobs 2`, give each worker a disjoint CPU pair (`0,1` and `2,3`); this VM has 4 CPUs.

- [ ] **Step 4: Run the baseline (long; run in background)**

Run: `uv run python -m bench.run --subset full --jobs 2`
Expected:
- A CSV is written.
- Every row has `seconds ≤ 180` and `peak_rss_mb ≤ 2200`. If not, stop and report to the owner, as in Task 2 Step 7.
- Vocal and organ rows may score low, but none may crash the runner.

- Paste the summary table into `docs/benchmark.md` under "Baseline".

- [ ] **Step 5: Write thresholds and the slow regression test**

`bench/thresholds.toml`:
- For each metric `note_f1`, `key_ok` (as a rate) and `full_bars_frac`, take the baseline mean on the **smoke piano pages** for the `clean` and `phone` variants, minus 0.05, rounded down to 2 dp.
- Add `max_seconds = 180` and `max_peak_rss_mb = 2200`.

```python
@pytest.mark.slow
def test_smoke_benchmark_meets_thresholds():
    # runs bench.run's library function on SMOKE_IDS piano pages with variants clean+phone,
    # asserts each mean >= threshold and every row within time/memory limits
```

- [ ] **Step 6: Run it**

Run: `uv run pytest -m slow -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add bench tests docs && git commit -m "feat: benchmark scoring, baseline and slow regression test"
```

---

### Task 8: Workflow glue and the Streamlit app (layout A)

**Files:**
- Create: `src/sheet_transposer/workflow.py`, `app.py`
- Test: `tests/test_workflow.py`, `tests/test_app.py`

**Interfaces:**
- Consumes: `images.prepare_image`/`ImageError`, `omr.recognise`/`OmrError`, `scoreio.*`, `keys.*`, `transpose.*`, `render.*`.
- Produces:
  ```python
  class ReadError(Exception)  # user-facing message; wraps ImageError, OmrError, parse ValueError
  @dataclass(frozen=True)
  class Page:
      musicxml: str            # as recognised
      detected: KeyResult
  def read_page(upload: bytes, *, recognise=omr.recognise) -> Page
  @dataclass(frozen=True)
  class Outputs:
      musicxml: str; svgs: list[str]; pdf: bytes; shift: str   # shift = shift_label(...)
  def build_outputs(page: Page, original: str, target: str) -> Outputs   # labels from key_choices
  ```

- [ ] **Step 1: Write failing workflow tests**

Use a fake `recognise` that returns the K545 12-bar MusicXML.

```python
def test_read_page_detects_c_major(): assert key_label(read_page(png, recognise=fake).detected.key) == "C major"
def test_read_page_wraps_unparseable_xml():
    with pytest.raises(ReadError): read_page(png, recognise=lambda b: "garbage")
def test_read_page_wraps_image_error():
    with pytest.raises(ReadError, match="photo or scan"): read_page(b"not an image", recognise=fake)
def test_build_outputs_transposes_and_renders():
    o = build_outputs(page, "C major", "D major")
    assert o.shift == "up 2 semitones" and o.svgs and o.pdf.startswith(b"%PDF")
    assert parse_musicxml(o.musicxml).recurse().getElementsByClass("KeySignature").first().sharps == 2
def test_build_outputs_with_corrected_original():
    # page detected C major, user says original is "A minor" and target "B minor" -> up 2 semitones
```

- [ ] **Step 2: Run tests, verify they fail → implement `workflow.py` → verify they pass**

Run: `uv run pytest tests/test_workflow.py -v`
Expected: FAIL first, then PASS after implementing.

- [ ] **Step 3: Write `app.py`**

The app is a single column, in this order (exact copy where quoted):
1. Title "Sheet Transposer". Caption: "Works best with printed piano music: flat, well-lit, whole page in frame."
2. `st.file_uploader("Upload a photo or scan of one page", type=["jpg", "jpeg", "png", "webp"])`
3. On upload: inside `st.status("Reading the music… this can take a few minutes. Keep this screen open.")`, call `cached_read(data)`.
   - `cached_read` is `@st.cache_data(max_entries=20, show_spinner=False)` wrapping `read_page`, so an identical upload is instant.
   - Show elapsed seconds in the status label when done.
   - If another run holds the lock, the status already covers the wait. Add the line "If a friend is also using the app, yours will start when theirs finishes."
4. On `ReadError`: `st.error(str(e))`, then stop.
5. "Original key" selectbox: `key_choices(detected.key.mode, include=detected.key)`, defaulting to the detected key. Help text: "detected: {signature_label(sharps)}".
   - If `not detected.confident`, show `st.info(f"Not sure — this could also be {key_label(alternative)}. Change it above if so.")`.
6. "Change to" selectbox: `key_choices(original.mode, include=original)`. The original is labelled with the suffix " (original)" and selected by default. Caption: `outputs.shift`.
7. One `st.html(svg)` per page of `outputs.svgs`, rendered with `render_svg_pages(xml, fit_height=True)` for scrolling (`Outputs.svgs` uses this; the PDF keeps A4 pages).
8. Two `st.download_button`s:
   - "Download MusicXML": `{stem}-{target-slug}.musicxml`, `application/vnd.recordare.musicxml+xml`
   - "Download PDF": `.pdf`
9. Footer caption:
   - "Source code (AGPL-3.0): {SOURCE_URL}"
   - "Recognition by homr; may misread notes — fix them in MuseScore via the MusicXML download."
   - `SOURCE_URL` is a module constant `"https://github.com/OWNER/sheet-transposer"`, to be set at deploy (README step).

- [ ] **Step 4: Write the AppTest smoke test**

```python
def test_app_loads_with_uploader_and_footer():
    at = AppTest.from_file("app.py").run(timeout=30)
    assert not at.exception and "Sheet Transposer" in at.title[0].value
    assert any("AGPL" in c.value for c in at.caption)
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 6: Manual end-to-end run**

- Run `uv run streamlit run app.py --server.headless true --server.port 8501`. Using a second shell, `curl -s localhost:8501/_stcore/health` returns `ok`.
- Upload `bench/data/mozart_k545__c-major/phone.png` via a Playwright or manual session if available. If neither is possible, call `read_page` on that file from a Python shell and confirm `build_outputs` produces non-empty SVGs and a PDF.
- Record what was checked in the commit message.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: single-column Streamlit app"
```

---

### Task 9: Tuning against the benchmark

**Files:**
- Modify: `src/sheet_transposer/images.py` (only if a change wins), `bench/thresholds.toml` (only if raised), `docs/benchmark.md`

**Interfaces:**
- Consumes: `bench.run` (Task 7).
- Produces: possibly a new `images.MAX_SIDE` value and an `images.prepare_image(..., autocontrast: bool)` default. Signatures are otherwise unchanged.

- [ ] **Step 1: `MAX_SIDE` sweep**

Run `bench.run --subset full --jobs 2 --max-side N` for N ∈ {2000, 2500, 3000, 4000}.
Keep the N with the best mean piano `note_f1` on `phone`, subject to every row ≤ 180 s and ≤ 2200 MB.

- [ ] **Step 2: Autocontrast experiment**

- Add `autocontrast: bool = False` to `prepare_image`, implemented with `ImageOps.autocontrast(img, cutoff=1)` after conversion to greyscale-then-RGB.
- Write a unit test that it raises the contrast of a washed-out image.
- Run the full benchmark with it on.
- Default it to True only if mean piano `note_f1` on `phone` improves by ≥ 0.02 without hurting `clean` by > 0.01.

- [ ] **Step 3: Measure, don't build, the post-processing candidates**

From the latest full run, report in `docs/benchmark.md`:
- the share of piano pages with `full_bars_frac < 0.8`
- the share of pages where `key_sig_ok` is False

These decide whether bar-repair or crossed-hand repair is worth building later. Do not implement them in v1. Raise them with the owner.

- [ ] **Step 4: Re-run tests, update thresholds if the winning config raised the baseline, commit**

Run: `uv run pytest -v && uv run pytest -m slow -v`
Expected: PASS.

```bash
git add -A && git commit -m "perf: tune image preparation against benchmark"
```

---

### Task 10: Deploy readiness and README

**Files:**
- Create: `.streamlit/config.toml`, `README.md`
- Test: `tests/test_deploy_files.py`

**Interfaces:**
- Consumes: everything above.
- Produces: no code interfaces.

- [ ] **Step 1: Write failing test**

```python
def test_only_uv_lock_dependency_file():
    root = Path(__file__).parents[1]
    assert (root / "uv.lock").exists()
    for f in ["requirements.txt", "Pipfile", "environment.yml"]:
        assert not (root / f).exists()
    assert (root / ".python-version").read_text().strip().startswith("3.12")

def test_upload_limit_configured():
    cfg = tomllib.loads((Path(__file__).parents[1] / ".streamlit/config.toml").read_text())
    assert cfg["server"]["maxUploadSize"] == 25
```

- [ ] **Step 2: Run, fail, create `.streamlit/config.toml` (`[server] maxUploadSize = 25`), and pass**

Run: `uv run pytest tests/test_deploy_files.py -v`
Expected: FAIL first, then PASS after creating the file.

- [ ] **Step 3: Write `README.md`**

Include:
- What the app does, and its limits (one page; piano best; homr ignores dynamics and articulation; crossed hands may be misassigned).
- Local run: `uv sync && uv run streamlit run app.py`
- Tests: `uv run pytest`, and `uv run pytest -m slow` (real homr, takes minutes).
- Benchmark: `uv run python -m bench.build && uv run python -m bench.run --subset full --jobs 2`, with a pointer to `docs/benchmark.md`.
- **Deploying (owner):**
  1. Create a public repo on your GitHub account and push `main`.
  2. Set `SOURCE_URL` in `app.py` to that repo's URL and commit.
  3. Sign in at share.streamlit.io with GitHub → Create app → choose the repo, branch `main`, file `app.py`.
  4. Under Advanced settings, pick Python 3.12.
  5. Deploy, then share the `*.streamlit.app` link.
  6. The first upload after the app wakes downloads homr's models, so expect it to be slower.
- Licence: AGPL-3.0.

- [ ] **Step 4: Final verification**

Run: `uv run pytest -v && uv run pytest -m slow -v && git status --short`
Expected: all PASS, and a clean tree apart from git-ignored `bench/data` and `bench/results`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "docs: README with deploy steps; Streamlit config"
```
