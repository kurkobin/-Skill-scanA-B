"""生成两张演示用「成分表」图片（含换行、作用小节、水印，用于验证提取逻辑）。"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]


def load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def render(path: str, lines) -> None:
    img = Image.new("RGB", (800, 560), "white")
    draw = ImageDraw.Draw(img)
    title_font = load_font(28)
    body_font = load_font(20)
    small_font = load_font(14)
    y = 28
    for i, line in enumerate(lines):
        font = title_font if i == 0 else body_font
        draw.text((40, y), line, font=font, fill="black")
        y += 20 if i == 0 else 0
        y += 40 if i == 0 else 30
    draw.line([(40, 84), (760, 84)], fill="#cccccc", width=2)
    # 水印（模拟知乎署名）
    draw.text((560, 520), "知乎@Markgo", font=small_font, fill="#bbbbbb")
    img.save(path)
    print("saved", path)


A_LINES = [
    "某某面霜  净含量：50g",
    "成分：水、甘油、PEG-100 硬脂酸酯、甘油硬脂酸酯、",
    "烟酰胺、丙二醇、苯氧乙醇",
    "作用：保湿、修护",
    "使用方法：取适量涂抹于面部",
    "备案编号：粤G妆网备字2024000001",
]

B_LINES = [
    "某某面霜  净含量：50g",
    "成分：水、甘油、PEG-20 硬脂酸酯、甘油硬脂酸酯、",
    "烟酰胺、透明质酸钠、丙二醇、苯氧乙醇、凡士林",
    "作用：保湿、修护、舒缓",
    "使用方法：取适量涂抹于面部",
    "备案编号：粤G妆网备字2024000001",
]


if __name__ == "__main__":
    render(os.path.join(HERE, "demo_a.png"), A_LINES)
    render(os.path.join(HERE, "demo_b.png"), B_LINES)
