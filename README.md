# Sheet Transposer

A small Streamlit app that reads a photo or scan of **one page** of printed sheet music, works out
its key, lets you move it to another key, and shows the result as engraved music, with MusicXML and
PDF downloads.

- Recognition: [homr](https://github.com/liebharc/homr) (optical music recognition, CPU).
- Key detection and transposition: [music21](https://www.music21.org/).
- Engraving: [Verovio](https://www.verovio.org/); PDF pages are rendered images (via resvg + Pillow).

## Limits

- One page per upload (multi-page is planned).
- Piano music works best. Organ and songs work, but rhythms under lyrics are weaker.
- homr ignores dynamics, articulation and double sharps/flats, and may put crossed-hand notes on the wrong staff.
- Recognition can misread notes. Fix them in MuseScore (or similar) using the MusicXML download.
- Nothing is stored on the server. Download what you want to keep.

## Run locally

```bash
uv sync
uv run streamlit run app.py
```

## Tests

```bash
uv run pytest            # fast suite
uv run pytest -m slow    # runs real homr (about a minute); needs `python -m bench.build` first
```

## Benchmark

Synthetic test pages are built from public-domain pieces bundled with music21, then degraded to
look like scans and phone photos. The runner pins homr to 2 CPUs to imitate Streamlit Community Cloud.

```bash
uv run python -m bench.build
uv run python -m bench.run --subset full --jobs 2
```

Results and tuning decisions are in [docs/benchmark.md](docs/benchmark.md). On this benchmark, a page
takes under a minute and under 2 GB of memory.

## Deploying to Streamlit Community Cloud

1. Create a **public** repository on your GitHub account and push this repo's `main` branch to it.
   Public is the simplest way to meet homr's AGPL licence.
2. In `app.py`, set `SOURCE_URL` to that repository's URL, then commit and push.
3. Sign in at [share.streamlit.io](https://share.streamlit.io) with GitHub → **Create app** → pick the
   repository, branch `main`, main file `app.py`.
4. Under **Advanced settings**, choose **Python 3.12** (to match `.python-version`).
5. Deploy and share the `*.streamlit.app` link with friends.

Community Cloud installs dependencies from `uv.lock` automatically. Keep it the only dependency file
(no `requirements.txt`). The app sleeps after 12 hours without visitors. The first visit after that,
and the first upload after a restart (when homr fetches its ~150 MB of models), are slower.

## Licence

AGPL-3.0-or-later. See [LICENSE](LICENSE).
