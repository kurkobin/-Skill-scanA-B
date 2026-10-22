"""OCR 后端抽象。

支持两种免费、离线的 OCR 后端：
- PaddleOCR（较重）
- RapidOCR（基于 onnxruntime，轻量）

通过 ``IMAGE_DIFF_OCR_BACKEND`` 环境变量选择：``paddleocr`` / ``rapidocr`` / ``auto``（默认）。
``auto`` 会优先使用已安装的 PaddleOCR，其次 RapidOCR。
"""
from __future__ import annotations

import os
from typing import List, Optional

from PIL import Image

from .models import OCRLine


class OCRUnavailableError(RuntimeError):
    """OCR 引擎不可用（未安装或初始化失败）。"""


class BaseOCRBackend:
    name = "base"

    def is_available(self) -> bool:
        return True

    def recognize(self, image: Image.Image) -> List[OCRLine]:
        raise NotImplementedError


class PaddleOCRBackend(BaseOCRBackend):
    """PaddleOCR 后端，兼容 2.x 的 ``ocr.ocr`` 与 3.x 的 ``ocr.predict``。"""

    name = "paddleocr"

    def __init__(self, lang: str = "ch"):
        self.lang = lang
        self._engine = None

    def is_available(self) -> bool:
        try:
            import paddleocr  # noqa: F401
            return True
        except Exception:
            return False

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return
        try:
            import paddleocr
        except Exception as exc:  # pragma: no cover
            raise OCRUnavailableError(
                "未找到 PaddleOCR。请先安装：\n"
                "  pip install paddlepaddle paddleocr\n"
                "原始错误：" + str(exc)
            ) from exc
        attempts = (
            {"use_angle_cls": True, "lang": self.lang, "show_log": False},
            {"use_angle_cls": True, "lang": self.lang},
            {"lang": self.lang},
            {},
        )
        last_err: Optional[Exception] = None
        for kwargs in attempts:
            try:
                self._engine = paddleocr.PaddleOCR(**kwargs)
                return
            except TypeError as exc:
                last_err = exc
                continue
            except Exception as exc:  # pragma: no cover
                raise OCRUnavailableError("PaddleOCR 初始化失败：" + str(exc)) from exc
        raise OCRUnavailableError(
            "PaddleOCR 初始化失败（版本 API 不兼容）：" + (str(last_err) if last_err else "")
        )

    def recognize(self, image: Image.Image) -> List[OCRLine]:
        self._ensure_engine()
        import numpy as np

        arr = np.asarray(image.convert("RGB"))
        engine = self._engine
        raw = None
        last_err: Optional[Exception] = None

        if hasattr(engine, "ocr") and callable(getattr(engine, "ocr")):
            for call in (lambda: engine.ocr(arr, cls=True), lambda: engine.ocr(arr)):
                try:
                    raw = call()
                    if raw is not None:
                        break
                except Exception as exc:
                    last_err = exc

        if raw is None and hasattr(engine, "predict"):
            try:
                raw = engine.predict(input=arr)
            except TypeError:
                try:
                    raw = engine.predict(arr)
                except Exception as exc:
                    last_err = exc

        if raw is None:
            raise OCRUnavailableError(
                "无法调用 PaddleOCR 识别接口：" + (str(last_err) if last_err else "")
            )
        return self._normalize(raw)

    @staticmethod
    def _normalize(raw) -> List[OCRLine]:
        lines: List[OCRLine] = []
        if isinstance(raw, (list, tuple)):
            for item in raw:
                data = _as_dict(item)
                if data and "rec_texts" in data:
                    texts = data.get("rec_texts") or []
                    scores = data.get("rec_scores") or []
                    polys = data.get("rec_polys") or data.get("dt_polys") or []
                    for i, text in enumerate(texts):
                        conf = float(scores[i]) if i < len(scores) else 0.0
                        box = polys[i] if i < len(polys) else []
                        lines.append(OCRLine(text=str(text), box=_to_box(box), confidence=conf))
                    continue
                _walk_v2(item, lines)
        else:
            _walk_v2(raw, lines)
        return lines


class RapidOCRBackend(BaseOCRBackend):
    """RapidOCR 后端（onnxruntime，轻量、完全离线）。"""

    name = "rapidocr"

    def __init__(self):
        self._engine = None

    def is_available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401
            return True
        except Exception:
            return False

    def _ensure_engine(self) -> None:
        if self._engine is not None:
            return
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception as exc:  # pragma: no cover
            raise OCRUnavailableError(
                "未找到 RapidOCR。请先安装：\n"
                "  pip install rapidocr_onnxruntime\n"
                "原始错误：" + str(exc)
            ) from exc
        self._engine = RapidOCR()

    def recognize(self, image: Image.Image) -> List[OCRLine]:
        self._ensure_engine()
        import numpy as np

        arr = np.asarray(image.convert("RGB"))
        output = self._engine(arr)
        data = output[0] if isinstance(output, tuple) else output
        lines: List[OCRLine] = []
        for item in (data or []):
            try:
                box, text, score = item[0], item[1], item[2]
            except Exception:
                continue
            lines.append(OCRLine(text=str(text), box=_to_box(box), confidence=float(score)))
        return lines


def _as_dict(item):
    if isinstance(item, dict):
        return item
    for attr in ("json", "to_dict"):
        if hasattr(item, attr):
            try:
                val = getattr(item, attr)
                val = val() if callable(val) else val
                if isinstance(val, dict):
                    if isinstance(val.get("res"), dict):
                        return val["res"]
                    return val
            except Exception:
                continue
    return None


def _is_box(x) -> bool:
    if not isinstance(x, (list, tuple)) or len(x) != 4:
        return False
    for point in x:
        if not (isinstance(point, (list, tuple)) and len(point) == 2):
            return False
    return True


def _is_text_conf(x) -> bool:
    if not isinstance(x, (list, tuple)) or len(x) != 2:
        return False
    return isinstance(x[0], str) and isinstance(x[1], (int, float))


def _to_box(box):
    try:
        return [(float(p[0]), float(p[1])) for p in box]
    except Exception:
        return []


def _walk_v2(node, lines: List[OCRLine]) -> None:
    if isinstance(node, (list, tuple)):
        if len(node) == 2 and _is_box(node[0]) and _is_text_conf(node[1]):
            box, text_conf = node
            text, conf = text_conf
            lines.append(OCRLine(text=text, box=_to_box(box), confidence=float(conf)))
            return
        for child in node:
            _walk_v2(child, lines)


def _available_backends() -> List[str]:
    names = []
    if PaddleOCRBackend().is_available():
        names.append("paddleocr")
    if RapidOCRBackend().is_available():
        names.append("rapidocr")
    return names


def get_default_backend(lang: str = "ch") -> BaseOCRBackend:
    name = os.environ.get("IMAGE_DIFF_OCR_BACKEND", "auto").strip().lower()
    if name == "paddleocr":
        return PaddleOCRBackend(lang=lang)
    if name == "rapidocr":
        return RapidOCRBackend()
    if name in ("", "auto"):
        paddle = PaddleOCRBackend(lang=lang)
        if paddle.is_available():
            return paddle
        rapid = RapidOCRBackend()
        if rapid.is_available():
            return rapid
        return PaddleOCRBackend(lang=lang)  # 两者都没有时，由它抛出带安装提示的错误
    raise OCRUnavailableError(f"未知的 OCR 后端: {name}（支持 paddleocr / rapidocr / auto）")


def ocr_status() -> str:
    names = _available_backends()
    if names:
        return "可用 OCR 后端: " + ", ".join(names)
    return (
        "未安装 OCR 后端。任选其一安装：\n"
        "  pip install rapidocr_onnxruntime          # 轻量，推荐\n"
        "  pip install paddlepaddle paddleocr        # 较重"
    )
