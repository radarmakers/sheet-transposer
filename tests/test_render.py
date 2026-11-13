from sheet_transposer.render import render_pdf, render_png, render_svg_pages


def test_svg_pages_for_twelve_bars(k545_xml):
    pages = render_svg_pages(k545_xml)
    assert len(pages) == 1 and pages[0].lstrip().startswith("<svg")
    assert "pgFoot" not in pages[0]  # no visible "engraved with Verovio" footer


def test_png_is_png(k545_xml):
    png = render_png(render_svg_pages(k545_xml)[0], width_px=1240)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_pdf_has_one_page_per_svg(k545_xml):
    pdf = render_pdf(k545_xml)
    assert pdf.startswith(b"%PDF") and b"/Count 1" in pdf


def test_png_has_opaque_white_background(k545_xml):
    import io

    from PIL import Image

    image = Image.open(io.BytesIO(render_png(render_svg_pages(k545_xml)[0], width_px=600)))
    assert image.convert("RGBA").getpixel((2, 2)) == (255, 255, 255, 255)


def test_renders_from_another_thread(k545_xml):
    # Streamlit runs app scripts on worker threads; Verovio's default resource path is per-thread.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        pages = pool.submit(render_svg_pages, k545_xml).result()
    assert len(pages) == 1


def _stderr_of_threaded_render(musicxml: str) -> str:
    """Render on a worker thread (as Streamlit does) in a fresh process; return what it printed."""
    import subprocess
    import sys

    script = (
        "import sys\n"
        "from concurrent.futures import ThreadPoolExecutor\n"
        "from sheet_transposer.render import render_svg_pages\n"
        "with ThreadPoolExecutor(1) as pool:\n"
        "    assert pool.submit(render_svg_pages, sys.stdin.read()).result()\n"
    )
    done = subprocess.run([sys.executable, "-c", script], input=musicxml, capture_output=True, text=True, check=True)
    return done.stdout + done.stderr


def test_threaded_render_prints_no_font_errors(k545_xml):
    assert "[Error]" not in _stderr_of_threaded_render(k545_xml)


def test_harmless_engraving_warnings_are_not_printed(k545_xml):
    unfinished_slur = k545_xml.replace("<notations>", '<notations><slur type="start" number="9"/>', 1)
    assert "[Warning]" not in _stderr_of_threaded_render(unfinished_slur)
