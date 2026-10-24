"""Image utilities and bed-only calibration metadata; no scene inspection."""
from dataclasses import dataclass
import io
import numpy as np
from PIL import Image, ImageOps


def read_image(data):
    with Image.open(io.BytesIO(data)) as image:
        if image.width*image.height > 16_000_000:
            raise ValueError('Images must not exceed 16 megapixels.')
        return ImageOps.exif_transpose(image).convert('RGB').copy()


def jpeg(image):
    out=io.BytesIO();image.save(out,'JPEG',quality=90)
    return out.getvalue()


def pixels(image):
    small=image.copy();small.thumbnail((480,360),Image.Resampling.BILINEAR)
    return np.asarray(small,dtype=np.float32)/255


@dataclass
class BedCalibration:
    camera: dict
    image_size: tuple
