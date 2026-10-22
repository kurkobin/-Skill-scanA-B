"""对比流水线：对齐 -> 像素差异 -> 提取成分（普通小节 / 表格列）-> 成分对比。"""
from __future__ import annotations

import os
from typing import Optional

from . import align, heuristics, pixel_diff, text_diff
from .models import CompareResult, IngredientDiff
from .ocr import BaseOCRBackend, OCRUnavailableError, get_default_backend


def compare_images(
    path_a: str,
    path_b: str,
    mode: str = "ingredient",
    output_dir: Optional[str] = None,
    max_width: int = 1280,
    threshold: int = 30,
    min_area: int = 120,
    ocr_backend: Optional[BaseOCRBackend] = None,
) -> CompareResult:
    if mode not in ("ingredient", "text", "pixel"):
        raise ValueError(f"未知 mode: {mode}")

    im_a = align.load_image(path_a)
    im_b = align.load_image(path_b)
    im_a, im_b = align.align(im_a, im_b, max_width=max_width)

    regions, _mask = pixel_diff.diff_regions(
        im_a, im_b, threshold=threshold, min_area=min_area
    )
    result = CompareResult(mode=mode, regions=regions)

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        result.highlight_path = os.path.join(output_dir, "diff_compare.png")
        pixel_diff.render_comparison(im_a, im_b, regions, result.highlight_path)
        result.region_paths = pixel_diff.crop_regions(im_a, regions, output_dir)

    if mode == "pixel":
        return result

    backend = ocr_backend or get_default_backend()
    try:
        result.ocr_a = backend.recognize(im_a)
        result.ocr_b = backend.recognize(im_b)
    except OCRUnavailableError as exc:
        result.ocr_error = str(exc)
        return result

    result.text_a = "\n".join(line.text for line in result.ocr_a)
    result.text_b = "\n".join(line.text for line in result.ocr_b)

    width = im_a.width
    result.ingredient_text_a, result.ingredients_a = heuristics.extract_ingredients_from_lines(
        result.ocr_a, width
    )
    result.ingredient_text_b, result.ingredients_b = heuristics.extract_ingredients_from_lines(
        result.ocr_b, width
    )

    is_ing, score = heuristics.looks_like_ingredient_list(
        result.ingredient_text_a + "\n" + result.ingredient_text_b
    )
    result.is_ingredient_list = is_ing
    result.ingredient_score = score

    if mode == "ingredient":
        added, removed, changed = text_diff.diff_lists(
            result.ingredients_a, result.ingredients_b
        )
        result.ingredient_diff = IngredientDiff(
            added=added, removed=removed, changed=changed
        )

    confidences = [
        line.confidence for line in (result.ocr_a + result.ocr_b) if line.confidence
    ]
    result.avg_confidence = (
        sum(confidences) / len(confidences) if confidences else 0.0
    )
    result.low_confidence = [
        line.text
        for line in (result.ocr_a + result.ocr_b)
        if line.confidence and line.confidence < 0.6
    ]
    return result
