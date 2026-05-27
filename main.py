"""语音输入法主程序 - 集成所有模块的应用入口"""

import os
import signal
import logging
import threading
import queue
import numpy as np
from typing import Optional

# 配置 HuggingFace 国内镜像（必须在 import faster-whisper/huggingface_hub 之前设置）
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from config import Config
from audio.recorder import AudioRecorder
from engine.whisper_engine import WhisperEngine
from engine.hotword_manager import HotwordManager
from engine.punctuation_processor import PunctuationProcessor
from engine.emoji_injector import EmojiInjector
from engine.post_processor import PostProcessor
from engine.punctuation_restorer import PunctuationRestorer
from engine.audio_preprocessor import AudioPreprocessor
from engine.text_corrector import TextCorrector
from engine.stream_vad import StreamVAD
from input.text_injector import TextInjector
from hotkey.hotkey_manager import HotkeyManager
from ui.tray_app import TrayApp, AppState
from ui.settings_window import SettingsWindow
from ui.transcribe_window import TranscribeWindow
from utils.history import RecognitionHistory

# 应用主题配置
import customtkinter as ctk

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("VoiceInput")


class VoiceInputApp:
    """语音输入法主应用"""

    def __init__(self):
        # 初始化配置
        self.config = Config()

        # 应用状态
        self._state = AppState.IDLE
        self._service_active = True

        # 线程通信
        self._task_queue: queue.Queue = queue.Queue()
        self._result_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # 设置窗口引用
        self._settings_window = None
        # 转写窗口引用
        self._transcribe_window = None
        # Tkinter 根窗口（隐藏）
        self._tk_root = None
        # 线程安全的 UI 动作队列（pystray 回调 -> 主线程）
        self._ui_actions: queue.Queue = queue.Queue()

        # 流式识别状态
        self._streaming_active = False  # 当前是否处于流式录音中
        self._stream_sentence_count = 0  # 本次流式录音已识别的句子数
        self._stream_clipboard_saved = False  # 是否已保存剪贴板
        self._original_clipboard = None  # 流式模式保存的原始剪贴板内容

        # 初始化各模块
        self._init_modules()

    def _init_modules(self):
        """初始化所有模块"""
        # 流式 VAD 检测器（提前初始化，因为 AudioRecorder 需要它的 feed 回调）
        self.stream_vad = StreamVAD(
            sample_rate=self.config.get("sample_rate", 16000),
            silence_threshold=self.config.get("stream_silence_threshold", 0.01),
            silence_duration=self.config.get("stream_silence_duration", 0.8),
            on_sentence_end=self._on_sentence_detected,
        )

        # 音频录制器（流式模式下将 StreamVAD.feed 作为实时回调）
        streaming_enabled = self.config.get("streaming_enabled", False)
        self.recorder = AudioRecorder(
            sample_rate=self.config.get("sample_rate", 16000),
            device=self.config.get("audio_device"),
            on_audio_chunk=self.stream_vad.feed if streaming_enabled else None,
        )

        # 音频预处理器（高通滤波 + 谱减降噪）
        self.audio_preprocessor = AudioPreprocessor(
            sample_rate=self.config.get("sample_rate", 16000),
            noise_reduction_strength=self.config.get("noise_reduction_strength", 1.0),
            enabled=self.config.get("audio_preprocessing", True),
        )

        # 语音识别引擎
        self.engine = WhisperEngine(
            model_size=self.config.get("model_size", "base"),
            compute_type=self.config.get("compute_type", "int8"),
            cache_dir=str(self.config.model_cache_dir),
            audio_preprocessor=self.audio_preprocessor,
        )

        # 热词管理器
        self.hotword_manager = HotwordManager(
            hotword_file=str(self.config.hotword_file),
        )

        # 标点优化器（语气修正，在 CT-Transformer 之后执行）
        self.punctuation_processor = PunctuationProcessor(
            auto_paragraph=self.config.get("auto_paragraph", False),
        )

        # 标点恢复引擎（CT-Transformer，将纯文本恢复为带标点文本）
        self.punctuation_restorer = PunctuationRestorer(
            cache_dir=str(self.config.model_cache_dir),
        )

        # Emoji 注入器
        self.emoji_injector = EmojiInjector(
            enabled=self.config.get("emoji_enabled", True),
            density=self.config.get("emoji_density", "medium"),
        )

        # 后处理规则引擎
        self.post_processor = PostProcessor(
            rules_file=str(self.config.rules_file),
        )

        # 同音纠错器
        self.text_corrector = TextCorrector(
            enabled=self.config.get("text_correction", True),
        )

        # 识别历史记录
        self.history = RecognitionHistory(
            history_file=str(self.config.history_file),
            max_records=self.config.get("history_max_records", 500),
        )

        # 文本输入器
        self.injector = TextInjector(
            restore_clipboard=self.config.get("restore_clipboard", True),
        )

        # 快捷键管理器
        self.hotkey_manager = HotkeyManager(
            hotkey=self.config.get("hotkey", "right alt"),
            mode=self.config.get("hotkey_mode", "hold"),
            on_start=self._on_recording_start,
            on_stop=self._on_recording_stop,
            on_cancel=self._on_recording_cancel,
        )

    def _ensure_tk_root(self):
        """确保 Tkinter 根窗口已创建（隐藏窗口，用于驱动事件循环）"""
        if self._tk_root is not None:
            return
        self._tk_root = ctk.CTk()
        self._tk_root.withdraw()  # 隐藏主窗口
        self._tk_root.overrideredirect(True)
        logger.info("Tkinter 根窗口已创建")

    def _schedule_ui_action(self, action):
        """线程安全地将 UI 动作调度到主线程执行"""
        self._ui_actions.put(action)

    def _process_ui_actions(self):
        """处理待执行的 UI 动作（主线程调用）"""
        while True:
            try:
                action = self._ui_actions.get_nowait()
                action()
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"UI 动作执行失败: {e}")

    def run(self):
        """启动应用"""
        # 应用保存的主题配置
        theme = self.config.get("theme", "system")
        ctk.set_appearance_mode(theme)

        # 创建隐藏的 Tkinter 根窗口（驱动 CTkToplevel 事件循环）
        self._ensure_tk_root()

        # 获取快捷键显示名称
        hotkey_display = self._get_hotkey_display()

        # 创建托盘应用
        self.tray = TrayApp(
            hotkey=hotkey_display,
            on_settings=lambda: self._schedule_ui_action(self._show_settings),
            on_quit=self._quit,
            on_toggle=self._toggle_service,
            on_transcribe=lambda: self._schedule_ui_action(self._show_transcribe),
        )
        self.tray.setup()

        # 启动后台 worker 线程
        self._start_worker()

        # 注册快捷键
        self.hotkey_manager.register()

        # 预加载模型
        self._load_model_async()

        logger.info("语音输入法已启动")

        if self.config.get("show_notifications", True):
            self.tray.show_notification(
                "语音输入法",
                f"已启动，按住 {hotkey_display} 开始说话",
            )

        # 主线程循环：处理结果 + Tkinter 事件 + UI 动作
        signal.signal(signal.SIGINT, lambda *_: self._quit())

        try:
            while not self._stop_event.is_set():
                # 处理 Tkinter 事件（包括用户交互）
                try:
                    self._tk_root.update()
                except Exception:
                    pass

                # 处理线程安全的 UI 动作
                self._process_ui_actions()

                # 非阻塞检查结果队列
                try:
                    result_type, result_data = self._result_queue.get(timeout=0.05)
                    self._handle_result(result_type, result_data)
                except queue.Empty:
                    pass
        except KeyboardInterrupt:
            pass

        self._cleanup()

    def _start_worker(self):
        """启动后台工作线程"""
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True, name="WorkerThread"
        )
        self._worker_thread.start()

    def _worker_loop(self):
        """Worker 线程主循环"""
        logger.info("Worker 线程已启动")

        while not self._stop_event.is_set():
            try:
                task_type, task_data = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if task_type == "load_model":
                try:
                    self.engine.load_model(on_progress=lambda msg: logger.info(msg))
                    self._result_queue.put(("model_loaded", None))
                except Exception as e:
                    self._result_queue.put(("model_load_failed", str(e)))

            elif task_type == "load_punctuation_model":
                try:
                    self.punctuation_restorer.load_model(
                        on_progress=lambda msg: logger.info(msg)
                    )
                    if self.punctuation_restorer.is_fallback:
                        logger.warning("标点恢复使用规则后备方案")
                    self._result_queue.put(("punctuation_model_loaded", None))
                except Exception as e:
                    logger.warning(f"标点恢复模型加载异常: {e}")
                    self._result_queue.put(("punctuation_model_loaded", None))

            elif task_type == "transcribe":
                try:
                    audio_data = task_data

                    # 构建热词 initial_prompt（含预置词库 + 用户自定义）
                    initial_prompt = self.hotword_manager.build_initial_prompt(
                        weight=self.config.get("hotword_weight", 1.5),
                        max_words=self.config.get("hotword_max_count", 30),
                    )

                    text = self.engine.transcribe(
                        audio_data,
                        language=self.config.get("language"),
                        initial_prompt=initial_prompt,
                        beam_size=self.config.get("beam_size", 5),
                        vad_filter=self.config.get("vad_filter", True),
                        vad_threshold=self.config.get("vad_threshold", 0.5),
                    )

                    if text:
                        # 后处理流水线: 繁转简 -> 同音纠错 -> 标点恢复 -> 语气修正 -> emoji -> 规则替换
                        text = self._to_simplified(text)
                        text = self.text_corrector.correct(text)
                        text = self.punctuation_restorer.restore(text)
                        text = self.punctuation_processor.process(
                            text, language=self.config.get("language")
                        )
                        text = self.emoji_injector.process(text)
                        if self.config.get("post_process_enabled", True):
                            text = self.post_processor.process(text)
                        self._result_queue.put(("transcription_complete", text))
                    else:
                        self._result_queue.put(
                            ("transcription_failed", "未能识别出文字")
                        )

                except Exception as e:
                    self._result_queue.put(("transcription_failed", str(e)))

            elif task_type == "stream_transcribe":
                # 流式识别：识别单个句子
                try:
                    audio_data = task_data

                    initial_prompt = self.hotword_manager.build_initial_prompt(
                        weight=self.config.get("hotword_weight", 1.5),
                        max_words=self.config.get("hotword_max_count", 30),
                    )

                    text = self.engine.transcribe(
                        audio_data,
                        language=self.config.get("language"),
                        initial_prompt=initial_prompt,
                        beam_size=self.config.get("beam_size", 5),
                        vad_filter=self.config.get("vad_filter", True),
                        vad_threshold=self.config.get("vad_threshold", 0.5),
                    )

                    if text:
                        # 流式后处理流水线（同批处理）
                        text = self._to_simplified(text)
                        text = self.text_corrector.correct(text)
                        text = self.punctuation_restorer.restore(text)
                        text = self.punctuation_processor.process(
                            text, language=self.config.get("language")
                        )
                        text = self.emoji_injector.process(text)
                        if self.config.get("post_process_enabled", True):
                            text = self.post_processor.process(text)
                        self._result_queue.put(("stream_transcription_complete", text))
                    else:
                        self._result_queue.put(
                            ("stream_transcription_failed", "流式句子识别失败")
                        )

                except Exception as e:
                    self._result_queue.put(("stream_transcription_failed", str(e)))

        logger.info("Worker 线程已退出")

    def _handle_result(self, result_type: str, data):
        """在主线程中处理 worker 返回的结果"""
        if result_type == "transcription_complete":
            logger.info(f"识别结果: {data}")

            # 保存识别历史
            if self.config.get("history_enabled", True):
                self.history.add_record(
                    text=data,
                    model=self.config.get("model_size", "small"),
                )

            success = self.injector.inject_text(data)
            if success:
                logger.info("文本输入成功")
            else:
                logger.error("文本输入失败")
                if self.config.get("show_notifications", True):
                    self.tray.show_notification("语音输入法", "文本输入失败")
            self._state = AppState.IDLE
            self.tray.set_state(AppState.IDLE)

        elif result_type == "transcription_failed":
            logger.error(f"识别失败: {data}")
            if self.config.get("show_notifications", True):
                self.tray.show_notification("语音输入法", f"识别失败: {data}")
            self._state = AppState.IDLE
            self.tray.set_state(AppState.IDLE)

        elif result_type == "model_loaded":
            logger.info("Whisper 模型加载完成")

        elif result_type == "punctuation_model_loaded":
            logger.info("标点恢复模型加载完成")

        elif result_type == "model_load_failed":
            logger.error(f"模型加载失败: {data}")
            if self.config.get("show_notifications", True):
                self.tray.show_notification("语音输入法", f"模型加载失败: {data}")

        elif result_type == "stream_transcription_complete":
            # 流式识别：单句完成，立即粘贴
            self._stream_sentence_count += 1
            logger.info(f"流式句子 #{self._stream_sentence_count}: {data}")

            # 保存识别历史
            if self.config.get("history_enabled", True):
                self.history.add_record(
                    text=data,
                    model=self.config.get("model_size", "small"),
                )

            # 流式粘贴：不恢复剪贴板（在录音结束时统一恢复）
            try:
                import pyperclip
                import keyboard
                import time

                pyperclip.copy(data)
                time.sleep(0.03)
                keyboard.send("ctrl+v")
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"流式粘贴失败: {e}")

            # 恢复录音状态图标（如果还在录音）
            if self._streaming_active:
                self.tray.set_state(AppState.RECORDING)
            else:
                # 最后一句（尾句）识别完成，恢复剪贴板并回到 IDLE
                self._restore_stream_clipboard()
                self._state = AppState.IDLE
                self.tray.set_state(AppState.IDLE)

        elif result_type == "stream_transcription_failed":
            logger.error(f"流式句子识别失败: {data}")
            # 流式模式下不因单句失败而中断，继续录音
            if self._streaming_active:
                self.tray.set_state(AppState.RECORDING)
            else:
                self._restore_stream_clipboard()
                self._state = AppState.IDLE
                self.tray.set_state(AppState.IDLE)

    # ---- 录音回调 ----

    def _on_recording_start(self):
        """开始录音回调（从快捷键线程调用）"""
        if not self._service_active:
            return

        if self.engine.is_processing:
            logger.warning("正在处理上一段音频，忽略本次录音")
            return

        self._state = AppState.RECORDING
        self.tray.set_state(AppState.RECORDING)

        # 流式模式：重置 VAD 并保存剪贴板
        if self.config.get("streaming_enabled", False):
            self._streaming_active = True
            self._stream_sentence_count = 0
            self._stream_clipboard_saved = False
            self._original_clipboard = None
            self.stream_vad.reset()
            # 提前保存剪贴板，流式粘贴时不再反复保存/恢复
            if self.config.get("restore_clipboard", True):
                try:
                    import pyperclip

                    self._original_clipboard = pyperclip.paste()
                    self._stream_clipboard_saved = True
                except Exception:
                    pass

        if not self.recorder.start_recording():
            logger.error("无法启动录音")
            self._state = AppState.IDLE
            self.tray.set_state(AppState.IDLE)
            self._streaming_active = False

    def _on_recording_stop(self):
        """停止录音回调（从快捷键线程调用）"""
        if self._state != AppState.RECORDING:
            return

        audio_data = self.recorder.stop_recording()

        # 流式模式：处理尾句
        if self._streaming_active:
            self._streaming_active = False
            tail_audio = self.stream_vad.flush()
            if tail_audio is not None and len(tail_audio) >= 1600:
                logger.info(
                    f"流式尾句: {len(tail_audio) / self.config.get('sample_rate', 16000):.1f}s"
                )
                self._state = AppState.PROCESSING
                self.tray.set_state(AppState.PROCESSING)
                self._task_queue.put(("stream_transcribe", tail_audio))
                return

            # 流式模式无尾句：恢复剪贴板并回到 IDLE
            self._restore_stream_clipboard()
            if self._stream_sentence_count == 0:
                # 流式模式下一句都没识别出来，回退到批处理
                if audio_data is not None and len(audio_data) >= 1600:
                    self._state = AppState.PROCESSING
                    self.tray.set_state(AppState.PROCESSING)
                    self._task_queue.put(("transcribe", audio_data))
                    return
                logger.info("流式录音数据不足，跳过识别")

            self._state = AppState.IDLE
            self.tray.set_state(AppState.IDLE)
            return

        # 非流式模式：原有逻辑
        if audio_data is None or len(audio_data) < 1600:
            logger.info("录音数据不足，跳过识别")
            self._state = AppState.IDLE
            self.tray.set_state(AppState.IDLE)
            return

        duration = self.recorder.get_audio_duration(audio_data)
        logger.info(f"录音完成，时长: {duration:.1f}秒")

        self._state = AppState.PROCESSING
        self.tray.set_state(AppState.PROCESSING)

        # 将识别任务放入队列
        self._task_queue.put(("transcribe", audio_data))

    def _on_recording_cancel(self):
        """取消录音回调"""
        self.recorder.cancel_recording()
        self._state = AppState.IDLE
        self.tray.set_state(AppState.IDLE)
        logger.info("录音已取消")

    # ---- 流式识别回调 ----

    def _on_sentence_detected(self, audio_data: np.ndarray):
        """流式 VAD 检测到句子边界回调（在音频线程中调用）"""
        if not self._streaming_active:
            return

        if len(audio_data) < 1600:
            return

        # 更新状态为 STREAMING（录音中 + 识别中）
        self.tray.set_state(AppState.STREAMING)

        # 将句子音频送入识别队列
        self._task_queue.put(("stream_transcribe", audio_data))
        logger.info(
            f"流式句子 #{self._stream_sentence_count + 1}: "
            f"{len(audio_data) / self.config.get('sample_rate', 16000):.1f}s"
        )

    def _restore_stream_clipboard(self):
        """流式模式结束后恢复剪贴板"""
        if self._stream_clipboard_saved and self._original_clipboard is not None:
            try:
                import pyperclip
                import time

                time.sleep(0.3)  # 等待最后一次粘贴完成
                pyperclip.copy(self._original_clipboard)
            except Exception:
                pass
        self._stream_clipboard_saved = False
        self._original_clipboard = None

    # ---- 模型加载 ----

    def _load_model_async(self):
        """异步加载模型（Whisper + 标点恢复模型并行加载）"""
        self._task_queue.put(("load_model", None))
        self._task_queue.put(("load_punctuation_model", None))

    # ---- 设置窗口 ----

    def _show_settings(self):
        """显示设置窗口（主线程调用）"""
        # 如果窗口已存在且还在显示，直接置顶
        if self._settings_window is not None:
            try:
                self._settings_window.deiconify()
                self._settings_window.lift()
                self._settings_window.focus_force()
                return
            except Exception:
                self._settings_window = None

        self._ensure_tk_root()
        self._settings_window = SettingsWindow(
            self.config,
            on_settings_changed=self._on_settings_changed,
            hotword_manager=self.hotword_manager,
            post_processor=self.post_processor,
            history=self.history,
            master=self._tk_root,
        )
        self._settings_window.protocol("WM_DELETE_WINDOW", self._on_settings_closed)

    def _on_settings_closed(self):
        """设置窗口关闭"""
        if self._settings_window:
            self._settings_window.destroy()
            self._settings_window = None

    # ---- 转写窗口 ----

    def _show_transcribe(self):
        """显示转写窗口（主线程调用）"""
        # 如果窗口已存在且还在显示，直接置顶
        if self._transcribe_window is not None:
            try:
                self._transcribe_window.deiconify()
                self._transcribe_window.lift()
                self._transcribe_window.focus_force()
                return
            except Exception:
                self._transcribe_window = None

        self._ensure_tk_root()
        self._transcribe_window = TranscribeWindow(
            model_size=self.config.get("model_size", "small"),
            cache_dir=str(self.config.model_cache_dir),
            device=self.config.get("device", "cpu"),
            compute_type=self.config.get("compute_type", "int8"),
            punctuation_restorer=self.punctuation_restorer,
            punctuation_processor=self.punctuation_processor,
            audio_preprocessor=self.audio_preprocessor,
            text_corrector=self.text_corrector,
            master=self._tk_root,
        )
        self._transcribe_window.protocol("WM_DELETE_WINDOW", self._on_transcribe_closed)

    def _on_transcribe_closed(self):
        """转写窗口关闭"""
        if self._transcribe_window:
            self._transcribe_window.destroy()
            self._transcribe_window = None

    def _on_settings_changed(self, changes: dict):
        """处理设置变更"""
        logger.info(f"设置变更: {list(changes.keys())}")

        if changes.pop("_reload_model", False):
            self.engine.change_model(self.config.get("model_size"))
            self._load_model_async()

        if changes.pop("_unload_model", False):
            self.engine.unload_model()

        # 更新快捷键
        if "hotkey" in changes or "hotkey_mode" in changes:
            self.hotkey_manager.change_hotkey(
                self.config.get("hotkey"),
                self.config.get("hotkey_mode"),
            )
            hotkey_display = self._get_hotkey_display()
            self.tray.update_hotkey_display(hotkey_display)

        # 更新模型
        if "model_size" in changes:
            self.engine.change_model(changes["model_size"])
            self._load_model_async()

        # 更新音频设备
        if "audio_device" in changes:
            self.recorder.device = changes["audio_device"]

        # 更新标点设置
        if "auto_paragraph" in changes:
            self.punctuation_processor.auto_paragraph = changes["auto_paragraph"]

        # 更新 Emoji 设置
        if "emoji_enabled" in changes:
            self.emoji_injector.enabled = changes["emoji_enabled"]
        if "emoji_density" in changes:
            self.emoji_injector.set_density(changes["emoji_density"])

        # 更新后处理规则设置
        if "post_process_builtin" in changes:
            self.post_processor.set_builtin_enabled(changes["post_process_builtin"])

        # 更新主题
        if "theme" in changes:
            ctk.set_appearance_mode(changes["theme"])

        # 更新流式识别设置
        if "streaming_enabled" in changes:
            enabled = changes["streaming_enabled"]
            self.recorder.on_audio_chunk = self.stream_vad.feed if enabled else None

        if "stream_silence_duration" in changes:
            self.stream_vad.update_params(
                silence_duration=changes["stream_silence_duration"]
            )

        if "stream_silence_threshold" in changes:
            self.stream_vad.update_params(
                silence_threshold=changes["stream_silence_threshold"]
            )

    # ---- 服务控制 ----

    def _toggle_service(self, active: bool):
        """切换服务开关"""
        self._service_active = active
        self.hotkey_manager.set_active(active)
        logger.info(f"服务{'启动' if active else '停止'}")

    @staticmethod
    def _to_simplified(text: str) -> str:
        """繁体转简体（自动检测语言时 Whisper 可能输出繁体）"""
        try:
            import zhconv

            return zhconv.convert(text, "zh-cn")
        except ImportError:
            return text

    def _get_hotkey_display(self) -> str:
        """获取快捷键显示名称"""
        hotkey_map = {
            "right alt": "右Alt",
            "right ctrl": "右Ctrl",
            "right shift": "右Shift",
        }
        return hotkey_map.get(self.config.get("hotkey"), self.config.get("hotkey"))

    def _quit(self):
        """退出应用"""
        logger.info("正在退出...")
        self._stop_event.set()

    def _cleanup(self):
        """清理资源"""
        # 注销快捷键
        self.hotkey_manager.unregister()

        # 停止 worker 线程
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3)

        # 清理托盘图标
        if hasattr(self, "tray"):
            self.tray.cleanup()

        # 清理 Tkinter 根窗口
        if self._tk_root is not None:
            try:
                self._tk_root.destroy()
            except Exception:
                pass
            self._tk_root = None

        logger.info("已退出")


def main():
    """应用入口"""
    app = VoiceInputApp()
    app.run()


if __name__ == "__main__":
    main()
