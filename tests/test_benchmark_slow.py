import tomllib
from pathlib import Path
from statistics import mean

import pytest

from bench.pieces import PIECES
from bench.run import load_manifest, run_pages

THRESHOLDS = tomllib.loads((Path(__file__).parents[1] / "bench" / "thresholds.toml").read_text())
PIANO_IDS = {p.id for p in PIECES if p.kind == "piano"}


@pytest.mark.slow
def test_smoke_benchmark_meets_thresholds():
    entries = [e for e in load_manifest("smoke") if e["piece_id"] in PIANO_IDS]
    assert entries, "run `python -m bench.build` first"
    rows = run_pages(entries, ["clean", "phone"], jobs=2)
    assert all(row["ok"] for row in rows)
    assert all(row["seconds"] <= THRESHOLDS["max_seconds"] for row in rows)
    assert all(row["peak_rss_mb"] <= THRESHOLDS["max_peak_rss_mb"] for row in rows)
    for metric in ("note_f1", "key_ok", "full_bars_frac"):
        assert mean(float(row[metric]) for row in rows) >= THRESHOLDS[metric], metric
