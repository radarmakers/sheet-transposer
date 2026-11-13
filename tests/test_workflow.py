import io

import pytest
from PIL import Image

from sheet_transposer.keys import key_label
from sheet_transposer.scoreio import parse_musicxml
from sheet_transposer.workflow import ReadError, build_outputs, read_page


@pytest.fixture(scope="module")
def png():
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture(scope="module")
def page(png, k545_xml):
    return read_page(png, recognise=lambda image: k545_xml)


def test_read_page_detects_c_major(page):
    assert key_label(page.detected.key) == "C major"


def test_read_page_wraps_unparseable_xml(png):
    with pytest.raises(ReadError, match="couldn't read"):
        read_page(png, recognise=lambda image: "garbage")


def test_read_page_wraps_image_error(k545_xml):
    with pytest.raises(ReadError, match="photo or scan"):
        read_page(b"not an image", recognise=lambda image: k545_xml)


def test_read_page_wraps_omr_error(png):
    from sheet_transposer.omr import OmrError

    def failing(image):
        raise OmrError("Sorry — we couldn't read any music in that image.")

    with pytest.raises(ReadError, match="couldn't read any music"):
        read_page(png, recognise=failing)


def test_build_outputs_transposes_and_renders(page):
    outputs = build_outputs(page, "C major", "D major")
    assert outputs.shift == "up 2 semitones"
    assert outputs.svgs and outputs.pdf.startswith(b"%PDF")
    signature = parse_musicxml(outputs.musicxml).recurse().getElementsByClass("KeySignature").first()
    assert signature.sharps == 2


def test_build_outputs_with_corrected_original(page):
    assert build_outputs(page, "A minor", "B minor").shift == "up 2 semitones"


def test_build_outputs_same_key_is_no_change(page):
    assert build_outputs(page, "C major", "C major").shift == "no change"
