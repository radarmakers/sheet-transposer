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
