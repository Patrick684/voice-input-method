"""设置窗口模块 - 使用 CustomTkinter 实现"""

from typing import Callable, Optional

import customtkinter as ctk

from config import Config
from audio.recorder import AudioRecorder


class SettingsWindow(ctk.CTkToplevel):
    """应用设置窗口"""

    def __init__(
        self,
        config: Config,
        on_settings_changed: Optional[Callable[[dict], None]] = None,
        hotword_manager=None,
        post_processor=None,
        history=None,
        master=None,
    ):
        super().__init__(master)
        self.config = config
        self._on_settings_changed = on_settings_changed
        self._hotword_manager = hotword_manager
        self._post_processor = post_processor
        self._history = history

        self.title("语音输入法 - 设置")
        self.geometry("560x580")
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
        self._create_hotwords_tab()
        self._create_advanced_tab()
        self._create_history_tab()

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

        # 主题设置
        ctk.CTkLabel(tab, text="外观主题:").pack(anchor="w")
        self.theme_var = ctk.StringVar()
        ctk.CTkOptionMenu(
            tab,
            variable=self.theme_var,
            values=["跟随系统", "亮色", "暗色"],
            command=self._on_theme_changed,
        ).pack(fill="x", pady=(0, 10))

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

        # 后处理规则
        ctk.CTkLabel(tab, text="后处理规则", font=("", 14, "bold")).pack(
            anchor="w", pady=(5, 5)
        )

        self.post_process_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="启用文本替换修正",
            variable=self.post_process_var,
        ).pack(anchor="w", pady=(0, 5))

        self.post_builtin_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="启用预置替换规则",
            variable=self.post_builtin_var,
        ).pack(anchor="w", pady=(0, 10))

        # 历史记录
        ctk.CTkLabel(tab, text="历史记录", font=("", 14, "bold")).pack(
            anchor="w", pady=(5, 5)
        )

        self.history_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="保存识别历史",
            variable=self.history_var,
        ).pack(anchor="w", pady=(0, 10))

        # 流式识别
        ctk.CTkLabel(tab, text="流式识别", font=("", 14, "bold")).pack(
            anchor="w", pady=(5, 5)
        )

        self.streaming_var = ctk.BooleanVar()
        ctk.CTkSwitch(
            tab,
            text="启用流式识别（边说边识别）",
            variable=self.streaming_var,
        ).pack(anchor="w", pady=(0, 5))

        # 静音切句时长
        silence_frame = ctk.CTkFrame(tab, fg_color="transparent")
        silence_frame.pack(fill="x", pady=(0, 5))
        ctk.CTkLabel(silence_frame, text="静音切句时长:").pack(side="left")
        self.silence_duration_var = ctk.IntVar(value=8)  # 0.8s = 8 (x0.1)
        self.silence_duration_label = ctk.CTkLabel(silence_frame, text="0.8s", width=40)
        self.silence_duration_label.pack(side="right")
        ctk.CTkSlider(
            silence_frame,
            from_=5,
            to=20,
            number_of_steps=15,
            variable=self.silence_duration_var,
            command=self._on_silence_duration_changed,
        ).pack(side="right", fill="x", expand=True, padx=(5, 5))

    def _create_hotwords_tab(self):
        """热词管理选项卡"""
        tab = self.tabview.add("热词管理")

        # 预置词库
        ctk.CTkLabel(tab, text="预置词库", font=("", 14, "bold")).pack(
            anchor="w", pady=(10, 5)
        )

        self._builtin_switches = {}
        if self._hotword_manager:
            for cat_name in self._hotword_manager.get_builtin_categories():
                var = ctk.BooleanVar()
                ctk.CTkSwitch(
                    tab,
                    text=f"启用「{cat_name}」({len(self._hotword_manager.get_builtin_hotwords(cat_name))}词)",
                    variable=var,
                ).pack(anchor="w", pady=(0, 3))
                self._builtin_switches[cat_name] = var

        # 用户热词
        ctk.CTkLabel(tab, text="用户自定义热词", font=("", 14, "bold")).pack(
            anchor="w", pady=(15, 5)
        )

        # 热词显示框
        self._hotword_textbox = ctk.CTkTextbox(tab, height=180)
        self._hotword_textbox.pack(fill="both", expand=True, pady=(0, 5))

        ctk.CTkLabel(
            tab,
            text="每行一个热词，支持中英文混合。热词将注入 Whisper 提升识别率。",
            text_color="gray",
        ).pack(anchor="w")

        # 加载当前热词
        if self._hotword_manager:
            existing = self._hotword_manager.get_global_hotwords()
            self._hotword_textbox.insert("1.0", "\n".join(existing))

    def _create_history_tab(self):
        """识别历史选项卡"""
        tab = self.tabview.add("识别历史")

        # 统计信息栏
        stats_frame = ctk.CTkFrame(tab, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(10, 5))

        self._history_stats_label = ctk.CTkLabel(
            stats_frame, text="加载统计中...", text_color="gray"
        )
        self._history_stats_label.pack(anchor="w")

        # 搜索框
        search_frame = ctk.CTkFrame(tab, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 5))

        self._history_search_var = ctk.StringVar()
        ctk.CTkEntry(
            search_frame,
            placeholder_text="搜索历史记录...",
            textvariable=self._history_search_var,
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            search_frame,
            text="搜索",
            width=60,
            command=self._search_history,
        ).pack(side="left")

        ctk.CTkButton(
            search_frame,
            text="刷新",
            width=60,
            fg_color="gray",
            command=self._refresh_history,
        ).pack(side="left", padx=(5, 0))

        # 历史列表
        self._history_textbox = ctk.CTkTextbox(tab, height=260)
        self._history_textbox.pack(fill="both", expand=True, pady=(0, 5))

        # 底部按钮
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame,
            text="清空历史",
            width=80,
            fg_color="#d9534f",
            command=self._clear_history,
        ).pack(side="right")

        # 初始加载
        self._refresh_history()

    def _on_theme_changed(self, choice: str):
        """主题切换回调"""
        theme_map = {"跟随系统": "system", "亮色": "light", "暗色": "dark"}
        ctk.set_appearance_mode(theme_map.get(choice, "system"))

    def _on_silence_duration_changed(self, value):
        """静音切句时长滑块回调"""
        seconds = int(value) / 10
        self.silence_duration_label.configure(text=f"{seconds:.1f}s")

    def _refresh_history(self):
        """刷新历史记录显示"""
        if not self._history:
            self._history_stats_label.configure(text="历史记录未启用")
            return

        stats = self._history.get_statistics()
        self._history_stats_label.configure(
            text=f"共 {stats['total_records']} 条记录 | "
            f"{stats['total_characters']} 字 | "
            f"总时长 {stats['total_duration_seconds']}s"
        )

        records = self._history.get_records(limit=50)
        self._history_textbox.delete("1.0", "end")
        for rec in records:
            self._history_textbox.insert("end", f"[{rec.display_time}] {rec.text}\n")

    def _search_history(self):
        """搜索历史记录"""
        if not self._history:
            return
        keyword = self._history_search_var.get().strip()
        if not keyword:
            self._refresh_history()
            return

        results = self._history.search(keyword)
        self._history_textbox.delete("1.0", "end")
        self._history_stats_label.configure(
            text=f"搜索「{keyword}」: {len(results)} 条结果"
        )
        for rec in results[:50]:
            self._history_textbox.insert("end", f"[{rec.display_time}] {rec.text}\n")

    def _clear_history(self):
        """清空历史记录"""
        if not self._history:
            return
        dialog = ctk.CTkInputDialog(
            text="输入 'clear' 确认清空历史:",
            title="确认",
        )
        result = dialog.get_input()
        if result and result.strip().lower() == "clear":
            self._history.clear_all()
            self._refresh_history()

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

        # 后处理规则
        self.post_process_var.set(self.config.get("post_process_enabled", True))
        self.post_builtin_var.set(self.config.get("post_process_builtin", True))

        # 历史记录
        self.history_var.set(self.config.get("history_enabled", True))

        # 流式识别
        self.streaming_var.set(self.config.get("streaming_enabled", False))
        silence_val = self.config.get("stream_silence_duration", 0.8)
        self.silence_duration_var.set(int(silence_val * 10))
        self.silence_duration_label.configure(text=f"{silence_val:.1f}s")

        # 主题
        theme_map = {"system": "跟随系统", "light": "亮色", "dark": "暗色"}
        self.theme_var.set(
            theme_map.get(self.config.get("theme", "system"), "跟随系统")
        )

        # 热词预置分类开关
        if self._hotword_manager:
            active_builtin = self._hotword_manager.get_active_builtin_categories()
            for cat_name, var in self._builtin_switches.items():
                var.set(cat_name in active_builtin)

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

        # 后处理规则
        if self.post_process_var.get() != self.config.get("post_process_enabled"):
            changes["post_process_enabled"] = self.post_process_var.get()
        if self.post_builtin_var.get() != self.config.get("post_process_builtin"):
            changes["post_process_builtin"] = self.post_builtin_var.get()

        # 历史记录
        if self.history_var.get() != self.config.get("history_enabled"):
            changes["history_enabled"] = self.history_var.get()

        # 流式识别
        if self.streaming_var.get() != self.config.get("streaming_enabled"):
            changes["streaming_enabled"] = self.streaming_var.get()

        silence_dur = self.silence_duration_var.get() / 10
        if silence_dur != self.config.get("stream_silence_duration"):
            changes["stream_silence_duration"] = silence_dur

        # 主题
        theme_reverse = {"跟随系统": "system", "亮色": "light", "暗色": "dark"}
        theme = theme_reverse.get(self.theme_var.get(), "system")
        if theme != self.config.get("theme", "system"):
            changes["theme"] = theme

        # 热词管理（保存用户全局热词和预置分类开关）
        if self._hotword_manager:
            # 保存用户自定义热词
            new_hotwords_text = self._hotword_textbox.get("1.0", "end").strip()
            new_hotwords = [
                w.strip() for w in new_hotwords_text.split("\n") if w.strip()
            ]
            old_hotwords = self._hotword_manager.get_global_hotwords()
            if new_hotwords != old_hotwords:
                # 清除旧的，添加新的
                for w in old_hotwords:
                    self._hotword_manager.remove_global_hotword(w)
                for w in new_hotwords:
                    self._hotword_manager.add_global_hotword(w)

            # 保存预置分类开关
            for cat_name, var in self._builtin_switches.items():
                is_active = (
                    cat_name in self._hotword_manager.get_active_builtin_categories()
                )
                if var.get() and not is_active:
                    self._hotword_manager.activate_builtin_category(cat_name)
                elif not var.get() and is_active:
                    self._hotword_manager.deactivate_builtin_category(cat_name)

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
