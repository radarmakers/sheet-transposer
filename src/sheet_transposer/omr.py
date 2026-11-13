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
# Re-entrant so callers can also hold it while preparing the image (workflow.read_page).
LOCK = threading.RLock()

Runner = Callable[[Path, int], str | None]  # returns homr's console output, if captured

DETAILS_TAIL_CHARS = 4000


class OmrError(Exception):
    """Recognition failed; the message is safe to show to users, `details` is homr's own output."""

    def __init__(self, message: str, details: str = "") -> None:
        super().__init__(message)
        self.details = details


def homr_command(image: Path) -> list[str]:
    """Command line that runs the homr installed alongside this Python."""
    return [str(Path(sys.executable).parent / "homr"), str(image)]


def _run_homr(image: Path, timeout_s: int) -> str:
    completed = subprocess.run(homr_command(image), timeout=timeout_s, check=True, capture_output=True)
    return _console_text(completed.stdout, completed.stderr)


def _console_text(stdout: bytes | None, stderr: bytes | None) -> str:
    text = b"\n".join(part for part in (stdout, stderr) if part).decode("utf-8", errors="replace")
    return text[-DETAILS_TAIL_CHARS:]


def _failed(message: str, details: str) -> OmrError:
    print(f"homr failed: {message}\n{details}", file=sys.stderr)  # visible in the host's app logs
    return OmrError(message, details=details)


def recognise(png: bytes, *, runner: Runner | None = None, timeout_s: int = DEFAULT_TIMEOUT_S) -> str:
    """Recognise one page image (PNG bytes) and return MusicXML text."""
    runner = runner or _run_homr
    with LOCK, tempfile.TemporaryDirectory(prefix="omr-") as workdir:
        image = Path(workdir) / "page.png"
        image.write_bytes(png)
        try:
            console = runner(image, timeout_s) or ""
        except subprocess.TimeoutExpired as error:
            details = _console_text(error.stdout, error.stderr)
            raise _failed("Reading the music took too long. Try a smaller or clearer photo.", details) from error
        except subprocess.CalledProcessError as error:
            details = f"exit code {error.returncode}\n" + _console_text(error.output, error.stderr)
            if _out_of_memory(error):
                raise _failed(
                    "Image processing engine out of memory. Please try again in a minute, "
                    "or with a smaller photo.",
                    details,
                ) from error
            raise _failed(UNREADABLE, details) from error
        except OSError as error:
            raise _failed("Something went wrong starting the music reader. Please try again.", repr(error)) from error
        output = image.with_suffix(".musicxml")
        if not output.exists():
            # homr reports some failures (e.g. "no noteheads found") without a non-zero exit.
            raise _failed(UNREADABLE, console)
        return output.read_text(encoding="utf-8")


def _out_of_memory(error: subprocess.CalledProcessError) -> bool:
    """Killed by a signal (the OOM killer sends SIGKILL), or homr reported an allocation failure."""
    stderr = error.stderr or b""
    return error.returncode < 0 or b"MemoryError" in stderr or b"bad_alloc" in stderr


UNREADABLE = (
    "Sorry — we couldn't read any music in that image. "
    "Try a flatter, brighter photo of printed music."
)


def is_busy() -> bool:
    """True if another thread is reading (or preparing) a page right now."""
    if LOCK.acquire(blocking=False):
        LOCK.release()
        return False
    return True
