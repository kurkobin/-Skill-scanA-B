"""图片读取与尺寸对齐。"""
from __future__ import annotations

from typing import Tuple

from PIL import Image

RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS


def load_image(path: str) -> Image.Image:
    """读取图片并统一为 RGB。"""
    img = Image.open(path)
    img = img.convert("RGB")
    img.load()
    return img


def align(im_a: Image.Image, im_b: Image.Image, max_width: int = 1280) -> Tuple[Image.Image, Image.Image]:
    """把两张图缩放到相同尺寸，便于逐像素比较。

    以图 A 的宽高比为基准。对同源拍摄/截图的成分表（常见情况）效果最好；
    若两张图来自差异很大的设备，透视/比例差异会降低像素对比的准确性。
    """
    wa, ha = im_a.size
    wb, hb = im_b.size
    if wa == 0 or ha == 0:
        return im_a, im_b
    target_w = int(min(max_width, max(wa, wb)))
    target_h = max(1, round(target_w * (ha / wa)))
    if (wa, ha) != (target_w, target_h):
        im_a = im_a.resize((target_w, target_h), RESAMPLE)
    if (wb, hb) != (target_w, target_h):
        im_b = im_b.resize((target_w, target_h), RESAMPLE)
    return im_a, im_b
