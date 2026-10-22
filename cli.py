"""命令行入口：image-diff A B [-o out] [--no-ocr] [--json] [--debug]"""
from __future__ import annotations

import argparse
import json
import os
import sys

from image_diff import compare_images
from image_diff.report import render_text_summary, save_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image-diff",
        description="成分表对比：提取两张图片的成分，找出对比旧版所新增的内容。离线、免费。",
    )
    parser.add_argument("image_a", help="旧版图片路径（左）")
    parser.add_argument("image_b", help="新版图片路径（右）")
    parser.add_argument("-o", "--output", default="out", help="输出目录（默认 out）")
    parser.add_argument("--max-width", type=int, default=1280, help="对齐后的最大宽度")
    parser.add_argument("--threshold", type=int, default=30, help="像素差异阈值 0-255")
    parser.add_argument("--min-area", type=int, default=120, help="差异区域最小面积")
    parser.add_argument("--no-ocr", action="store_true", help="跳过 OCR，仅做像素差异")
    parser.add_argument("--json", action="store_true", help="以 JSON 打印结果摘要")
    parser.add_argument("--debug", action="store_true", help="输出 OCR 原文与提取明细到 debug_ocr.txt")
    return parser


def _write_debug(result, output_dir: str) -> str:
    path = os.path.join(output_dir, "debug_ocr.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("=== 旧版 OCR 原文 ===\n")
        fh.write(result.text_a + "\n\n")
        fh.write("=== 新版 OCR 原文 ===\n")
        fh.write(result.text_b + "\n\n")
        fh.write("=== 旧版 成分小节 ===\n")
        fh.write(result.ingredient_text_a + "\n\n")
        fh.write("=== 新版 成分小节 ===\n")
        fh.write(result.ingredient_text_b + "\n\n")
        fh.write(f"=== 旧版 成分列表（{len(result.ingredients_a)}） ===\n")
        fh.write("\n".join(result.ingredients_a) + "\n\n")
        fh.write(f"=== 新版 成分列表（{len(result.ingredients_b)}） ===\n")
        fh.write("\n".join(result.ingredients_b) + "\n")
    return path


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    for path in (args.image_a, args.image_b):
        if not os.path.isfile(path):
            print(f"找不到图片: {path}", file=sys.stderr)
            return 2

    mode = "pixel" if args.no_ocr else "ingredient"
    result = compare_images(
        args.image_a,
        args.image_b,
        mode=mode,
        output_dir=args.output,
        max_width=args.max_width,
        threshold=args.threshold,
        min_area=args.min_area,
    )

    report_path = os.path.join(args.output, "report.md")
    save_markdown(result, report_path)

    if args.json:
        payload = {
            "ocr_error": result.ocr_error,
            "added": result.ingredient_diff.added if result.ingredient_diff else [],
            "removed": result.ingredient_diff.removed if result.ingredient_diff else [],
            "ingredients_a": result.ingredients_a,
            "ingredients_b": result.ingredients_b,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text_summary(result))

    print(f"[已保存] 报告: {report_path}")
    if result.highlight_path:
        print(f"[已保存] 对比图: {result.highlight_path}")
    if args.debug:
        debug_path = _write_debug(result, args.output)
        print(f"[已保存] 调试信息: {debug_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
