import subprocess
import threading
import time
from pathlib import Path

import pytest

from sheet_transposer.omr import OmrError, homr_command, recognise


def test_returns_musicxml_written_beside_image():
    def fake(image: Path, timeout_s: int) -> None:
        image.with_suffix(".musicxml").write_text("<score-partwise/>")

    assert recognise(b"png", runner=fake) == "<score-partwise/>"


def test_nonzero_exit_raises_omr_error():
    def fake(image: Path, timeout_s: int) -> None:
        raise subprocess.CalledProcessError(1, "homr")

    with pytest.raises(OmrError, match="couldn't read"):
        recognise(b"png", runner=fake)


def test_missing_output_raises_omr_error():
    with pytest.raises(OmrError, match="couldn't read"):
        recognise(b"png", runner=lambda image, timeout_s: None)


def test_timeout_raises_omr_error():
    def fake(image: Path, timeout_s: int) -> None:
        raise subprocess.TimeoutExpired("homr", timeout_s)

    with pytest.raises(OmrError, match="too long"):
        recognise(b"png", runner=fake)


def test_runs_are_serialised():
    intervals = []

    def fake(image: Path, timeout_s: int) -> None:
        start = time.monotonic()
        time.sleep(0.2)
        intervals.append((start, time.monotonic()))
        image.with_suffix(".musicxml").write_text("<x/>")

    threads = [threading.Thread(target=recognise, args=(b"png",), kwargs={"runner": fake}) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    (first_start, first_end), (second_start, _) = sorted(intervals)
    assert second_start >= first_end


def test_temp_files_are_removed():
    seen = []

    def fake(image: Path, timeout_s: int) -> None:
        seen.append(image)
        image.with_suffix(".musicxml").write_text("<x/>")

    recognise(b"png", runner=fake)
    assert not seen[0].parent.exists()


def test_homr_command_uses_venv_executable():
    command = homr_command(Path("/tmp/page.png"))
    assert command[0].endswith("/homr") and command[1] == "/tmp/page.png"


def test_homr_failing_to_start_raises_omr_error():
    def fake(image: Path, timeout_s: int) -> None:
        raise FileNotFoundError("homr")

    with pytest.raises(OmrError):
        recognise(b"png", runner=fake)


def test_is_busy_only_while_another_thread_holds_the_lock():
    from sheet_transposer.omr import LOCK, is_busy

    assert not is_busy()
    holding, release = threading.Event(), threading.Event()

    def hold():
        with LOCK:
            holding.set()
            release.wait()

    worker = threading.Thread(target=hold)
    worker.start()
    holding.wait()
    try:
        assert is_busy()
    finally:
        release.set()
        worker.join()
    assert not is_busy()


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(-9, "homr"),  # killed by the out-of-memory killer
        subprocess.CalledProcessError(1, "homr", stderr=b"...\nMemoryError\n"),
        subprocess.CalledProcessError(1, "homr", stderr=b"onnxruntime ... std::bad_alloc"),
    ],
)
def test_out_of_memory_has_its_own_message(error):
    def fake(image: Path, timeout_s: int) -> None:
        raise error

    with pytest.raises(OmrError, match="Image processing engine out of memory"):
        recognise(b"png", runner=fake)
