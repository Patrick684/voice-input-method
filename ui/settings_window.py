"""设置窗口模块 - 使用 CustomTkinter 实现"""

from typing import Callable, Optional

import customtkinter as ctk

from config import Config
from audio.recorder import AudioRecorder

# 设置外观主题
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class SettingsWindow(ctk.CTkToplevel):
    """应用设置窗口"""

    def __init__(
        self,
        config: Config,
        on_settings_changed: Optional[Callable[[dict], None]] = None,
        master=None,
    ):
        super().__init__(master)
        self.config = config
        self._on_settings_changed = on_settings_changed

        self.title("语音输入法 - 设置")
        self.geometry("500x520")
        self.resizable(False, False)

        # 确保窗口在前台
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """构建 UI"""
        # 选项卡
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(15, 5))

        self._create_general_tab()
        self._create_engine_tab()
        self._create_advanced_tab()

        # 底部按钮栏
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(5, 15))

        ctk.CTkButton(
            btn_frame,
            text="恢复默认",
            width=80,
            fg_color="gray",
            command=self._reset_settings,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text="取消",
            width=80,
            fg_color="gray",
            command=self.destroy,
        ).pack(side="right")

        ctk.CTkButton(
            btn_frame,
            text="保存",
            width=80,
            command=self._save_settings,
        ).pack(side="right", padx=(0, 10))

    def _create_general_tab(self):
        """基本设置选项卡"""
        tab = self.tabview.add("基本设置")

        # 快捷键
        ctk.CTkLabel(tab, text="录音快捷键:").pack(anchor="w", pady=(10, 0))
        self.hotkey_var = ctk.StringVar()
        self.hotkey_menu = ctk.CTkOptionMenu(
            tab,
            variable=self.hotkey_var,
            values=["右 Alt", "右 Ctrl", "右 Shift", "F4", "F8", "F9", "F10"],
        )
        self.hotkey_menu.pack(fill="x", pady=(0, 10))

        # 触发模式
        ctk.CTkLabel(tab, text="触发方式:").pack(anchor="w")
        self.mode_var = ctk.StringVar()
        self.mode_menu = ctk.CTkOptionMenu(
            tab,
            variable=self.mode_var,
            values=["按住说话", "切换模式"],
        )
        self.mode_menu.pack(fill="x", pady=(0, 10))

        # 语言
        ctk.CTkLabel(tab, text="识别语言:").pack(anchor="w")
        self.lang_var = ctk.StringVar()
        self.lang_menu = ctk.CTkOptionMenu(
            tab,
            variable=self.lang_var,
            values=["中文", "English", "日本語", "自动检测"],
        )
        self.lang_menu.pack(fill="x", pady=(0, 10))

        # 开关选项
        self.auto_start_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="开机自动启动",
            variable=self.auto_start_var,
        ).pack(anchor="w", pady=(5, 5))

        self.minimized_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="启动时最小化到托盘",
            variable=self.minimized_var,
        ).pack(anchor="w", pady=(0, 5))

        self.notify_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="显示系统通知",
            variable=self.notify_var,
        ).pack(anchor="w", pady=(0, 10))

    def _create_engine_tab(self):
        """语音识别设置选项卡"""
        tab = self.tabview.add("语音识别")

        # 模型选择
        ctk.CTkLabel(tab, text="识别模型:").pack(anchor="w", pady=(10, 0))
        self.model_var = ctk.StringVar()
        self.model_menu = ctk.CTkOptionMenu(
            tab,
            variable=self.model_var,
            values=[
                "Tiny (75MB, 最快)",
                "Base (150MB, 推荐)",
                "Small (500MB, 高精度)",
                "Medium (1.5GB, 专业)",
            ],
        )
        self.model_menu.pack(fill="x", pady=(0, 10))

        # 计算精度
        ctk.CTkLabel(tab, text="计算精度:").pack(anchor="w")
        self.compute_var = ctk.StringVar()
        self.compute_menu = ctk.CTkOptionMenu(
            tab,
            variable=self.compute_var,
            values=["Int8 (推荐)", "Float16", "Float32 (最准确)"],
        )
        self.compute_menu.pack(fill="x", pady=(0, 10))

        # 束搜索大小
        ctk.CTkLabel(tab, text="束搜索大小:").pack(anchor="w")
        self.beam_var = ctk.IntVar(value=5)
        self.beam_slider = ctk.CTkSlider(
            tab,
            from_=1,
            to=10,
            number_of_steps=9,
            variable=self.beam_var,
            command=lambda v: self.beam_label.configure(text=f"束搜索大小: {int(v)}"),
        )
        self.beam_slider.pack(fill="x")
        self.beam_label = ctk.CTkLabel(tab, text="束搜索大小: 5")
        self.beam_label.pack(anchor="w", pady=(0, 10))

        # 音频设备
        ctk.CTkLabel(tab, text="麦克风设备:").pack(anchor="w")
        self.device_var = ctk.StringVar()
        device_values = ["默认设备"]
        try:
            for dev in AudioRecorder.list_devices():
                device_values.append(dev["name"])
        except Exception:
            pass
        self.device_menu = ctk.CTkOptionMenu(
            tab,
            variable=self.device_var,
            values=device_values,
        )
        self.device_menu.pack(fill="x", pady=(0, 10))

    def _create_advanced_tab(self):
        """高级设置选项卡"""
        tab = self.tabview.add("高级设置")

        # VAD
        ctk.CTkLabel(tab, text="语音活动检测 (VAD)", font=("", 14, "bold")).pack(
            anchor="w", pady=(10, 5)
        )

        self.vad_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="启用 VAD 过滤",
            variable=self.vad_var,
        ).pack(anchor="w", pady=(0, 5))

        ctk.CTkLabel(tab, text="VAD 灵敏度:").pack(anchor="w")
        self.vad_threshold_var = ctk.IntVar(value=50)
        self.vad_slider = ctk.CTkSlider(
            tab,
            from_=0,
            to=100,
            variable=self.vad_threshold_var,
            command=lambda v: self.vad_label.configure(text=f"{int(v)}%"),
        )
        self.vad_slider.pack(fill="x")
        self.vad_label = ctk.CTkLabel(tab, text="50%")
        self.vad_label.pack(anchor="w", pady=(0, 15))

        # 文本输入
        ctk.CTkLabel(tab, text="文本输入", font=("", 14, "bold")).pack(
            anchor="w", pady=(5, 5)
        )

        self.restore_clip_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="粘贴后恢复剪贴板内容",
            variable=self.restore_clip_var,
        ).pack(anchor="w", pady=(0, 15))

        # Emoji
        ctk.CTkLabel(tab, text="表情符号", font=("", 14, "bold")).pack(
            anchor="w", pady=(5, 5)
        )

        self.emoji_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="启用语义 Emoji",
            variable=self.emoji_var,
        ).pack(anchor="w", pady=(0, 5))

        ctk.CTkLabel(tab, text="Emoji 密度:").pack(anchor="w")
        self.emoji_density_var = ctk.StringVar()
        ctk.CTkOptionMenu(
            tab,
            variable=self.emoji_density_var,
            values=["低", "中", "高"],
        ).pack(fill="x", pady=(0, 10))

    def _load_settings(self):
        """从配置加载设置"""
        # 快捷键映射
        hotkey_map = {
            "right alt": "右 Alt",
            "right ctrl": "右 Ctrl",
            "right shift": "右 Shift",
            "f4": "F4",
            "f8": "F8",
            "f9": "F9",
            "f10": "F10",
        }
        self.hotkey_var.set(hotkey_map.get(self.config.get("hotkey"), "右 Alt"))

        mode_map = {"hold": "按住说话", "toggle": "切换模式"}
        self.mode_var.set(mode_map.get(self.config.get("hotkey_mode"), "按住说话"))

        lang_map = {
            "zh": "中文",
            "en": "English",
            "ja": "日本語",
            None: "自动检测",
            "": "自动检测",
        }
        self.lang_var.set(lang_map.get(self.config.get("language"), "中文"))

        self.auto_start_var.set(self.config.get("auto_start", False))
        self.minimized_var.set(self.config.get("start_minimized", True))
        self.notify_var.set(self.config.get("show_notifications", True))

        # 模型
        model_map = {
            "tiny": "Tiny (75MB, 最快)",
            "base": "Base (150MB, 推荐)",
            "small": "Small (500MB, 高精度)",
            "medium": "Medium (1.5GB, 专业)",
        }
        self.model_var.set(
            model_map.get(self.config.get("model_size"), "Base (150MB, 推荐)")
        )

        compute_map = {
            "int8": "Int8 (推荐)",
            "float16": "Float16",
            "float32": "Float32 (最准确)",
        }
        self.compute_var.set(
            compute_map.get(self.config.get("compute_type"), "Int8 (推荐)")
        )

        beam = self.config.get("beam_size", 5)
        self.beam_var.set(beam)
        self.beam_label.configure(text=f"束搜索大小: {beam}")

        self.device_var.set("默认设备")

        # 高级
        self.vad_var.set(self.config.get("vad_filter", True))
        threshold = int(self.config.get("vad_threshold", 0.5) * 100)
        self.vad_threshold_var.set(threshold)
        self.vad_label.configure(text=f"{threshold}%")

        self.restore_clip_var.set(self.config.get("restore_clipboard", True))
        self.emoji_var.set(self.config.get("emoji_enabled", True))

        density_map = {"low": "低", "medium": "中", "high": "高"}
        self.emoji_density_var.set(
            density_map.get(self.config.get("emoji_density"), "中")
        )

    def _save_settings(self):
        """保存设置"""
        changes = {}

        # 快捷键
        hotkey_reverse = {
            "右 Alt": "right alt",
            "右 Ctrl": "right ctrl",
            "右 Shift": "right shift",
            "F4": "f4",
            "F8": "f8",
            "F9": "f9",
            "F10": "f10",
        }
        hotkey = hotkey_reverse.get(self.hotkey_var.get(), "right alt")
        if hotkey != self.config.get("hotkey"):
            changes["hotkey"] = hotkey

        mode_reverse = {"按住说话": "hold", "切换模式": "toggle"}
        mode = mode_reverse.get(self.mode_var.get(), "hold")
        if mode != self.config.get("hotkey_mode"):
            changes["hotkey_mode"] = mode

        lang_reverse = {"中文": "zh", "English": "en", "日本語": "ja", "自动检测": None}
        lang = lang_reverse.get(self.lang_var.get())
        if lang != self.config.get("language"):
            changes["language"] = lang

        if self.auto_start_var.get() != self.config.get("auto_start"):
            changes["auto_start"] = self.auto_start_var.get()
        if self.minimized_var.get() != self.config.get("start_minimized"):
            changes["start_minimized"] = self.minimized_var.get()
        if self.notify_var.get() != self.config.get("show_notifications"):
            changes["show_notifications"] = self.notify_var.get()

        # 模型
        model_reverse = {
            "Tiny (75MB, 最快)": "tiny",
            "Base (150MB, 推荐)": "base",
            "Small (500MB, 高精度)": "small",
            "Medium (1.5GB, 专业)": "medium",
        }
        model = model_reverse.get(self.model_var.get(), "base")
        if model != self.config.get("model_size"):
            changes["model_size"] = model

        compute_reverse = {
            "Int8 (推荐)": "int8",
            "Float16": "float16",
            "Float32 (最准确)": "float32",
        }
        compute = compute_reverse.get(self.compute_var.get(), "int8")
        if compute != self.config.get("compute_type"):
            changes["compute_type"] = compute

        beam = self.beam_var.get()
        if beam != self.config.get("beam_size"):
            changes["beam_size"] = beam

        # 高级
        if self.vad_var.get() != self.config.get("vad_filter"):
            changes["vad_filter"] = self.vad_var.get()

        vad_threshold = self.vad_threshold_var.get() / 100
        if vad_threshold != self.config.get("vad_threshold"):
            changes["vad_threshold"] = vad_threshold

        if self.restore_clip_var.get() != self.config.get("restore_clipboard"):
            changes["restore_clipboard"] = self.restore_clip_var.get()

        if self.emoji_var.get() != self.config.get("emoji_enabled"):
            changes["emoji_enabled"] = self.emoji_var.get()

        density_reverse = {"低": "low", "中": "medium", "高": "high"}
        density = density_reverse.get(self.emoji_density_var.get(), "medium")
        if density != self.config.get("emoji_density"):
            changes["emoji_density"] = density

        # 保存
        if changes:
            for key, value in changes.items():
                self.config.set(key, value)
            if self._on_settings_changed:
                self._on_settings_changed(changes)

        self.destroy()

    def _reset_settings(self):
        """恢复默认设置"""
        dialog = ctk.CTkInputDialog(
            text="输入 'reset' 确认恢复默认设置:",
            title="确认",
        )
        result = dialog.get_input()
        if result and result.strip().lower() == "reset":
            self.config.reset()
            self._load_settings()
