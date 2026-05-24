"""语音输入法主程序 - 集成所有模块的应用入口"""

import os
import sys
import signal
import logging
import threading
import queue
import time
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
from input.text_injector import TextInjector
from hotkey.hotkey_manager import HotkeyManager
from ui.tray_app import TrayApp, AppState
from ui.settings_window import SettingsWindow


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

        # 初始化各模块
        self._init_modules()

    def _init_modules(self):
        """初始化所有模块"""
        # 音频录制器
        self.recorder = AudioRecorder(
            sample_rate=self.config.get("sample_rate", 16000),
            device=self.config.get("audio_device"),
        )

        # 语音识别引擎
        self.engine = WhisperEngine(
            model_size=self.config.get("model_size", "base"),
            compute_type=self.config.get("compute_type", "int8"),
            cache_dir=str(self.config.model_cache_dir),
        )

        # 热词管理器
        self.hotword_manager = HotwordManager(
            hotword_file=str(self.config.hotword_file),
        )

        # 标点优化器
        self.punctuation_processor = PunctuationProcessor(
            auto_paragraph=self.config.get("auto_paragraph", False),
        )

        # Emoji 注入器
        self.emoji_injector = EmojiInjector(
            enabled=self.config.get("emoji_enabled", True),
            density=self.config.get("emoji_density", "medium"),
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

    def run(self):
        """启动应用"""
        # 获取快捷键显示名称
        hotkey_display = self._get_hotkey_display()

        # 创建托盘应用
        self.tray = TrayApp(
            hotkey=hotkey_display,
            on_settings=self._show_settings,
            on_quit=self._quit,
            on_toggle=self._toggle_service,
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

        # 主线程循环：处理结果 + 等待退出信号
        signal.signal(signal.SIGINT, lambda *_: self._quit())

        try:
            while not self._stop_event.is_set():
                # 非阻塞检查结果队列
                try:
                    result_type, result_data = self._result_queue.get(timeout=0.5)
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

            elif task_type == "transcribe":
                try:
                    audio_data = task_data

                    # 构建热词 initial_prompt
                    initial_prompt = self.hotword_manager.build_initial_prompt(
                        weight=self.config.get("hotword_weight", 1.5)
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
                        # 后处理流水线: 标点优化 -> emoji 注入
                        text = self.punctuation_processor.process(
                            text, language=self.config.get("language")
                        )
                        text = self.emoji_injector.process(text)
                        self._result_queue.put(("transcription_complete", text))
                    else:
                        self._result_queue.put(("transcription_failed", "未能识别出文字"))

                except Exception as e:
                    self._result_queue.put(("transcription_failed", str(e)))

        logger.info("Worker 线程已退出")

    def _handle_result(self, result_type: str, data):
        """在主线程中处理 worker 返回的结果"""
        if result_type == "transcription_complete":
            logger.info(f"识别结果: {data}")
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
            logger.info("模型加载完成")

        elif result_type == "model_load_failed":
            logger.error(f"模型加载失败: {data}")
            if self.config.get("show_notifications", True):
                self.tray.show_notification("语音输入法", f"模型加载失败: {data}")

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

        if not self.recorder.start_recording():
            logger.error("无法启动录音")
            self._state = AppState.IDLE
            self.tray.set_state(AppState.IDLE)

    def _on_recording_stop(self):
        """停止录音回调（从快捷键线程调用）"""
        if self._state != AppState.RECORDING:
            return

        audio_data = self.recorder.stop_recording()

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

    # ---- 模型加载 ----

    def _load_model_async(self):
        """异步加载模型"""
        self._task_queue.put(("load_model", None))

    # ---- 设置窗口 ----

    def _show_settings(self):
        """显示设置窗口"""
        import customtkinter as ctk

        # 如果窗口已存在且还在显示，直接置顶
        if self._settings_window is not None:
            try:
                self._settings_window.focus()
                return
            except Exception:
                self._settings_window = None

        self._settings_window = SettingsWindow(
            self.config,
            on_settings_changed=self._on_settings_changed,
        )
        self._settings_window.protocol("WM_DELETE_WINDOW", self._on_settings_closed)

        # 让 CustomTkinter 事件循环运行（非阻塞）
        self._settings_window.after(100, self._pump_tk_events)

    def _pump_tk_events(self):
        """持续处理 CustomTkinter 事件"""
        if self._settings_window is not None:
            try:
                self._settings_window.update_idletasks()
                self._settings_window.after(100, self._pump_tk_events)
            except Exception:
                self._settings_window = None

    def _on_settings_closed(self):
        """设置窗口关闭"""
        if self._settings_window:
            self._settings_window.destroy()
            self._settings_window = None

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

    # ---- 服务控制 ----

    def _toggle_service(self, active: bool):
        """切换服务开关"""
        self._service_active = active
        self.hotkey_manager.set_active(active)
        logger.info(f"服务{'启动' if active else '停止'}")

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

        logger.info("已退出")


def main():
    """应用入口"""
    app = VoiceInputApp()
    app.run()


if __name__ == "__main__":
    main()
