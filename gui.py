"""现代图形界面（CustomTkinter，浅色主题）。只做「成分表」对比，支持拖拽上传。"""
from __future__ import annotations

import os
import queue
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from image_diff import compare_images
from image_diff.report import render_text_summary, save_markdown

try:
    import tkinterdnd2
    _DND_AVAILABLE = True
except Exception:  # pragma: no cover - 没装拖拽库时仍可点击选择
    tkinterdnd2 = None
    _DND_AVAILABLE = False

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

BG = "#f4f6f9"
CARD = "#ffffff"
BORDER = "#e6e8ec"
TEXT = "#1f2937"
MUTED = "#6b7280"
HINT = "#9aa0a6"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
GREEN = "#16a34a"
RED = "#dc2626"
SOFT_BTN = "#eef2f7"
SOFT_BTN_HOVER = "#e2e8f0"

FONT_FAMILY = "Microsoft YaHei"
PREVIEW_H = 150
POLL_MS = 100


def _font(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def _parse_drop_paths(widget, event) -> list:
    """把拖拽事件里的文件路径解析成列表。"""
    try:
        items = widget.winfo_toplevel().tk.splitlist(event.data)
    except Exception:
        items = [getattr(event, "data", "")]
    paths = []
    for item in items:
        item = str(item).strip()
        if item.startswith("{") and item.endswith("}"):
            item = item[1:-1]
        if item:
            paths.append(item)
    return paths


if _DND_AVAILABLE:

    class _BaseApp(ctk.CTk, tkinterdnd2.TkinterDnD.DnDWrapper):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.TkdndVersion = tkinterdnd2.TkinterDnD._require(self)

else:

    class _BaseApp(ctk.CTk):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)


class ImageSlot(ctk.CTkFrame):
    """图片卡片：可拖拽图片进来，也可点击选择。"""

    def __init__(self, master, title: str, hint: str = "拖拽或点击上传图片"):
        super().__init__(
            master, fg_color=CARD, corner_radius=16,
            border_width=1, border_color=BORDER,
        )
        self.path = None
        self._img = None
        self._photo = None
        self._hint = hint

        ctk.CTkLabel(self, text=title, font=_font(14, "bold"), text_color=TEXT).pack(
            anchor="w", padx=16, pady=(14, 8)
        )
        self.canvas = tk.Canvas(
            self, bg="#f9fafb", highlightthickness=0, height=PREVIEW_H, cursor="hand2"
        )
        self.canvas.pack(fill="x", padx=16)
        self.canvas.bind("<Button-1>", lambda _e: self.choose())
        self.canvas.bind("<Configure>", lambda _e: self._redraw())

        self.name_label = ctk.CTkLabel(
            self, text="未选择图片", font=_font(11), text_color=MUTED, anchor="w"
        )
        self.name_label.pack(fill="x", padx=16, pady=(6, 14))
        self._redraw()
        self._register_dnd()

    # ---- 拖拽 ----
    def _register_dnd(self) -> None:
        if not _DND_AVAILABLE:
            return
        for widget in (self, self.canvas):
            try:
                widget.drop_target_register(tkinterdnd2.DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    def _on_drop(self, event):
        for path in _parse_drop_paths(self, event):
            if os.path.isfile(path):
                self.load(path)
                return

    # ---- 点击 ----
    def choose(self) -> None:
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")],
        )
        if path:
            self.load(path)

    def load(self, path: str) -> None:
        try:
            self._img = Image.open(path).convert("RGB")
        except Exception as exc:
            messagebox.showerror("无法打开图片", str(exc))
            return
        self.path = path
        self.name_label.configure(text=os.path.basename(path))
        self._redraw()

    # ---- 绘制 ----
    def _redraw(self) -> None:
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        self.canvas.delete("all")
        if self._img is None:
            self.canvas.create_text(
                cw // 2, ch // 2, text=self._hint, fill=HINT, font=(FONT_FAMILY, 12)
            )
            return
        img = self._img.copy()
        img.thumbnail((max(1, cw - 12), max(1, ch - 12)), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.canvas.create_image(cw // 2, ch // 2, image=self._photo)


class App(_BaseApp):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.title("成分对比 · Ingredient Diff")
        self.geometry("1080x800")
        self.minsize(960, 700)

        self._result = None
        self._comparison_path = None
        self._photo_cmp = None
        self._out_dir = os.path.join(os.getcwd(), "out")
        self._queue: "queue.Queue" = queue.Queue()

        self._build_ui()
        self.after(POLL_MS, self._poll_queue)

    # ---- UI ----
    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(22, 10))
        ctk.CTkLabel(header, text="成分对比", font=_font(24, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="拖拽或点击上传两张成分表图片，自动提取成分并找出新增内容（左 = 旧版，右 = 新版）",
            font=_font(12), text_color=MUTED,
        ).pack(anchor="w", pady=(2, 0))

        inputs = ctk.CTkFrame(self, fg_color="transparent")
        inputs.pack(fill="x", padx=24)
        inputs.columnconfigure(0, weight=1, uniform="slot")
        inputs.columnconfigure(1, weight=1, uniform="slot")
        self.slot_a = ImageSlot(inputs, "旧版成分表（左）", "拖拽或点击上传旧版图片")
        self.slot_a.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.slot_b = ImageSlot(inputs, "新版成分表（右）", "拖拽或点击上传新版图片")
        self.slot_b.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # 整窗拖拽兜底：拖到任意位置时，自动填入第一个空位
        if _DND_AVAILABLE:
            try:
                self.drop_target_register(tkinterdnd2.DND_FILES)
                self.dnd_bind("<<Drop>>", self._on_root_drop)
            except Exception:
                pass

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=12)
        self.compare_btn = ctk.CTkButton(
            actions, text="开始对比", command=self.start_compare,
            font=_font(14, "bold"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
            corner_radius=10, width=150, height=42,
        )
        self.compare_btn.pack(side="left")
        self.progress = ctk.CTkProgressBar(actions, width=170, mode="indeterminate")
        self.progress.pack(side="left", padx=14)
        self.progress.set(0)
        self.status_label = ctk.CTkLabel(actions, text="就绪", font=_font(12), text_color=MUTED)
        self.status_label.pack(side="left")

        results = ctk.CTkFrame(self, fg_color="transparent")
        results.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        results.columnconfigure(0, weight=3, uniform="res")
        results.columnconfigure(1, weight=2, uniform="res")
        results.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(results, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ctk.CTkLabel(left, text="对比图", font=_font(13, "bold"), text_color=TEXT).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        self.cmp_canvas = tk.Canvas(left, bg="#f9fafb", highlightthickness=0)
        self.cmp_canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.cmp_canvas.bind("<Configure>", lambda _e: self._redraw_comparison())

        right = ctk.CTkFrame(results, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ctk.CTkLabel(right, text="对比结果", font=_font(13, "bold"), text_color=TEXT).pack(
            anchor="w", padx=16, pady=(14, 6)
        )
        self.diff_frame = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.diff_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._show_empty_diff()

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=24, pady=(0, 16))
        self.save_btn = self._soft_button(bottom, "保存结果", self.save_result)
        self.save_btn.pack(side="left")
        self.copy_btn = self._soft_button(bottom, "复制结果", self.copy_result)
        self.copy_btn.pack(side="left", padx=10)
        self.export_btn = self._soft_button(bottom, "导出对比图", self.export_image)
        self.export_btn.pack(side="left")

    def _on_root_drop(self, event) -> None:
        for path in _parse_drop_paths(self, event):
            if not os.path.isfile(path):
                continue
            if not self.slot_a.path:
                self.slot_a.load(path)
            elif not self.slot_b.path:
                self.slot_b.load(path)
            else:
                break

    def _soft_button(self, master, text, command) -> ctk.CTkButton:
        return ctk.CTkButton(
            master, text=text, command=command, state="disabled",
            font=_font(12), fg_color=SOFT_BTN, hover_color=SOFT_BTN_HOVER,
            text_color=TEXT, corner_radius=10, width=110,
        )

    # ---- 对比 ----
    def start_compare(self) -> None:
        if not self.slot_a.path or not self.slot_b.path:
            messagebox.showwarning("提示", "请先放入两张图片（左 = 旧版，右 = 新版）")
            return
        self.compare_btn.configure(state="disabled")
        self._progress_start()
        self.status_label.configure(text="识别中…", text_color=MUTED)
        args = (self.slot_a.path, self.slot_b.path)
        threading.Thread(target=self._run_compare, args=args, daemon=True).start()

    def _run_compare(self, path_a: str, path_b: str) -> None:
        try:
            os.makedirs(self._out_dir, exist_ok=True)
            result = compare_images(path_a, path_b, mode="ingredient", output_dir=self._out_dir)
            save_markdown(result, os.path.join(self._out_dir, "report.md"))
            self._queue.put(("ok", result))
        except Exception as exc:  # noqa: BLE001
            self._queue.put(("err", exc))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "ok":
                    self._result = payload
                    self._show_result(payload)
                else:
                    self._on_error(payload)
        except queue.Empty:
            pass
        self.after(POLL_MS, self._poll_queue)

    def _progress_start(self) -> None:
        try:
            self.progress.start()
        except Exception:
            self.progress.set(0.3)

    def _progress_stop(self) -> None:
        try:
            self.progress.stop()
        except Exception:
            pass
        self.progress.set(0)

    def _on_error(self, exc: Exception) -> None:
        self._progress_stop()
        self.compare_btn.configure(state="normal")
        self.status_label.configure(text="失败", text_color=RED)
        messagebox.showerror("对比失败", str(exc))

    # ---- 结果 ----
    def _show_result(self, result) -> None:
        self._progress_stop()
        self.compare_btn.configure(state="normal")
        self._comparison_path = result.highlight_path
        self._redraw_comparison()
        self._render_diff(result)

        if result.ocr_error:
            self.status_label.configure(text="OCR 不可用，无法提取成分", text_color=RED)
        else:
            diff = result.ingredient_diff
            added = len(diff.added) if diff else 0
            removed = len(diff.removed) if diff else 0
            self.status_label.configure(
                text=f"完成 · 新增 {added} · 删除 {removed}", text_color=MUTED
            )
        for btn in (self.save_btn, self.copy_btn):
            btn.configure(state="normal")
        self.export_btn.configure(state="normal" if result.highlight_path else "disabled")

    def _clear_diff(self) -> None:
        for child in self.diff_frame.winfo_children():
            child.destroy()

    def _show_empty_diff(self) -> None:
        self._clear_diff()
        ctk.CTkLabel(
            self.diff_frame, text="对比后在此显示 新增 / 删除 的成分",
            font=_font(12), text_color=HINT,
        ).pack(pady=24)

    def _render_diff(self, result) -> None:
        self._clear_diff()
        if result.ocr_error:
            ctk.CTkLabel(
                self.diff_frame, text="OCR 不可用", font=_font(13, "bold"), text_color=RED,
            ).pack(anchor="w", padx=6, pady=(6, 4))
            ctk.CTkLabel(
                self.diff_frame, text=result.ocr_error, font=_font(11), text_color=MUTED,
                wraplength=300, justify="left",
            ).pack(anchor="w", padx=6)
            return

        diff = result.ingredient_diff
        added = diff.added if diff else []
        removed = diff.removed if diff else []

        if not added and not removed:
            ctk.CTkLabel(
                self.diff_frame, text="两张图成分完全一致", font=_font(13, "bold"), text_color=GREEN,
            ).pack(anchor="w", padx=6, pady=10)
            return

        self._diff_section("新增", added, GREEN)
        self._diff_section("删除", removed, RED)

    def _diff_section(self, title: str, items, color: str) -> None:
        ctk.CTkLabel(
            self.diff_frame, text=f"{title} · {len(items)}",
            font=_font(13, "bold"), text_color=color, anchor="w",
        ).pack(fill="x", padx=6, pady=(12, 6))
        if not items:
            ctk.CTkLabel(
                self.diff_frame, text="（无）", font=_font(12), text_color=MUTED, anchor="w",
            ).pack(fill="x", padx=20)
            return
        for item in items:
            ctk.CTkLabel(
                self.diff_frame, text="· " + item, font=_font(12), text_color=TEXT,
                anchor="w", wraplength=300, justify="left",
            ).pack(fill="x", padx=20, pady=1)

    # ---- 对比图 ----
    def _redraw_comparison(self) -> None:
        self.cmp_canvas.delete("all")
        cw = max(1, self.cmp_canvas.winfo_width())
        ch = max(1, self.cmp_canvas.winfo_height())
        if not self._comparison_path or not os.path.isfile(self._comparison_path):
            self.cmp_canvas.create_text(
                16, 16, anchor="nw", text="对比后在此显示 旧版 / 新版 对比图（红框为差异处）",
                fill=HINT, font=(FONT_FAMILY, 12),
            )
            return
        try:
            img = Image.open(self._comparison_path).convert("RGB")
        except Exception:
            return
        img = img.copy()
        img.thumbnail((max(1, cw - 12), max(1, ch - 12)), Image.LANCZOS)
        self._photo_cmp = ImageTk.PhotoImage(img)
        self.cmp_canvas.create_image(cw // 2, ch // 2, image=self._photo_cmp)

    # ---- 底部动作 ----
    def save_result(self) -> None:
        if not self._result:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("文本", "*.txt")],
        )
        if not path:
            return
        try:
            if path.lower().endswith(".txt"):
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(render_text_summary(self._result))
            else:
                save_markdown(self._result, path)
            self.status_label.configure(text=f"已保存：{os.path.basename(path)}", text_color=MUTED)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("保存失败", str(exc))

    def copy_result(self) -> None:
        if not self._result:
            return
        self.clipboard_clear()
        self.clipboard_append(render_text_summary(self._result))
        self.status_label.configure(text="结果已复制到剪贴板", text_color=MUTED)

    def export_image(self) -> None:
        if not self._result or not self._result.highlight_path:
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if not path:
            return
        try:
            shutil.copyfile(self._result.highlight_path, path)
            self.status_label.configure(text=f"已导出：{os.path.basename(path)}", text_color=MUTED)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("导出失败", str(exc))


def main() -> None:
    try:
        App().mainloop()
    except Exception as exc:  # noqa: BLE001 - 启动失败时写日志并弹窗提示
        import traceback
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
        with open(log_path, "w", encoding="utf-8") as fh:
            fh.write("GUI 启动失败：\n")
            traceback.print_exc(file=fh)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("启动失败", str(exc) + "\n\n详细信息已写入 error.log")
            root.destroy()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
