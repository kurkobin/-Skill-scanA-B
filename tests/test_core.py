"""核心逻辑自测（无需 pytest）：python tests/test_core.py"""
from __future__ import annotations

import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from PIL import Image, ImageDraw

from image_diff import compare_images
from image_diff.heuristics import extract_ingredient_section, looks_like_ingredient_list
from image_diff.models import OCRLine
from image_diff.text_diff import diff_ingredients, split_ingredients


def test_split_ingredients():
    text = "水、甘油、烟酰胺、透明质酸钠"
    assert split_ingredients(text) == ["水", "甘油", "烟酰胺", "透明质酸钠"]


def test_split_keeps_wrapped_name():
    """换行不应把 PEG-100 硬脂酸酯 拆成两段。"""
    tokens = split_ingredients("水、甘油、PEG-100\n硬脂酸酯、烟酰胺")
    assert "PEG-100 硬脂酸酯" in tokens
    assert "PEG-100" not in tokens
    assert "硬脂酸酯" not in tokens


def test_table_extraction():
    """表格：只取最右侧原料列，行标签/水印不要。"""
    from image_diff.heuristics import extract_ingredients_from_lines
    from image_diff.models import OCRLine

    def line(text, x, y):
        return OCRLine(text=text, box=[(x, y), (x + 100, y), (x + 100, y + 20), (x, y + 20)], confidence=0.9)

    lines = [
        line("油脂", 50, 200),
        line("表面活性剂", 50, 400),
        line("●", 400, 200),
        line("●", 400, 400),
        line("凡士林、蜂蜡、角鲨烷、", 800, 150),
        line("聚异丁烯、植物油脂等", 800, 180),
        line("椰油酰胺丙基甜菜碱、甘油硬脂酸酯", 800, 380),
        line("香精、色素、热乎@Markgo", 800, 600),
    ]
    _, tokens = extract_ingredients_from_lines(lines, width=1280)
    assert "凡士林" in tokens
    assert "蜂蜡" in tokens
    assert "聚异丁烯" in tokens
    assert "植物油脂" in tokens
    assert "油脂" not in tokens
    assert not any("Markgo" in t for t in tokens)


def test_watermark_removed():
    """知乎@Markgo 之类的署名不能混进成分。"""
    tokens = split_ingredients("水、甘油、凡士林、知乎@Markgo、苯氧乙醇")
    assert "凡士林" in tokens
    assert "苯氧乙醇" in tokens
    assert not any("Markgo" in t for t in tokens)
    assert not any("知乎" in t for t in tokens)


def test_extract_ignores_other_sections():
    text = (
        "产品名称：某某面霜\n"
        "成分：水、甘油、PEG-100 硬脂酸酯、烟酰胺\n"
        "作用：保湿、修护\n"
        "使用方法：取适量涂抹\n"
        "备案编号：粤G妆网备字2024000001"
    )
    section = extract_ingredient_section(text)
    assert "水" in section
    assert "PEG-100 硬脂酸酯" in section
    assert "作用" not in section
    assert "保湿" not in section
    assert "使用方法" not in section
    assert "备案编号" not in section


def test_diff_ingredients():
    added, removed, _ = diff_ingredients("水、甘油、烟酰胺", "水、甘油、透明质酸钠、烟酰胺")
    assert "透明质酸钠" in added
    assert removed == []
    added2, removed2, _ = diff_ingredients("水、甘油、香精", "水、甘油")
    assert removed2 == ["香精"]


def test_heuristics():
    assert looks_like_ingredient_list("成分：水、甘油、烟酰胺、透明质酸钠、丙二醇、苯氧乙醇")[0]
    assert not looks_like_ingredient_list("今天天气不错")[0]


def _make_image(path: str, variant: bool) -> None:
    img = Image.new("RGB", (600, 400), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 550, 80], fill="black")
    if variant:
        draw.rectangle([50, 200, 400, 240], fill="black")
    else:
        draw.rectangle([50, 200, 250, 240], fill="black")
    img.save(path)


def test_pixel_pipeline(work: str):
    a = os.path.join(work, "a.png")
    b = os.path.join(work, "b.png")
    out = os.path.join(work, "out_pixel")
    _make_image(a, False)
    _make_image(b, True)
    result = compare_images(a, b, mode="pixel", output_dir=out)
    assert len(result.regions) >= 1, "应至少检测到一个差异区域"
    assert result.highlight_path and os.path.isfile(result.highlight_path)


def test_ingredient_pipeline_with_fake_ocr(work: str):
    a = os.path.join(work, "a2.png")
    b = os.path.join(work, "b2.png")
    _make_image(a, False)
    _make_image(b, True)

    class SequenceFake:
        def __init__(self):
            self.calls = 0

        def recognize(self, image):
            self.calls += 1
            if self.calls == 1:
                text = "成分：水、甘油、烟酰胺"
            else:
                text = "成分：水、甘油、透明质酸钠、烟酰胺"
            return [OCRLine(text=text, confidence=0.95)]

    result = compare_images(a, b, mode="ingredient", ocr_backend=SequenceFake())
    assert result.ocr_error is None
    assert result.ingredient_diff is not None
    assert "透明质酸钠" in result.ingredient_diff.added
    assert result.ingredients_a == ["水", "甘油", "烟酰胺"]


def main() -> int:
    work = os.path.join(_HERE, "_tmp")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    passed = 0
    try:
        for test in tests:
            if "work" in test.__code__.co_varnames:
                test(work)
            else:
                test()
            passed += 1
            print(f"PASS  {test.__name__}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"\n全部 {passed} 项测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
