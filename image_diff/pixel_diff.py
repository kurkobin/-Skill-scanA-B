"""像素级差异检测 + 对比图渲染。"""
from __future__ import annotations

from collections import deque
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .models import DiffRegion


def _dilate(mask: np.ndarray, size: int = 3) -> np.ndarray:
    if size <= 1:
        return mask
    img = Image.fromarray((mask.astype(np.uint8) * 255))
    img = img.filter(ImageFilter.MaxFilter(size))
    return np.asarray(img) > 0


def _components(mask: np.ndarray, min_area: int, min_dim: int = 3,
                max_pixels: int = 300000) -> List[DiffRegion]:
    total = int(mask.sum())
    if total == 0:
        return []
    if total > max_pixels:
        ys, xs = np.nonzero(mask)
        return [DiffRegion(
            bbox=(int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1),
            area=total,
        )]

    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    regions: List[DiffRegion] = []
    ys, xs = np.nonzero(mask)
    coords = list(zip(ys.tolist(), xs.tolist()))

    for y, x in coords:
        if visited[y, x]:
            continue
        q = deque([(y, x)])
        visited[y, x] = True
        cnt = 0
        minx = maxx = x
        miny = maxy = y
        while q:
            cy, cx = q.popleft()
            cnt += 1
            if cx < minx:
                minx = cx
            if cx > maxx:
                maxx = cx
            if cy < miny:
                miny = cy
            if cy > maxy:
                maxy = cy
            for dy in (-1, 0, 1):
                ny = cy + dy
                if ny < 0 or ny >= h:
                    continue
                for dx in (-1, 0, 1):
                    nx = cx + dx
                    if nx < 0 or nx >= w:
                        continue
                    if mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        q.append((ny, nx))
        if cnt >= min_area and (maxx - minx + 1) >= min_dim and (maxy - miny + 1) >= min_dim:
            regions.append(DiffRegion(bbox=(minx, miny, maxx + 1, maxy + 1), area=cnt))

    regions.sort(key=lambda r: (r.bbox[1], r.bbox[0]))
    return regions


def diff_regions(im_a: Image.Image, im_b: Image.Image, threshold: int = 30,
                 min_area: int = 120, dilation: int = 3) -> Tuple[List[DiffRegion], np.ndarray]:
    diff = ImageChops.difference(im_a, im_b).convert("L")
    arr = np.asarray(diff)
    mask = arr > threshold
    mask = _dilate(mask, dilation)
    regions = _components(mask, min_area)
    return regions, mask


def _load_font(size: int):
    for name in ("msyh.ttc", "simhei.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_comparison(im_a: Image.Image, im_b: Image.Image, regions: List[DiffRegion],
                      out_path: str, gap: int = 28, header: int = 40,
                      color: Tuple[int, int, int] = (239, 68, 68)) -> str:
    """把 A、B 并排画在一张图上，差异区域两边都画红框。"""
    wa, ha = im_a.size
    wb, hb = im_b.size
    height = max(ha, hb)
    width = wa + gap + wb
    canvas = Image.new("RGB", (width, header + height), "white")
    canvas.paste(im_a.convert("RGB"), (0, header))
    canvas.paste(im_b.convert("RGB"), (wa + gap, header))

    draw = ImageDraw.Draw(canvas)
    font = _load_font(20)
    draw.text((8, 9), "旧版", fill=(31, 41, 55), font=font)
    draw.text((wa + gap + 8, 9), "新版", fill=(31, 41, 55), font=font)

    for region in regions:
        x0, y0, x1, y1 = region.bbox
        for offset in (0, wa + gap):
            draw.rectangle(
                [offset + x0, header + y0, offset + x1 - 1, header + y1 - 1],
                outline=color, width=3,
            )
    canvas.save(out_path)
    return out_path


def crop_regions(im_a: Image.Image, regions: List[DiffRegion], out_dir: str,
                 prefix: str = "region", pad: int = 6) -> List[str]:
    import os
    paths: List[str] = []
    w, h = im_a.size
    for i, r in enumerate(regions, 1):
        x0, y0, x1, y1 = r.bbox
        box = (max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        crop = im_a.crop(box)
        path = os.path.join(out_dir, f"{prefix}_{i:02d}.png")
        crop.save(path)
        paths.append(path)
    return paths
