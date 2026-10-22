"""把对比结果渲染成简洁的 Markdown 报告 / 纯文本摘要。"""
from __future__ import annotations

from typing import List

from .models import CompareResult


def _list_lines(items: List[str]) -> List[str]:
    return [f"- {item}" for item in items] if items else ["- （无）"]


def render_markdown(result: CompareResult, title: str = "成分对比结果") -> str:
    lines: List[str] = [f"# {title}", ""]

    if result.ocr_error:
        lines.append("> ⚠ OCR 不可用，暂无法提取成分。")
        lines.append(">")
        lines.append("> " + result.ocr_error.replace("\n", "\n> "))
        return "\n".join(lines) + "\n"

    diff = result.ingredient_diff
    added = diff.added if diff else []
    removed = diff.removed if diff else []

    lines.append(f"- 新增：**{len(added)}** 项")
    lines.append(f"- 删除：**{len(removed)}** 项")
    lines.append(f"- 旧版成分数：**{len(result.ingredients_a)}**")
    lines.append(f"- 新版成分数：**{len(result.ingredients_b)}**")
    lines.append("")

    lines.append(f"## 新增（{len(added)}）")
    lines.extend(_list_lines(added))
    lines.append("")

    lines.append(f"## 删除（{len(removed)}）")
    lines.extend(_list_lines(removed))
    lines.append("")

    return "\n".join(lines) + "\n"


def render_text_summary(result: CompareResult) -> str:
    """给剪贴板/控制台用的纯文本摘要。"""
    if result.ocr_error:
        return "OCR 不可用：" + result.ocr_error
    diff = result.ingredient_diff
    added = diff.added if diff else []
    removed = diff.removed if diff else []
    return (
        f"新增（{len(added)}）\n"
        "  " + ("、".join(added) if added else "（无）")
        + "\n\n"
        + f"删除（{len(removed)}）\n"
        "  " + ("、".join(removed) if removed else "（无）")
    )


def save_markdown(result: CompareResult, path: str, title: str = "成分对比结果") -> str:
    text = render_markdown(result, title=title)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path
