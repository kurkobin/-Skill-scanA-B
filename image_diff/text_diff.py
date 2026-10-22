"""文本归一化与成分对比。"""
from __future__ import annotations

import re
from typing import List, Tuple

_FULLWIDTH_OFFSET = 0xFEE0
# 成分之间真正的分隔符：顿号、中英文逗号、分号
_SEP_RE = re.compile(r"[、,;]+")
# 换行只是排版，不能当作成分分隔
_LINE_JOIN_RE = re.compile(r"[ \t]*[\r\n]+[ \t]*")
_SPACE_RE = re.compile(r"[ \t\u3000]+")
_TRAILING_ETC = re.compile(r"等$")
_URL_RE = re.compile(r"(https?://|www\.)", re.I)
# 只有平台名的水印（无 @ 时也要去掉）
_PLATFORM_WORDS = {
    "知乎", "小红书", "抖音", "微博", "微信", "快手",
    "淘宝", "京东", "拼多多", "公众号", "b站", "bilibili", "热乎",
}
# 表格结构词（列标题 / 行标签），不是成分
_STRUCTURAL_WORDS = {
    "产品类型", "清洁产品", "膏霜乳液", "水剂/精华", "原料举例", "洗发水/洗面奶",
    "原料", "举例", "成分", "配料", "全成分", "成分表", "配料表", "配方",
}


def to_halfwidth(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - _FULLWIDTH_OFFSET))
        else:
            out.append(ch)
    return "".join(out)


def normalize(text: str) -> str:
    """归一化：全角转半角、统一标点、把换行拼接成空格。"""
    if not text:
        return ""
    text = to_halfwidth(text)
    text = text.replace("；", ";").replace("：", ":").replace("，", ",")
    text = _LINE_JOIN_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text)
    return text.strip()


def _is_noise_token(token: str) -> bool:
    """水印 / 平台署名 / 网址 / 表格结构词。"""
    if token in _STRUCTURAL_WORDS:
        return True
    if "@" in token or _URL_RE.search(token):
        return True
    if token.lower() in _PLATFORM_WORDS:
        return True
    return False


def split_ingredients(text: str) -> List[str]:
    """把成分表切成成分列表。

    只在 ``、 , ;`` 处拆分，绝不在换行/空格处拆分，
    这样像 ``PEG-100 硬脂酸酯`` 这种带空格、可能跨行的名称能保持完整。
    同时过滤掉「知乎@xxx」之类的署名噪声。
    """
    parts = _SEP_RE.split(normalize(text))
    result: List[str] = []
    seen = set()
    for part in parts:
        part = part.strip(" .。-·•*")
        if not part:
            continue
        if _is_noise_token(part):
            continue
        part = _TRAILING_ETC.sub("", part).strip()
        if not part or part in seen:
            continue
        seen.add(part)
        result.append(part)
    return result


def diff_lists(a: List[str], b: List[str]) -> Tuple[List[str], List[str], List[Tuple[str, str]]]:
    set_a = set(a)
    set_b = set(b)
    added = [x for x in b if x not in set_a]
    removed = [x for x in a if x not in set_b]
    return added, removed, []


def diff_ingredients(text_a: str, text_b: str) -> Tuple[List[str], List[str], List[Tuple[str, str]]]:
    """返回 (新增, 删除, 变化)。新增 = B 有、A 无。"""
    return diff_lists(split_ingredients(text_a), split_ingredients(text_b))
