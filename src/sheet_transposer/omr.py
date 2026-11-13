"""Run homr (optical music recognition) on one page image.

homr writes `<stem>.musicxml` (and a `<stem>_teaser.png` preview) beside the
input image. Its ONNX models (~150 MB) live inside the installed homr package
and are fetched on the first run.
"""

import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

DEFAULT_TIMEOUT_S = 600

# Only one recognition at a time per process, to stay inside Community Cloud's memory.
_LOCK = threading.Lock()

Runner = Callable[[Path, int], None]


class OmrError(Exception):
    """Recognition failed; the message is safe to show to users."""


def homr_command(image: Path) -> list[str]:
    """Command line that runs the homr installed alongside this Python."""
    return [str(Path(sys.executable).parent / "homr"), str(image)]


def _run_homr(image: Path, timeout_s: int) -> None:
    subprocess.run(homr_command(image), timeout=timeout_s, check=True, capture_output=True)


def recognise(png: bytes, *, runner: Runner | None = None, timeout_s: int = DEFAULT_TIMEOUT_S) -> str:
    """Recognise one page image (PNG bytes) and return MusicXML text."""
    runner = runner or _run_homr
    with _LOCK, tempfile.TemporaryDirectory(prefix="omr-") as workdir:
        image = Path(workdir) / "page.png"
        image.write_bytes(png)
        try:
            runner(image, timeout_s)
        except subprocess.TimeoutExpired as error:
            raise OmrError("Reading the music took too long. Try a smaller or clearer photo.") from error
        except subprocess.CalledProcessError as error:
            raise _unreadable() from error
        output = image.with_suffix(".musicxml")
        if not output.exists():
            # homr reports some failures (e.g. "no noteheads found") without a non-zero exit.
            raise _unreadable()
        return output.read_text(encoding="utf-8")


def _unreadable() -> OmrError:
    return OmrError(
        "Sorry — we couldn't read any music in that image. "
        "Try a flatter, brighter photo of printed music."
    )
