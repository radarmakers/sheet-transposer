"""Glue for the app: read one uploaded page, then produce transposed outputs."""

from collections.abc import Callable
from dataclasses import dataclass

from sheet_transposer import omr
from sheet_transposer.images import ImageError, prepare_image
from sheet_transposer.keys import KeyResult, detect_key, key_from_label
from sheet_transposer.render import render_pdf, render_svg_pages
from sheet_transposer.scoreio import parse_musicxml, to_musicxml
from sheet_transposer.transpose import semitone_shift, shift_label, transpose_score


class ReadError(Exception):
    """Reading the page failed; the message is safe to show to users."""


@dataclass(frozen=True)
class Page:
    musicxml: str  # as recognised
    detected: KeyResult


@dataclass(frozen=True)
class Outputs:
    musicxml: str
    svgs: list[str]
    pdf: bytes
    shift: str


def read_page(upload: bytes, *, recognise: Callable[[bytes], str] = omr.recognise) -> Page:
    """Prepare the image, recognise the music, and detect its key."""
    try:
        musicxml = recognise(prepare_image(upload))
        score = parse_musicxml(musicxml)
    except (ImageError, omr.OmrError) as error:
        raise ReadError(str(error)) from error
    except ValueError as error:
        raise ReadError(
            "Sorry — we couldn't read the music in that image. Try a flatter, brighter photo."
        ) from error
    return Page(musicxml=musicxml, detected=detect_key(score))


def build_outputs(page: Page, original: str, target: str) -> Outputs:
    """Transpose from the (possibly user-corrected) original key to the target; render it."""
    src, dst = key_from_label(original), key_from_label(target)
    moved = transpose_score(parse_musicxml(page.musicxml), src, dst)
    musicxml = to_musicxml(moved)
    return Outputs(
        musicxml=musicxml,
        svgs=render_svg_pages(musicxml, fit_height=True),
        pdf=render_pdf(musicxml),
        shift=shift_label(semitone_shift(src, dst)),
    )
