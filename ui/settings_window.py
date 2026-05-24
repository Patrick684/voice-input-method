"""设置窗口模块 - 提供应用配置界面"""

from typing import Optional
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QPushButton,
    QLabel,
    QLineEdit,
    QGroupBox,
    QSpinBox,
    QSlider,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from config import Config
from audio.recorder import AudioRecorder


class SettingsWindow(QWidget):
    """应用设置窗口"""

    settings_changed = pyqtSignal(dict)  # 设置变更信号

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """构建 UI"""
        self.setWindowTitle("语音输入法 - 设置")
        self.setMinimumWidth(450)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # 选项卡
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 基本设置
        tabs.addTab(self._create_general_tab(), "基本设置")

        # 语音识别
        tabs.addTab(self._create_engine_tab(), "语音识别")

        # 高级设置
        tabs.addTab(self._create_advanced_tab(), "高级设置")

        # 底部按钮
        btn_layout = QHBoxLayout()
        layout.addLayout(btn_layout)

        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)

    def _create_general_tab(self) -> QWidget:
        """基本设置选项卡"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # 快捷键选择
        self.hotkey_combo = QComboBox()
        hotkeys = [
            ("right alt", "右 Alt"),
            ("right ctrl", "右 Ctrl"),
            ("right shift", "右 Shift"),
            ("f4", "F4"),
            ("f8", "F8"),
            ("f9", "F9"),
            ("f10", "F10"),
        ]
        for value, label in hotkeys:
            self.hotkey_combo.addItem(label, value)
        layout.addRow("录音快捷键:", self.hotkey_combo)

        # 触发模式
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("按住说话", "hold")
        self.mode_combo.addItem("切换模式", "toggle")
        layout.addRow("触发方式:", self.mode_combo)

        # 语言选择
        self.language_combo = QComboBox()
        self.language_combo.addItem("中文", "zh")
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("日本語", "ja")
        self.language_combo.addItem("自动检测", "")
        layout.addRow("识别语言:", self.language_combo)

        # 开机启动
        self.auto_start_check = QCheckBox("开机自动启动")
        layout.addRow("", self.auto_start_check)

        # 最小化启动
        self.minimized_check = QCheckBox("启动时最小化到托盘")
        layout.addRow("", self.minimized_check)

        # 显示通知
        self.notify_check = QCheckBox("显示系统通知")
        layout.addRow("", self.notify_check)

        return widget

    def _create_engine_tab(self) -> QWidget:
        """语音识别设置选项卡"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # 模型选择
        self.model_combo = QComboBox()
        models = [
            ("tiny", "Tiny (75MB, 最快, 一般准确度)"),
            ("base", "Base (150MB, 快, 较好准确度)"),
            ("small", "Small (500MB, 中等速度, 好准确度)"),
            ("medium", "Medium (1.5GB, 较慢, 很好准确度)"),
        ]
        for value, label in models:
            self.model_combo.addItem(label, value)
        layout.addRow("识别模型:", self.model_combo)

        # 计算精度
        self.compute_combo = QComboBox()
        self.compute_combo.addItem("Int8 (推荐，速度最快)", "int8")
        self.compute_combo.addItem("Float16", "float16")
        self.compute_combo.addItem("Float32 (最准确)", "float32")
        layout.addRow("计算精度:", self.compute_combo)

        # 束搜索大小
        self.beam_spin = QSpinBox()
        self.beam_spin.setRange(1, 10)
        self.beam_spin.setValue(5)
        layout.addRow("束搜索大小:", self.beam_spin)

        # 音频设备
        self.device_combo = QComboBox()
        self.device_combo.addItem("默认设备", None)
        try:
            for dev in AudioRecorder.list_devices():
                self.device_combo.addItem(dev["name"], dev["index"])
        except Exception:
            pass
        layout.addRow("麦克风设备:", self.device_combo)

        # 模型管理按钮
        model_btn_layout = QHBoxLayout()
        reload_btn = QPushButton("重新加载模型")
        reload_btn.clicked.connect(self._reload_model)
        model_btn_layout.addWidget(reload_btn)

        unload_btn = QPushButton("卸载模型")
        unload_btn.clicked.connect(self._unload_model)
        model_btn_layout.addWidget(unload_btn)

        layout.addRow("模型管理:", model_btn_layout)

        return widget

    def _create_advanced_tab(self) -> QWidget:
        """高级设置选项卡"""
        widget = QWidget()
        layout = QFormLayout(widget)

        # VAD 设置
        vad_group = QGroupBox("语音活动检测 (VAD)")
        vad_layout = QFormLayout(vad_group)

        self.vad_check = QCheckBox("启用 VAD 过滤")
        vad_layout.addRow(self.vad_check)

        self.vad_slider = QSlider(Qt.Orientation.Horizontal)
        self.vad_slider.setRange(0, 100)
        self.vad_slider.setValue(50)
        self.vad_label = QLabel("50%")
        self.vad_slider.valueChanged.connect(
            lambda v: self.vad_label.setText(f"{v}%")
        )

        vad_layout.addRow("VAD 灵敏度:", self.vad_slider)
        vad_layout.addRow("", self.vad_label)
        layout.addRow(vad_group)

        # 剪贴板设置
        clip_group = QGroupBox("文本输入")
        clip_layout = QFormLayout(clip_group)

        self.restore_clip_check = QCheckBox("粘贴后恢复剪贴板内容")
        clip_layout.addRow(self.restore_clip_check)
        layout.addRow(clip_group)

        return widget

    def _load_settings(self):
        """从配置加载设置"""
        # 基本设置
        idx = self.hotkey_combo.findData(self.config.get("hotkey"))
        if idx >= 0:
            self.hotkey_combo.setCurrentIndex(idx)

        idx = self.mode_combo.findData(self.config.get("hotkey_mode"))
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)

        lang = self.config.get("language") or ""
        idx = self.language_combo.findData(lang)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)

        self.auto_start_check.setChecked(self.config.get("auto_start", False))
        self.minimized_check.setChecked(self.config.get("start_minimized", True))
        self.notify_check.setChecked(self.config.get("show_notifications", True))

        # 语音识别
        idx = self.model_combo.findData(self.config.get("model_size"))
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        idx = self.compute_combo.findData(self.config.get("compute_type"))
        if idx >= 0:
            self.compute_combo.setCurrentIndex(idx)

        self.beam_spin.setValue(self.config.get("beam_size", 5))

        device = self.config.get("audio_device")
        if device is not None:
            idx = self.device_combo.findData(device)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)

        # 高级设置
        self.vad_check.setChecked(self.config.get("vad_filter", True))
        threshold = int(self.config.get("vad_threshold", 0.5) * 100)
        self.vad_slider.setValue(threshold)
        self.restore_clip_check.setChecked(self.config.get("restore_clipboard", True))

    def _save_settings(self):
        """保存设置"""
        changes = {}

        # 基本设置
        hotkey = self.hotkey_combo.currentData()
        if hotkey != self.config.get("hotkey"):
            changes["hotkey"] = hotkey

        mode = self.mode_combo.currentData()
        if mode != self.config.get("hotkey_mode"):
            changes["hotkey_mode"] = mode

        lang = self.language_combo.currentData() or None
        if lang != self.config.get("language"):
            changes["language"] = lang

        auto_start = self.auto_start_check.isChecked()
        if auto_start != self.config.get("auto_start"):
            changes["auto_start"] = auto_start

        minimized = self.minimized_check.isChecked()
        if minimized != self.config.get("start_minimized"):
            changes["start_minimized"] = minimized

        notify = self.notify_check.isChecked()
        if notify != self.config.get("show_notifications"):
            changes["show_notifications"] = notify

        # 语音识别
        model = self.model_combo.currentData()
        if model != self.config.get("model_size"):
            changes["model_size"] = model

        compute = self.compute_combo.currentData()
        if compute != self.config.get("compute_type"):
            changes["compute_type"] = compute

        beam = self.beam_spin.value()
        if beam != self.config.get("beam_size"):
            changes["beam_size"] = beam

        device = self.device_combo.currentData()
        if device != self.config.get("audio_device"):
            changes["audio_device"] = device

        # 高级设置
        vad = self.vad_check.isChecked()
        if vad != self.config.get("vad_filter"):
            changes["vad_filter"] = vad

        vad_threshold = self.vad_slider.value() / 100
        if vad_threshold != self.config.get("vad_threshold"):
            changes["vad_threshold"] = vad_threshold

        restore = self.restore_clip_check.isChecked()
        if restore != self.config.get("restore_clipboard"):
            changes["restore_clipboard"] = restore

        # 保存变更
        if changes:
            for key, value in changes.items():
                self.config.set(key, value)
            self.settings_changed.emit(changes)

        self.close()

    def _reset_settings(self):
        """恢复默认设置"""
        reply = QMessageBox.question(
            self,
            "确认",
            "确定要恢复所有设置为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.reset()
            self._load_settings()

    def _reload_model(self):
        """重新加载模型（信号由主程序处理）"""
        self.settings_changed.emit({"_reload_model": True})

    def _unload_model(self):
        """卸载模型（信号由主程序处理）"""
        self.settings_changed.emit({"_unload_model": True})
