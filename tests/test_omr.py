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


def test_homr_command_runs_homr_module_with_this_python_and_skips_titles():
    import sys

    command = homr_command(Path("/tmp/page.png"))
    assert command[:3] == [sys.executable, "-m", "homr.main"]
    assert "--no-title" in command and command[-1] == "/tmp/page.png"


def _fake_homr_install(root: Path) -> Path:
    package = root / "site-packages" / "homr"
    for sub in ("segmentation", "transformer"):
        (package / sub).mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "main.py").write_text("# homr")
    return package


def test_writable_install_runs_in_place(tmp_path, monkeypatch):
    from sheet_transposer import omr

    monkeypatch.setattr(omr, "_installed_homr_dir", lambda: _fake_homr_install(tmp_path))
    monkeypatch.setattr(omr, "WRITABLE_HOMR_ROOT", tmp_path / "copy")
    assert omr.homr_python_path() is None


def test_read_only_install_runs_from_a_writable_copy(tmp_path, monkeypatch):
    import os
    import stat

    from sheet_transposer import omr

    package = _fake_homr_install(tmp_path)
    for directory in (package / "segmentation", package / "transformer", package):
        directory.chmod(stat.S_IRUSR | stat.S_IXUSR)  # like Streamlit Cloud's site-packages
    try:
        monkeypatch.setattr(omr, "_installed_homr_dir", lambda: package)
        monkeypatch.setattr(omr, "WRITABLE_HOMR_ROOT", tmp_path / "copy")
        root = omr.homr_python_path()
        assert root == tmp_path / "copy"
        assert (root / "homr" / "main.py").read_text() == "# homr"
        assert os.access(root / "homr" / "segmentation", os.W_OK)
        (root / "homr" / "segmentation" / "model.onnx").write_text("downloaded")
        assert omr.homr_python_path() == root  # reused, not recopied
        assert (root / "homr" / "segmentation" / "model.onnx").exists()
    finally:
        for directory in (package, package / "segmentation", package / "transformer"):
            directory.chmod(stat.S_IRWXU)


def test_default_runner_puts_the_writable_copy_first_on_pythonpath(tmp_path, monkeypatch):
    from sheet_transposer import omr

    seen = {}

    def fake_run(command, **kwargs):
        seen["env"] = kwargs["env"]
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(omr, "homr_python_path", lambda: tmp_path / "copy")
    monkeypatch.setattr(omr.subprocess, "run", fake_run)
    omr._run_homr(Path("/tmp/page.png"), 10)
    assert seen["env"]["PYTHONPATH"].split(":")[0] == str(tmp_path / "copy")


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


def test_failure_details_include_homr_output():
    def fake(image: Path, timeout_s: int) -> None:
        raise subprocess.CalledProcessError(1, "homr", output=b"loading", stderr=b"Traceback...\nOSError: read-only")

    with pytest.raises(OmrError) as caught:
        recognise(b"png", runner=fake)
    assert "OSError: read-only" in caught.value.details


def test_missing_output_details_include_homr_output():
    def fake(image: Path, timeout_s: int) -> str:
        return "An error occurred while processing page.png: No noteheads or clefs found"

    with pytest.raises(OmrError) as caught:
        recognise(b"png", runner=fake)
    assert "No noteheads" in caught.value.details
