"""语音输入法主程序 - 集成所有模块的应用入口"""

import sys
import logging
from enum import Enum
from typing import Optional

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QThread, pyqtSlot

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


class AppWorker(QObject):
    """后台工作线程，处理语音识别"""

    transcription_complete = pyqtSignal(str)  # 识别完成
    transcription_failed = pyqtSignal(str)    # 识别失败
    model_loaded = pyqtSignal()               # 模型加载完成
    model_load_failed = pyqtSignal(str)       # 模型加载失败

    def __init__(
        self,
        engine: WhisperEngine,
        config: Config,
        hotword_manager: HotwordManager,
        punctuation_processor: PunctuationProcessor,
        emoji_injector: EmojiInjector,
    ):
        super().__init__()
        self.engine = engine
        self.config = config
        self.hotword_manager = hotword_manager
        self.punctuation_processor = punctuation_processor
        self.emoji_injector = emoji_injector

    @pyqtSlot()
    def load_model(self):
        """在后台线程加载模型"""
        try:
            self.engine.load_model(on_progress=lambda msg: logger.info(msg))
            self.model_loaded.emit()
        except Exception as e:
            self.model_load_failed.emit(str(e))

    @pyqtSlot(object)
    def transcribe(self, audio_data):
        """在后台线程执行语音识别"""
        try:
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

                self.transcription_complete.emit(text)
            else:
                self.transcription_failed.emit("未能识别出文字")
        except Exception as e:
            self.transcription_failed.emit(str(e))


class VoiceInputApp:
    """语音输入法主应用"""

    def __init__(self):
        # 初始化配置
        self.config = Config()

        # 应用状态
        self._state = AppState.IDLE
        self._service_active = True

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

        # 快捷键管理器（回调稍后设置）
        self.hotkey_manager = HotkeyManager(
            hotkey=self.config.get("hotkey", "right alt"),
            mode=self.config.get("hotkey_mode", "hold"),
            on_start=self._on_recording_start,
            on_stop=self._on_recording_stop,
            on_cancel=self._on_recording_cancel,
        )

    def run(self):
        """启动应用"""
        # 创建 Qt 应用
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

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

        # 创建工作线程
        self._setup_worker()

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

        # 运行应用事件循环
        return self.app.exec()

    def _setup_worker(self):
        """设置后台工作线程"""
        self.worker_thread = QThread()
        self.worker = AppWorker(
            self.engine,
            self.config,
            self.hotword_manager,
            self.punctuation_processor,
            self.emoji_injector,
        )
        self.worker.moveToThread(self.worker_thread)

        # 连接信号
        self.worker.transcription_complete.connect(self._on_transcription_complete)
        self.worker.transcription_failed.connect(self._on_transcription_failed)
        self.worker.model_loaded.connect(self._on_model_loaded)
        self.worker.model_load_failed.connect(self._on_model_load_failed)

        self.worker_thread.start()

    def _load_model_async(self):
        """异步加载模型"""
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(self.worker, "load_model", Qt.ConnectionType.QueuedConnection)

    def _on_recording_start(self):
        """开始录音回调"""
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
        """停止录音回调"""
        if self._state != AppState.RECORDING:
            return

        # 停止录音获取音频数据
        audio_data = self.recorder.stop_recording()

        if audio_data is None or len(audio_data) < 1600:
            logger.info("录音数据不足，跳过识别")
            self._state = AppState.IDLE
            self.tray.set_state(AppState.IDLE)
            return

        duration = self.recorder.get_audio_duration(audio_data)
        logger.info(f"录音完成，时长: {duration:.1f}秒")

        # 切换到识别状态
        self._state = AppState.PROCESSING
        self.tray.set_state(AppState.PROCESSING)

        # 在后台线程执行识别
        from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self.worker,
            "transcribe",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(object, audio_data),
        )

    def _on_recording_cancel(self):
        """取消录音回调"""
        self.recorder.cancel_recording()
        self._state = AppState.IDLE
        self.tray.set_state(AppState.IDLE)
        logger.info("录音已取消")

    def _on_transcription_complete(self, text: str):
        """识别完成回调"""
        logger.info(f"识别结果: {text}")

        # 注入文本到当前窗口
        success = self.injector.inject_text(text)

        if success:
            logger.info("文本输入成功")
        else:
            logger.error("文本输入失败")
            if self.config.get("show_notifications", True):
                self.tray.show_notification("语音输入法", "文本输入失败")

        # 恢复到空闲状态
        self._state = AppState.IDLE
        self.tray.set_state(AppState.IDLE)

    def _on_transcription_failed(self, error: str):
        """识别失败回调"""
        logger.error(f"识别失败: {error}")

        if self.config.get("show_notifications", True):
            self.tray.show_notification("语音输入法", f"识别失败: {error}")

        self._state = AppState.IDLE
        self.tray.set_state(AppState.IDLE)

    def _on_model_loaded(self):
        """模型加载完成回调"""
        logger.info("模型加载完成")

    def _on_model_load_failed(self, error: str):
        """模型加载失败回调"""
        logger.error(f"模型加载失败: {error}")
        if self.config.get("show_notifications", True):
            self.tray.show_notification("语音输入法", f"模型加载失败: {error}")

    def _show_settings(self):
        """显示设置窗口"""
        if not hasattr(self, "_settings_window") or self._settings_window is None:
            self._settings_window = SettingsWindow(self.config)
            self._settings_window.settings_changed.connect(self._on_settings_changed)

        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _on_settings_changed(self, changes: dict):
        """处理设置变更"""
        logger.info(f"设置变更: {list(changes.keys())}")

        # 处理特殊操作
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

        # 注销快捷键
        self.hotkey_manager.unregister()

        # 停止工作线程
        if hasattr(self, "worker_thread"):
            self.worker_thread.quit()
            self.worker_thread.wait(3000)

        # 清理托盘图标
        if hasattr(self, "tray"):
            self.tray.cleanup()

        # 退出应用
        self.app.quit()


def main():
    """应用入口"""
    app = VoiceInputApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
