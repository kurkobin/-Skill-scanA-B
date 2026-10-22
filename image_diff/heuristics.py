"""成分表识别：普通「成分」小节 与 表格「原料」列 两种提取方式。"""
from __future__ import annotations

import re
from typing import List, Tuple

from .models import OCRLine
from .text_diff import split_ingredients

KEYWORDS = (
    "成分", "成份", "ingredients", "配料", "配方",
    "备案", "净含量", "生产日期", "保质期", "使用方法", "生产企业",
)

# 普通成分表的标题
INGREDIENT_HEADER_RE = re.compile(r"(全成分|成分表|成分|配料表|配料|ingredients)", re.I)
# 出现在成分之后、需要截断的其它小节
STOP_PREFIX_RE = re.compile(
    r"^(作用|功效|功效成分|使用方法|用法|注意事项|储存|贮存|适用|备案|生产|保质期|"
    r"净含量|执行标准|委托|制造|地址|产地|规格|容量|批准文号|产品名称|警告|温馨提示|备注|"
    r"保质|限用|批号|卫生许可|生产企业)"
)
# 成分内部的小标题（保留内容，仅去掉标题词）
SUB_HEADER_RE = re.compile(r"(其他微量成分|微量成分|主要成分|核心成分|有效成分)\s*[:：]?\s*")


def looks_like_ingredient_list(text: str) -> Tuple[bool, int]:
    if not text or not text.strip():
        return False, 0
    score = 0
    low = text.lower()
    if any(keyword in low for keyword in KEYWORDS):
        score += 1
    tokens = split_ingredients(text)
    if len(tokens) >= 6:
        score += 1
    if len(tokens) >= 12:
        score += 1
    comma_count = text.count("、") + text.count(",") + text.count("，")
    if comma_count >= 5:
        score += 1
    return score >= 2, score


def extract_ingredient_section(text: str) -> str:
    """从整页文本里截取「成分 / 配料 / 成分表」这一节（普通成分表用）。"""
    if not text or not text.strip():
        return ""
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln]

    start = None
    for i, line in enumerate(lines):
        if INGREDIENT_HEADER_RE.search(line):
            start = i
            break
    if start is None:
        return text.strip()

    collected = []
    for i in range(start, len(lines)):
        line = lines[i]
        if i > start and STOP_PREFIX_RE.match(line):
            break
        collected.append(line)

    section = " ".join(collected)
    section = INGREDIENT_HEADER_RE.sub("", section, count=1)
    section = SUB_HEADER_RE.sub("", section)
    section = re.sub(r"^[\s:：]+", "", section)
    return section.strip()


# ---------------- 表格感知 ----------------

def _x0(line: OCRLine) -> float:
    return min(p[0] for p in line.box) if line.box else 0.0


def _yc(line: OCRLine) -> float:
    if not line.box:
        return 0.0
    return sum(p[1] for p in line.box) / len(line.box)


def _clusters(lines: List[OCRLine], width: int) -> List[List[OCRLine]]:
    """按 x0 把文字行聚成列。"""
    gap = max(60.0, width * 0.08)
    ordered = sorted(lines, key=_x0)
    groups: List[List[OCRLine]] = []
    for line in ordered:
        if groups and _x0(line) - _x0(groups[-1][-1]) <= gap:
            groups[-1].append(line)
        else:
            groups.append([line])
    return groups


def _looks_like_table(lines: List[OCRLine], width: int) -> bool:
    if len(lines) < 6:
        return False
    return len(_clusters(lines, width)) >= 3


def _extract_table_tokens(lines: List[OCRLine], width: int) -> List[str]:
    """表格：左列是行标签，最右侧的密集列是成分/原料列。"""
    groups = _clusters(lines, width)
    if len(groups) < 3:
        return []

    labels = sorted(groups[0], key=_yc)  # 最左列 = 行标签
    candidates = [g for g in groups[1:] if len(g) >= 3]
    if not candidates:
        return []
    content = sorted(max(candidates, key=len), key=_yc)  # 行数最多的列 = 内容列

    # 用行标签的 y 中点切分每行的内容
    edges = []
    for i in range(len(labels) - 1):
        edges.append((_yc(labels[i]) + _yc(labels[i + 1])) / 2.0)

    buckets: dict = {}
    for line in content:
        y = _yc(line)
        idx = 0
        while idx < len(edges) and y > edges[idx]:
            idx += 1
        buckets.setdefault(idx, []).append(line)

    tokens: List[str] = []
    for idx in sorted(buckets):
        text = "".join(line.text for line in buckets[idx])  # 行内拼接，不插空格
        tokens.extend(split_ingredients(text))
    return tokens


def extract_ingredients_from_lines(lines: List[OCRLine], width: int = 1280) -> Tuple[str, List[str]]:
    """自动判断是表格还是普通成分表，返回 (成分文本, 成分列表)。"""
    if _looks_like_table(lines, width):
        tokens = _extract_table_tokens(lines, width)
        if tokens:
            return " ".join(tokens), tokens

    text = "\n".join(line.text for line in lines)
    section = extract_ingredient_section(text)
    return section, split_ingredients(section)
