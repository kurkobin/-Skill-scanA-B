"""image_diff —— 两张图片对比，定位并提取差异内容（成分表场景优化）。

用法（库）：
    from image_diff import compare_images
    result = compare_images("a.png", "b.png", mode="ingredient", output_dir="out")
"""
from .models import OCRLine, DiffRegion, IngredientDiff, CompareResult
from .pipeline import compare_images

__all__ = ["OCRLine", "DiffRegion", "IngredientDiff", "CompareResult", "compare_images"]
__version__ = "0.1.0"
