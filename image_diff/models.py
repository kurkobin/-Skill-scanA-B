"""数据类型定义。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

Box = List[Tuple[float, float]]


@dataclass
class OCRLine:
    """一行 OCR 结果。"""
    text: str
    box: Box = field(default_factory=list)   # 4 个角点 [(x, y) * 4]
    confidence: float = 0.0


@dataclass
class DiffRegion:
    """一个差异区域。bbox = (x0, y0, x1, y1)，右/下开区间。"""
    bbox: Tuple[int, int, int, int]
    area: int = 0


@dataclass
class IngredientDiff:
    """成分级差异。"""
    added: List[str] = field(default_factory=list)      # 新增
    removed: List[str] = field(default_factory=list)    # 删除
    changed: List[Tuple[str, str]] = field(default_factory=list)  # (旧, 新)


@dataclass
class CompareResult:
    """一次对比的完整结果。"""
    mode: str = "ingredient"
    regions: List[DiffRegion] = field(default_factory=list)
    ocr_a: List[OCRLine] = field(default_factory=list)
    ocr_b: List[OCRLine] = field(default_factory=list)
    text_a: str = ""
    text_b: str = ""
    ingredient_text_a: str = ""
    ingredient_text_b: str = ""
    ingredients_a: List[str] = field(default_factory=list)
    ingredients_b: List[str] = field(default_factory=list)
    ingredient_diff: Optional[IngredientDiff] = None
    is_ingredient_list: bool = False
    ingredient_score: int = 0
    highlight_path: Optional[str] = None
    region_paths: List[str] = field(default_factory=list)
    avg_confidence: float = 0.0
    low_confidence: List[str] = field(default_factory=list)
    ocr_error: Optional[str] = None
