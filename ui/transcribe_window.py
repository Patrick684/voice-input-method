"""文件转写窗口模块 - 使用 CustomTkinter 实现音视频转写 GUI"""

import os
import threading
from tkinter import filedialog
from typing import Optional

import customtkinter as ctk

from engine.transcriber import FileTranscriber, TranscriptionSegment


class TranscribeWindow(ctk.CTkToplevel):
    """文件转写窗口"""

    def __init__(
        self,
        model_size: str = "small",
        cache_dir: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
        master=None,
    ):
        super().__init__(master)
        self._model_size = model_size
        self._cache_dir = cache_dir
        self._device = device
        self._compute_type = compute_type

        # 转写状态
        self._transcriber: Optional[FileTranscriber] = None
        self._segments: list[TranscriptionSegment] = []
        self._is_running = False
        self._progress_text = ""
        self._progress_value = 0.0

        self.title("语音输入法 - 文件转写")
        self.geometry("520x560")
        self.resizable(False, False)

        # 确保窗口在前台
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))

        self._setup_ui()

    def _setup_ui(self):
        """构建 UI"""
        pad_x = 15

        # ---- 文件选择区 ----
        file_frame = ctk.CTkFrame(self, fg_color="transparent")
        file_frame.pack(fill="x", padx=pad_x, pady=(15, 5))

        ctk.CTkLabel(file_frame, text="输入文件:", anchor="w").pack(anchor="w")

        path_row = ctk.CTkFrame(file_frame, fg_color="transparent")
        path_row.pack(fill="x", pady=(2, 0))

        self._file_var = ctk.StringVar(value="")
        self._file_entry = ctk.CTkEntry(
            path_row,
            textvariable=self._file_var,
            placeholder_text="选择音频或视频文件...",
        )
        self._file_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            path_row,
            text="浏览...",
            width=70,
            command=self._browse_file,
        ).pack(side="right")

        # ---- 设置区 ----
        settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        settings_frame.pack(fill="x", padx=pad_x, pady=(10, 5))

        # 输出格式
        ctk.CTkLabel(settings_frame, text="输出格式:", anchor="w").pack(anchor="w")
        format_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        format_row.pack(fill="x", pady=(2, 8))
        self._format_var = ctk.StringVar(value="srt")
        ctk.CTkRadioButton(
            format_row, text="SRT 字幕", variable=self._format_var, value="srt"
        ).pack(side="left", padx=(0, 15))
        ctk.CTkRadioButton(
            format_row, text="TXT 纯文本", variable=self._format_var, value="txt"
        ).pack(side="left")

        # 模型和语言
        opts_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        opts_row.pack(fill="x")

        ctk.CTkLabel(opts_row, text="模型:").pack(side="left")
        self._model_var = ctk.StringVar(value=self._model_display(self._model_size))
        ctk.CTkOptionMenu(
            opts_row,
            variable=self._model_var,
            values=[
                "Tiny (75MB, 最快)",
                "Base (150MB, 推荐)",
                "Small (500MB, 高精度)",
                "Medium (1.5GB, 专业)",
            ],
            width=180,
        ).pack(side="left", padx=(5, 15))

        ctk.CTkLabel(opts_row, text="语言:").pack(side="left")
        self._lang_var = ctk.StringVar(value="中文")
        ctk.CTkOptionMenu(
            opts_row,
            variable=self._lang_var,
            values=["中文", "English", "日本語", "自动检测"],
            width=100,
        ).pack(side="left", padx=(5, 0))

        # ---- 操作区 ----
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=pad_x, pady=(10, 5))

        self._start_btn = ctk.CTkButton(
            action_frame,
            text="开始转写",
            command=self._start_transcribe,
            width=100,
        )
        self._start_btn.pack(side="left")

        self._status_label = ctk.CTkLabel(
            action_frame,
            text="就绪",
            text_color="gray",
        )
        self._status_label.pack(side="right")

        # 进度条
        self._progress_bar = ctk.CTkProgressBar(self)
        self._progress_bar.pack(fill="x", padx=pad_x, pady=(0, 5))
        self._progress_bar.set(0)

        # ---- 预览区 ----
        preview_label = ctk.CTkLabel(self, text="预览:", anchor="w")
        preview_label.pack(anchor="w", padx=pad_x, pady=(5, 2))

        self._preview_text = ctk.CTkTextbox(self, height=200)
        self._preview_text.pack(fill="both", expand=True, padx=pad_x, pady=(0, 5))

        # ---- 保存按钮 ----
        self._save_btn = ctk.CTkButton(
            self,
            text="保存字幕文件",
            command=self._save_file,
            state="disabled",
            width=120,
        )
        self._save_btn.pack(pady=(0, 15))

    # ---- 事件处理 ----

    def _browse_file(self):
        """浏览选择文件"""
        filetypes = [
            (
                "所有支持格式",
                " ".join(f"*{e}" for e in sorted(FileTranscriber.SUPPORTED_FORMATS)),
            ),
            (
                "音频文件",
                " ".join(f"*{e}" for e in sorted(FileTranscriber.SUPPORTED_AUDIO)),
            ),
            (
                "视频文件",
                " ".join(f"*{e}" for e in sorted(FileTranscriber.SUPPORTED_VIDEO)),
            ),
        ]
        path = filedialog.askopenfilename(
            title="选择音频或视频文件",
            filetypes=filetypes,
        )
        if path:
            self._file_var.set(path)

    def _start_transcribe(self):
        """开始转写"""
        file_path = self._file_var.get().strip()
        if not file_path or not os.path.exists(file_path):
            self._status_label.configure(text="请选择有效文件", text_color="red")
            return

        if self._is_running:
            return

        # 重置状态
        self._is_running = True
        self._segments = []
        self._progress_bar.set(0)
        self._status_label.configure(text="准备中...", text_color="gray")
        self._start_btn.configure(state="disabled", text="转写中...")
        self._save_btn.configure(state="disabled")
        self._preview_text.delete("1.0", "end")

        # 解析模型和语言
        model_reverse = {
            "Tiny (75MB, 最快)": "tiny",
            "Base (150MB, 推荐)": "base",
            "Small (500MB, 高精度)": "small",
            "Medium (1.5GB, 专业)": "medium",
        }
        model_size = model_reverse.get(self._model_var.get(), "small")

        lang_reverse = {"中文": "zh", "English": "en", "日本語": "ja", "自动检测": None}
        language = lang_reverse.get(self._lang_var.get())

        # 创建转写器
        self._transcriber = FileTranscriber(
            model_size=model_size,
            cache_dir=self._cache_dir,
            device=self._device,
            compute_type=self._compute_type,
        )

        # 后台线程执行转写
        thread = threading.Thread(
            target=self._transcribe_worker,
            args=(file_path, language),
            daemon=True,
        )
        thread.start()

        # 开始轮询进度
        self._poll_progress()

    def _transcribe_worker(self, file_path: str, language: Optional[str]):
        """后台转写线程"""
        try:
            self._segments = self._transcriber.transcribe(
                file_path,
                language=language,
                on_progress=self._on_progress_callback,
            )
        except Exception as e:
            self._progress_text = f"转写失败: {e}"
            self._progress_value = -1  # 错误标记

    def _on_progress_callback(self, text: str, progress: float):
        """进度回调（在工作线程中调用）"""
        self._progress_text = text
        self._progress_value = progress

    def _poll_progress(self):
        """轮询更新进度（主线程）"""
        if not self._is_running:
            return

        # 更新进度条
        if self._progress_value >= 0:
            self._progress_bar.set(self._progress_value)

        # 更新状态文字
        self._status_label.configure(text=self._progress_text, text_color="gray")

        # 检查是否完成
        if self._progress_value >= 1.0:
            self._on_transcribe_done()
            return

        if self._progress_value < 0:
            # 错误
            self._status_label.configure(text=self._progress_text, text_color="red")
            self._start_btn.configure(state="normal", text="开始转写")
            self._is_running = False
            return

        # 继续轮询
        self.after(200, self._poll_progress)

    def _on_transcribe_done(self):
        """转写完成"""
        self._is_running = False
        self._progress_bar.set(1.0)
        self._start_btn.configure(state="normal", text="开始转写")
        self._save_btn.configure(state="normal")

        count = len(self._segments)
        self._status_label.configure(
            text=f"转写完成，共 {count} 个片段", text_color="green"
        )

        # 预览
        fmt = self._format_var.get()
        if fmt == "srt":
            preview = FileTranscriber.segments_to_srt(self._segments)
        else:
            preview = FileTranscriber.segments_to_txt(self._segments)

        self._preview_text.delete("1.0", "end")
        self._preview_text.insert("1.0", preview)

    def _save_file(self):
        """保存字幕文件"""
        if not self._segments:
            return

        fmt = self._format_var.get()
        ext = ".srt" if fmt == "srt" else ".txt"

        # 默认文件名（基于输入文件）
        input_path = self._file_var.get().strip()
        default_name = ""
        if input_path:
            base = os.path.splitext(os.path.basename(input_path))[0]
            default_name = base + ext

        filetypes = [
            ("SRT 字幕", "*.srt") if fmt == "srt" else ("文本文件", "*.txt"),
            ("所有文件", "*.*"),
        ]

        save_path = filedialog.asksaveasfilename(
            title="保存字幕文件",
            initialfile=default_name,
            filetypes=filetypes,
            defaultextension=ext,
        )

        if not save_path:
            return

        # 生成内容
        if fmt == "srt":
            content = FileTranscriber.segments_to_srt(self._segments)
        else:
            content = FileTranscriber.segments_to_txt(self._segments)

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            self._status_label.configure(
                text=f"已保存: {os.path.basename(save_path)}",
                text_color="green",
            )
        except IOError as e:
            self._status_label.configure(text=f"保存失败: {e}", text_color="red")

    # ---- 辅助方法 ----

    @staticmethod
    def _model_display(model_size: str) -> str:
        """模型大小 -> 显示文本"""
        mapping = {
            "tiny": "Tiny (75MB, 最快)",
            "base": "Base (150MB, 推荐)",
            "small": "Small (500MB, 高精度)",
            "medium": "Medium (1.5GB, 专业)",
        }
        return mapping.get(model_size, "Small (500MB, 高精度)")
