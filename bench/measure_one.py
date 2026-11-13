"""Run homr once on an image and print time and peak memory as one JSON line.

Usage: python -m bench.measure_one IMAGE
Peak memory comes from RUSAGE_CHILDREN, which is exact here because this
process starts exactly one child.
"""

import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from sheet_transposer.omr import DEFAULT_TIMEOUT_S, homr_command


def measure(image: Path) -> dict:
    start = time.perf_counter()
    try:
        completed = subprocess.run(homr_command(image), capture_output=True, timeout=DEFAULT_TIMEOUT_S)
        ok = completed.returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    seconds = time.perf_counter() - start
    peak_rss_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    output = image.with_suffix(".musicxml")
    ok = ok and output.exists()
    return {
        "seconds": round(seconds, 2),
        "peak_rss_mb": round(peak_rss_mb, 1),
        "ok": ok,
        "musicxml_path": str(output) if ok else None,
    }


if __name__ == "__main__":
    print(json.dumps(measure(Path(sys.argv[1]))))
