"""Turn an uploaded photo or scan into an upright, size-bounded PNG for homr."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 3000


class ImageError(Exception):
    """The upload isn't a readable image; the message is safe to show to users."""


def prepare_image(data: bytes, *, max_side: int = MAX_SIDE, autocontrast: bool = False) -> bytes:
    """Return PNG bytes: EXIF-rotated upright, flattened onto white, RGB, longest side ≤ max_side.

    `autocontrast` converts to greyscale and stretches the tones (helps dim or washed-out photos).
    """
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as error:
        raise ImageError(
            "That file isn't a photo or scan we can read — please upload a JPG or PNG."
        ) from error
    image = ImageOps.exif_transpose(image)
    image = _flatten_onto_white(image)
    if autocontrast:
        image = ImageOps.autocontrast(image.convert("L"), cutoff=1).convert("RGB")
    image.thumbnail((max_side, max_side), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _flatten_onto_white(image: Image.Image) -> Image.Image:
    """Transparent areas become white (a plain RGB convert would make them black)."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")
