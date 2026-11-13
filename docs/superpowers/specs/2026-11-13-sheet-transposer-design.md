# Sheet Transposer — design

Date: 2026-11-13
Status: draft, awaiting owner approval

## Intent

A small, lightweight Streamlit web app, hosted on Streamlit Community Cloud,
that turns a photo or scan of one page of printed sheet music into digital
notation, tells you what key it is in, lets you move it to another key, and
lets you read and download the result.

The owner and a small group of friends play and teach a wide range of music:
church organ pieces, higher-grade teaching repertoire, and songs. Today a
piece in the wrong key means rewriting or re-sourcing it by hand. The main
outcome is **reading the transposed music on screen** (tablet, phone or
laptop). Downloading it to edit or print elsewhere comes second.

This first version is meant to **test whether the app is useful** with that
small group. It is deliberately single-page and minimal.

## Users

- The owner and a limited set of friends who have the link. It is not public
  or advertised.
- No accounts and no sign-in. Anyone with the link gets a fresh, empty app.
- They will mostly use phones and tablets, and sometimes laptops.

## Goals

1. Upload **one page** image (JPG/PNG): a photo from the gallery or photo
   reel, a photo taken there and then with the phone camera, or a scan.
2. Recognise the music into digital notation (MusicXML) using **homr**.
3. Detect and show the key in plain words, e.g. "E♭ major (3 flats)".
4. Let the user choose a new key, show the interval ("down 1 semitone"), and
   transpose the whole page.
5. Draw the transposed music as properly engraved notation on screen.
6. Offer downloads of the transposed music as **MusicXML** and **PDF**.

**Priority of music types:** piano (two staves: chords, both hands) must work
best. Organ (three staves including pedals) and vocal music (lyrics) only
need to not crash. Lower recognition quality for them is acceptable in v1.

## Non-goals (v1)

- Multi-page pieces. This is planned for later; see "Future: multi-page"
  below.
- Editing notes inside the app. If the recognition gets notes wrong, users
  fix them in MuseScore etc. via the MusicXML download.
- Storing anything on the server: no library, history or user accounts.
- A Google Photos or other cloud-account integration.
- Audio playback, practice tools, or a MIDI export.
- Retraining recognition models.
- oemer. The owner has ruled it out completely; homr is the only engine.

## Anti-goals (would make it a failure even if it "works")

- The app looks frozen during a long recognition with no feedback.
- The app shows a confident but wrong key with no hint that it might be wrong.
- Transposed music uses ugly or unreadable spellings, e.g. E𝄫 major instead
  of D major, or many needless double accidentals.
- It grows into a heavy app (databases, auth, extra services) that is hard to
  keep running on the free hosting tier.

## Constraints

- **Hosting:** Streamlit Community Cloud (free tier). Approx. limits as of the
  Streamlit docs: at most 2 CPU cores, at most 2.7 GB RAM, no GPU. Apps go to
  sleep after 12 hours without traffic and wake on the next visit (slow first
  load). System packages can be installed via `packages.txt`, and Python
  packages via `requirements.txt`. The app is deployed from a GitHub repo.
- **Recognition engine:** homr (`pip install homr`, v0.7.1 at time of
  writing, Python 3.11–3.12 recommended, ONNX-based, CPU supported). Its
  models download on first run. It handles pitch and rhythm in treble and bass
  clef, and it ignores dynamics, articulation and double sharps/flats. It
  assigns notes to staves (hands) by vertical position, so it gets
  crossed-hand passages wrong.
- **Licence:** homr is AGPL-3.0, so the app's source must be available to its
  users. A public GitHub repo satisfies this, and the app should link to it.
- **Speed is unknown.** homr publishes no CPU timings. Assume it could take
  anywhere from ~30 seconds to a few minutes per page on Community Cloud. This
  must be measured early (see Verification).

## Decided by the owner

- Streamlit, hosted on Streamlit Community Cloud.
- homr is the recognition engine. Don't use oemer.
- Piano is the priority over organ and voice.
- Single page only for v1.
- Layout **A: a single column, top to bottom** (see below).
- Small invited group via link. No accounts.
- The main use is reading on screen.
- Quality is checked with synthetic "rough" test pages, since there are no
  real sample photos yet.
- **Stay on free Community Cloud.** If homr turns out too slow or too
  memory-hungry, give up some recognition quality to fit, e.g. smaller input
  images or lighter settings. Don't move hosts. Hugging Face Spaces was
  considered and rejected because it now needs a paid plan for apps like
  this.
- This is a **learning exercise** developed on a dev VM. The owner will move
  the repo to a different GitHub account to deploy it, so the builder does
  not push to GitHub or deploy. The plan should end with written deploy
  steps the owner can follow:
  1. Push to a public GitHub repo.
  2. Sign in at share.streamlit.io with GitHub.
  3. Pick the repo, branch and `app.py`, then deploy.

## Acceptance thresholds (builder's call, owner may override)

- Recognising one page takes **≤ 3 minutes** under Community-Cloud-like
  limits (2 CPUs, 2.7 GB). If it takes longer, apply the quality trade-offs
  above until it fits.
- Peak memory for one recognition is **comfortably under 2.7 GB**, leaving
  room for Streamlit itself.

## Screen (layout A)

One column. Each step appears under the previous one once it is ready:

```
┌──────────────────────────────────┐
│ [ Upload a photo or scan ]       │
│   "Reading the music… this can   │
│    take a few minutes" + progress│
│                                  │
│ Original key: [E♭ major ▾]       │
│   detected: 3 flats              │
│   (+ "not sure — could be C      │
│    minor" when uncertain)        │
│ Change to: [ D major ▾ ]         │
│            down 1 semitone       │
│ ┌──────────────────────────────┐ │
│ │ Transposed sheet music,      │ │
│ │ engraved, scroll to read     │ │
│ └──────────────────────────────┘ │
│ [Download MusicXML] [Download PDF]│
│                                  │
│ small footer: source code link   │
│ (AGPL), known limitations        │
└──────────────────────────────────┘
```

- **Upload:** a single `st.file_uploader` accepting images. On phones this
  opens the OS picker. iOS offers Photo Library / Take Photo / Choose File.
  Android offers camera, gallery and usually Google Photos. "Take Photo"
  gives a full-resolution camera image. A laptop picks a file from disk.
- **Long work:** show a clear progress or status message while homr runs,
  with "keep this screen open". Cache recognition results by image content
  hash, so re-uploading the same image is instant.
- **Key picker:** offers a "back to original key" option and labels each
  choice with its interval from the original.
- **Before upload:** a short line about what works best, e.g. "printed piano
  music, flat, well-lit, whole page in frame".

## Builder's calls (made during brainstorming, owner may override)

These were proposed by me (Claude), not decided by the owner:

1. **Output format:** MusicXML, chosen because it is widely supported
   (MuseScore, Sibelius, Dorico, phone apps). PDF is added for easy reading
   on tablets.
2. **Rendering:** Verovio (Python package) renders MusicXML to SVG for
   on-screen display. The PDF is built from the same Verovio output, so the
   on-screen and PDF versions match. The builder chooses the SVG→PDF route,
   preferring a pure-Python option or one installable via `packages.txt`.
3. **Music processing:** music21 for parsing MusicXML, key analysis and
   transposition.
4. **Key detection:** start from the key signature homr reads. Use music21's
   key analysis of the notes to decide between the major key and its relative
   minor (e.g. E♭ major vs C minor). When the two disagree, or the analysis
   confidence is low, say so on screen rather than hiding it.
5. **Transposition:** transpose by the interval between the detected key and
   the chosen key. Offer the 12 major and 12 minor keys with conventional
   spellings (e.g. D♭ major not C♯ major, F♯ minor not G♭ minor). Simplify
   needless enharmonics in the result.
6. **No camera widget:** leave out `st.camera_input`. Its images are too low
   resolution for reliable recognition, and the upload button already gives
   access to the phone camera.
7. **No server-side persistence:** results live only in the user's session.
   Users keep what they download.
8. **Python 3.12, managed with uv** (owner's decision). Use `pyproject.toml`
   plus a committed `uv.lock`, installing from public PyPI. Community Cloud
   reads `uv.lock` directly; it is first in its dependency-file order. Keep
   it as the only dependency file. Set Python 3.12 in the Community Cloud
   deploy settings to match local development. This project is an exception
   to the owner's usual pixi rule.
9. **The user can correct the detected key.** The "Detected key" line is a
   dropdown that defaults to the detected key, so the user can correct it,
   e.g. "actually C minor". Transposition always starts from the key shown
   there. Without this, a misread key signature would move the music by the
   wrong interval and label it with the wrong key.
10. **One recognition at a time.** A single shared lock means only one homr
    run happens at once in the container. Others see "someone else's page is
    being read, yours is next". This keeps memory inside 2.7 GB when two
    friends upload at once.
11. **Clean-up around homr, not inside it:**
   - Optional image pre-processing (deskew, crop, contrast, resize to a
     staff-line spacing homr handles well).
   - Post-processing of homr's MusicXML (bars that don't add up to the time
     signature, accidentals vs key signature, crossed-hand staff assignment).
   - Keep each step only if the benchmark shows it helps.

## Verification and tuning

There are no real sample photos yet, so quality is measured on synthetic
pages with known correct answers:

1. **Ground truth:** a small set (~15–30 pages) of public-domain piano
   music that already exists as accurate MusicXML (e.g. OpenScore,
   Mutopia), covering grades of difficulty, key signatures with 0–6
   sharps/flats, and some minor keys. Add a handful of organ and vocal pages
   as smoke tests only.
2. **Clean pages:** render each to a page image.
3. **Rough pages:** generate degraded variants that imitate phone photos:
   rotation/skew, perspective warp, blur, uneven lighting, JPEG compression,
   lower resolution. Use an established augmentation library rather than
   hand-rolled code.
4. **Metrics per page:**
   - key signature correct
   - detected key (incl. major/minor) correct
   - note pitch and duration accuracy (aligned comparison against ground truth)
   - bar count correct
   - share of bars whose durations add up to the time signature
   - round-trip check: transpose up then back down equals the original
5. **Resource check:** measure time and peak memory per page while limited
   to ~2 CPUs and ~2.7 GB RAM, to match Community Cloud. Do this **first**,
   before building UI around assumptions.
6. **Regression tests:** the scoring runs as automated tests with
   thresholds, so later changes cannot quietly make recognition worse. Keep
   the CI-sized subset small enough to run quickly.
7. **Tuning loop:** each pre-/post-processing tweak is scored against the
   benchmark and kept only if it improves results.

Once friends start using the app, real photos they're happy to share can be
added to the benchmark.

## Future: multi-page (not in v1)

The owner said continuous multi-page scores are likely to be wanted later.
Agreed direction: read the pages one at a time with per-page progress, cache
each page, stitch them into one score, detect the key over the whole piece,
and cap the page count based on measured timings (probably ~6). v1 should not
block this. Keep "recognise one page" separate from "work on a score".

## Left to the builder

- Repo layout, module structure, and test framework details.
- The exact SVG→PDF method.
- Exact benchmark pieces, augmentation parameters and pass thresholds.
- Wording of on-screen messages.
- Whether pre-processing ends up enabled by default (benchmark decides).
