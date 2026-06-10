from __future__ import annotations

import io

from PIL import Image, ImageOps

MAX_DIMENSION = 1600
# Bluesky's blob limit is ~976KB, the strictest of the supported networks
MAX_BYTES = 976 * 1024
QUALITY_START = 95
QUALITY_FLOOR = 40
QUALITY_STEP = 10

INSTAGRAM_SIZES = {
    "portrait": (1080, 1350),
    "square": (1080, 1080),
}


class ImageProcessingError(Exception):
    pass


def _to_rgb(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").split()[-1])
        return background
    return image.convert("RGB")


def _encode_jpeg(image: Image.Image) -> bytes:
    quality = QUALITY_START
    while True:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, progressive=True, optimize=True)
        data = buffer.getvalue()
        if len(data) <= MAX_BYTES:
            return data
        if quality <= QUALITY_FLOOR:
            raise ImageProcessingError(
                f"could not fit image under {MAX_BYTES} bytes (got {len(data)})"
            )
        quality -= QUALITY_STEP


def process_upload(data: bytes) -> tuple[bytes, int, int]:
    """Normalize an uploaded image: orient, strip EXIF, fit 1600x1600, JPEG under 976KB."""
    try:
        image = Image.open(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise ImageProcessingError(f"cannot open image: {exc}") from exc
    image = _to_rgb(image)
    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
    return _encode_jpeg(image), image.width, image.height


def instagram_variant(data: bytes, aspect: str = "portrait") -> bytes:
    """Center-crop and resize to an Instagram-friendly frame."""
    if aspect not in INSTAGRAM_SIZES:
        raise ImageProcessingError(f"unknown instagram aspect: {aspect}")
    target_w, target_h = INSTAGRAM_SIZES[aspect]
    image = _to_rgb(Image.open(io.BytesIO(data)))
    cropped = ImageOps.fit(image, (target_w, target_h), Image.LANCZOS, centering=(0.5, 0.5))
    return _encode_jpeg(cropped)
