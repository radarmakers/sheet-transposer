"""Run homr over benchmark pages under a CPU pin; score, time and measure each one.

Usage: python -m bench.run [--subset smoke|full] [--jobs 1|2] [--max-side N] [--variants clean phone ...]
Writes bench/results/<UTC timestamp>.csv and prints mean scores by kind and variant.
"""

import argparse
import csv
import json
import queue
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from bench.build import DATA_DIR
from bench.degrade import VARIANTS
from bench.metrics import PageScore, compare
from bench.pieces import SMOKE_IDS
from sheet_transposer.images import MAX_SIDE, prepare_image
from sheet_transposer.scoreio import parse_musicxml

RESULTS_DIR = Path(__file__).parent / "results"
CPU_SETS = ["0,1", "2,3"]  # one disjoint pair of CPUs per parallel job
SCORE_FIELDS = [f.name for f in fields(PageScore)]


def load_manifest(subset: str) -> list[dict]:
    entries = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    return [e for e in entries if subset == "full" or e["page_id"] in SMOKE_IDS]


def run_one(entry: dict, variant: str, cpus: str, max_side: int, autocontrast: bool = False) -> dict:
    page_dir = DATA_DIR / entry["page_id"]
    row = {"page_id": entry["page_id"], "kind": entry["kind"], "variant": variant, "max_side": max_side}
    with tempfile.TemporaryDirectory(prefix="bench-") as workdir:
        image = Path(workdir) / "page.png"
        prepared = prepare_image((page_dir / f"{variant}.png").read_bytes(), max_side=max_side,
                                 **({"autocontrast": True} if autocontrast else {}))
        image.write_bytes(prepared)
        completed = subprocess.run(
            ["taskset", "-c", cpus, sys.executable, "-m", "bench.measure_one", str(image)],
            capture_output=True, text=True, check=True,
        )
        measured = json.loads(completed.stdout.strip().splitlines()[-1])
        row.update(seconds=measured["seconds"], peak_rss_mb=measured["peak_rss_mb"], ok=measured["ok"])
        score = None
        if measured["ok"]:
            try:
                truth = parse_musicxml((page_dir / "truth.musicxml").read_text(encoding="utf-8"))
                got = parse_musicxml(Path(measured["musicxml_path"]).read_text(encoding="utf-8"))
                score = compare(truth, got, entry["truth_key"])
            except ValueError:
                row["ok"] = False
    row.update(asdict(score) if score else {name: 0 for name in SCORE_FIELDS})
    return row


def run_pages(entries: list[dict], variants: list[str], *, jobs: int = 1, max_side: int = MAX_SIDE,
              autocontrast: bool = False) -> list[dict]:
    cpu_pool: queue.Queue = queue.Queue()
    for cpus in CPU_SETS[:jobs]:
        cpu_pool.put(cpus)

    def task(work: tuple[dict, str]) -> dict:
        cpus = cpu_pool.get()
        try:
            row = run_one(*work, cpus=cpus, max_side=max_side, autocontrast=autocontrast)
            print(f"{row['page_id']:40s} {row['variant']:6s} {row['seconds']:6.1f}s "
                  f"{row['peak_rss_mb']:7.0f}MB f1={row['note_f1']:.2f}", flush=True)
            return row
        finally:
            cpu_pool.put(cpus)

    work = [(entry, variant) for entry in entries for variant in variants]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(task, work))


def summarise(rows: list[dict]) -> str:
    metrics = ["note_f1", "duration_acc", "key_sig_ok", "key_ok", "bars_ok", "full_bars_frac", "seconds", "peak_rss_mb"]
    lines = ["| kind | variant | n | ok | " + " | ".join(metrics) + " |",
             "|---" * (len(metrics) + 4) + "|"]
    groups = sorted({(r["kind"], r["variant"]) for r in rows})
    for kind, variant in groups:
        group = [r for r in rows if r["kind"] == kind and r["variant"] == variant]
        values = []
        for m in metrics:
            agg = max if m in ("seconds", "peak_rss_mb") else mean
            label = "max " if agg is max else ""
            values.append(f"{label}{agg(float(r[m]) for r in group):.2f}")
        ok = sum(1 for r in group if r["ok"])
        lines.append(f"| {kind} | {variant} | {len(group)} | {ok} | " + " | ".join(values) + " |")
    return "\n".join(lines)


def write_csv(rows: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subset", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--jobs", type=int, choices=[1, 2], default=1)
    parser.add_argument("--max-side", type=int, default=MAX_SIDE)
    parser.add_argument("--autocontrast", action="store_true")
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS))
    args = parser.parse_args()
    rows = run_pages(load_manifest(args.subset), args.variants, jobs=args.jobs,
                     max_side=args.max_side, autocontrast=args.autocontrast)
    print(f"\nwrote {write_csv(rows)}\n")
    print(summarise(rows))
