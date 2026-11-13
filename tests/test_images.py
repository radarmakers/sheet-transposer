import io

import pytest
from PIL import Image

from sheet_transposer.images import MAX_SIDE, ImageError, prepare_image


def _encode(image: Image.Image, fmt: str = "PNG", **kwargs) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, fmt, **kwargs)
    return buffer.getvalue()


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_exif_rotation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90° clockwise to display
    data = _encode(Image.new("RGB", (400, 200), "white"), "JPEG", exif=exif)
    assert _open(prepare_image(data)).size == (200, 400)


def test_large_image_is_downscaled():
    out = _open(prepare_image(_encode(Image.new("RGB", (8000, 6000), "white"), "JPEG")))
    assert max(out.size) == MAX_SIDE == 3000
    assert abs(out.size[1] - 2250) <= 1


def test_small_image_is_not_upscaled():
    assert _open(prepare_image(_encode(Image.new("RGB", (1000, 800), "white")))).size == (1000, 800)


@pytest.mark.parametrize("mode", ["L", "RGBA"])
def test_greyscale_and_rgba_become_rgb(mode):
    assert _open(prepare_image(_encode(Image.new(mode, (50, 50))))).mode == "RGB"


def test_transparent_png_gets_white_background():
    out = _open(prepare_image(_encode(Image.new("RGBA", (50, 50), (0, 0, 0, 0)))))
    assert out.getpixel((10, 10)) == (255, 255, 255)


def test_output_is_png():
    assert prepare_image(_encode(Image.new("RGB", (50, 50)), "JPEG"))[:8] == b"\x89PNG\r\n\x1a\n"


def test_non_image_raises_image_error():
    with pytest.raises(ImageError, match="photo or scan"):
        prepare_image(b"%PDF-1.4 not an image")


def test_autocontrast_stretches_a_washed_out_page():
    washed = Image.new("L", (100, 100), 220)
    washed.paste(170, (40, 40, 60, 60))  # faint grey "ink"
    out = _open(prepare_image(_encode(washed), autocontrast=True)).convert("L")
    low, high = out.getextrema()
    assert low < 50 and high > 240


def test_autocontrast_is_off_by_default():
    washed = Image.new("L", (100, 100), 220)
    washed.paste(170, (40, 40, 60, 60))
    assert _open(prepare_image(_encode(washed))).convert("L").getextrema() == (170, 220)
