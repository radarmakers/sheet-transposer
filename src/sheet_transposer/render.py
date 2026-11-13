"""Engrave MusicXML with Verovio and turn the result into PNG or PDF."""

import io
import re
from importlib.resources import files

import resvg_py
import verovio
from PIL import Image

PDF_PAGE_WIDTH_PX = 1654  # A4 at 200 dpi
PDF_DPI = 200
# Verovio's default resource path is set per thread at import; Streamlit renders on other threads.
VEROVIO_RESOURCES = str(files("verovio") / "data")
# Only real errors on the console; warnings like an unfinished slur in recognised music are noise.
verovio.enableLog(verovio.LOG_ERROR)


def render_svg_pages(
    musicxml: str,
    *,
    page_width: int = 2100,
    page_height: int = 2970,
    scale: int = 40,
    fit_height: bool = False,
) -> list[str]:
    """Engrave MusicXML into one SVG string per page."""
    toolkit = verovio.toolkit(False)  # skip the default font lookup, which fails off the main thread
    toolkit.setResourcePath(VEROVIO_RESOURCES)
    toolkit.setOptions(
        {
            "pageWidth": page_width,
            "pageHeight": page_height,
            "scale": scale,
            "footer": "none",
            "adjustPageHeight": fit_height,
        }
    )
    if not toolkit.loadData(musicxml):
        raise ValueError("Verovio could not load the MusicXML")
    return [_on_white(toolkit.renderToSVG(page)) for page in range(1, toolkit.getPageCount() + 1)]


_ROOT_SVG_TAG = re.compile(r"<svg\b[^>]*>")
_WHITE_PAPER = '<rect width="100%" height="100%" fill="#ffffff"/>'


def _on_white(svg: str) -> str:
    """Verovio's SVG is transparent; give it white paper so notes show on dark-mode pages too."""
    return _ROOT_SVG_TAG.sub(lambda tag: tag.group(0) + _WHITE_PAPER, svg, count=1)


def render_png(svg: str, *, width_px: int) -> bytes:
    """Rasterise one SVG page to PNG bytes on an opaque white background."""
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width_px, background="#ffffff"))


def render_pdf(musicxml: str) -> bytes:
    """Engrave MusicXML to a PDF with one A4 page image per engraved page."""
    pages = [
        Image.open(io.BytesIO(render_png(svg, width_px=PDF_PAGE_WIDTH_PX))).convert("RGB")
        for svg in render_svg_pages(musicxml)
    ]
    buffer = io.BytesIO()
    pages[0].save(buffer, "PDF", save_all=True, append_images=pages[1:], resolution=PDF_DPI)
    return buffer.getvalue()
