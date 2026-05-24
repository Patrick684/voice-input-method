"""系统托盘应用模块 - 提供系统托盘图标和菜单"""

import io
from enum import Enum
from typing import Callable, Optional

from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QStyle,
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PyQt6.QtCore import Qt, pyqtSignal, QObject


class AppState(Enum):
    """应用状态枚举"""
    IDLE = "idle"          # 空闲
    RECORDING = "recording"  # 录音中
    PROCESSING = "processing"  # 识别中
    DISABLED = "disabled"  # 已禁用


class TrayApp(QObject):
    """系统托盘应用，管理托盘图标和菜单"""

    # 信号定义（用于跨线程通信）
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    toggle_service = pyqtSignal(bool)

    # 图标颜色配置
    COLORS = {
        AppState.IDLE: QColor(100, 200, 100),       # 绿色 - 空闲
        AppState.RECORDING: QColor(220, 50, 50),     # 红色 - 录音中
        AppState.PROCESSING: QColor(50, 150, 220),   # 蓝色 - 识别中
        AppState.DISABLED: QColor(150, 150, 150),    # 灰色 - 已禁用
    }

    TOOLTIPS = {
        AppState.IDLE: "语音输入法 - 就绪 (按住 {hotkey} 说话)",
        AppState.RECORDING: "语音输入法 - 录音中...",
        AppState.PROCESSING: "语音输入法 - 识别中...",
        AppState.DISABLED: "语音输入法 - 已停止",
    }

    def __init__(
        self,
        hotkey: str = "右Alt",
        on_settings: Optional[Callable] = None,
        on_quit: Optional[Callable] = None,
        on_toggle: Optional[Callable[[bool], None]] = None,
    ):
        super().__init__()
        self._hotkey = hotkey
        self._state = AppState.IDLE
        self._service_active = True

        # 连接信号
        if on_settings:
            self.settings_requested.connect(on_settings)
        if on_quit:
            self.quit_requested.connect(on_quit)
        if on_toggle:
            self.toggle_service.connect(on_toggle)

        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._toggle_action: Optional[QAction] = None

    def _create_icon(self, state: AppState) -> QIcon:
        """生成指定状态的图标"""
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = self.COLORS.get(state, self.COLORS[AppState.IDLE])

        # 绘制圆形背景
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)

        # 绘制麦克风图标
        painter.setPen(QColor(255, 255, 255))
        painter.setBrush(QColor(255, 255, 255))

        if state == AppState.RECORDING:
            # 录音状态 - 绘制实心圆点
            painter.drawEllipse(10, 10, 12, 12)
        elif state == AppState.PROCESSING:
            # 识别中 - 绘制旋转线条
            painter.drawRect(12, 6, 3, 20)
            painter.drawRect(17, 10, 3, 12)
            painter.drawRect(7, 10, 3, 12)
        else:
            # 空闲/禁用 - 绘制麦克风形状
            painter.drawEllipse(11, 5, 10, 14)
            painter.drawRect(14, 19, 4, 5)
            painter.drawRect(10, 24, 12, 2)

        painter.end()
        return QIcon(pixmap)

    def setup(self):
        """初始化并显示托盘图标"""
        self._tray_icon = QSystemTrayIcon()
        self._update_icon()

        # 创建右键菜单
        self._menu = QMenu()

        # 状态显示（不可点击）
        status_action = self._menu.addAction("状态: 就绪")
        status_action.setEnabled(False)
        self._menu.addSeparator()

        # 开始/停止服务
        self._toggle_action = self._menu.addAction("停止服务")
        self._toggle_action.triggered.connect(self._on_toggle_service)

        self._menu.addSeparator()

        # 设置
        settings_action = self._menu.addAction("设置...")
        settings_action.triggered.connect(self.settings_requested.emit)

        self._menu.addSeparator()

        # 退出
        quit_action = self._menu.addAction("退出")
        quit_action.triggered.connect(self.quit_requested.emit)

        self._tray_icon.setContextMenu(self._menu)
        self._tray_icon.show()

        # 双击托盘图标打开设置
        self._tray_icon.activated.connect(self._on_activated)

    def _update_icon(self):
        """更新托盘图标"""
        if self._tray_icon:
            icon = self._create_icon(self._state)
            self._tray_icon.setIcon(icon)

            tooltip = self.TOOLTIPS.get(self._state, "")
            if self._state == AppState.IDLE:
                tooltip = tooltip.format(hotkey=self._hotkey)
            self._tray_icon.setToolTip(tooltip)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """托盘图标激活事件"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.settings_requested.emit()

    def _on_toggle_service(self):
        """切换服务状态"""
        self._service_active = not self._service_active
        self._toggle_action.setText(
            "停止服务" if self._service_active else "启动服务"
        )
        if not self._service_active:
            self.set_state(AppState.DISABLED)
        else:
            self.set_state(AppState.IDLE)
        self.toggle_service.emit(self._service_active)

    def set_state(self, state: AppState):
        """设置应用状态（更新图标和提示）"""
        self._state = state
        self._update_icon()

        # 更新菜单中的状态文本
        if self._menu:
            status_texts = {
                AppState.IDLE: "状态: 就绪",
                AppState.RECORDING: "状态: 录音中...",
                AppState.PROCESSING: "状态: 识别中...",
                AppState.DISABLED: "状态: 已停止",
            }
            actions = self._menu.actions()
            if actions:
                actions[0].setText(status_texts.get(state, "状态: 未知"))

    def show_notification(self, title: str, message: str, duration: int = 3000):
        """显示系统通知"""
        if self._tray_icon and self._tray_icon.supportsMessages():
            self._tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                duration,
            )

    def update_hotkey_display(self, hotkey: str):
        """更新快捷键显示文本"""
        self._hotkey = hotkey
        self._update_icon()

    def cleanup(self):
        """清理托盘图标"""
        if self._tray_icon:
            self._tray_icon.hide()
            self._tray_icon.deleteLater()
