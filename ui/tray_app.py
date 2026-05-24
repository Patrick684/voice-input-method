"""系统托盘应用模块 - 使用 pystray + Pillow 实现"""

import threading
from enum import Enum
from typing import Callable, Optional

from PIL import Image, ImageDraw
import pystray


class AppState(Enum):
    """应用状态枚举"""

    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    DISABLED = "disabled"


class TrayApp:
    """系统托盘应用，管理托盘图标和菜单"""

    # 图标颜色配置 (R, G, B)
    COLORS = {
        AppState.IDLE: (100, 200, 100),  # 绿色 - 空闲
        AppState.RECORDING: (220, 50, 50),  # 红色 - 录音中
        AppState.PROCESSING: (50, 150, 220),  # 蓝色 - 识别中
        AppState.DISABLED: (150, 150, 150),  # 灰色 - 已禁用
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
        self._hotkey = hotkey
        self._state = AppState.IDLE
        self._service_active = True

        self._on_settings = on_settings
        self._on_quit = on_quit
        self._on_toggle = on_toggle

        self._icon: Optional[pystray.Icon] = None
        self._status_text = "状态: 就绪"

    def _create_icon(self, state: AppState) -> Image.Image:
        """使用 Pillow 生成指定状态的图标"""
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        color = self.COLORS.get(state, self.COLORS[AppState.IDLE])

        # 绘制圆形背景
        margin = 4
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=color + (255,),
        )

        # 绘制白色麦克风图标
        white = (255, 255, 255, 255)
        cx, cy = size // 2, size // 2

        if state == AppState.RECORDING:
            # 录音状态 - 实心圆点
            r = 10
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=white)
        elif state == AppState.PROCESSING:
            # 识别中 - 音波线条
            draw.rectangle([cx - 2, cy - 16, cx + 2, cy + 16], fill=white)
            draw.rectangle([cx - 10, cy - 10, cx - 6, cy + 10], fill=white)
            draw.rectangle([cx + 6, cy - 10, cx + 10, cy + 10], fill=white)
        else:
            # 空闲/禁用 - 麦克风形状
            draw.ellipse([cx - 7, cy - 14, cx + 7, cy + 4], fill=white)
            draw.rectangle([cx - 2, cy + 4, cx + 2, cy + 12], fill=white)
            draw.rectangle([cx - 8, cy + 12, cx + 8, cy + 16], fill=white)

        return img

    def _build_menu(self) -> pystray.Menu:
        """构建右键菜单"""
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: self._status_text,
                None,
                enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "启动服务" if not self._service_active else "停止服务",
                self._on_toggle_service,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "设置...",
                self._handle_settings,
                default=True,  # 双击触发此项
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "退出",
                self._handle_quit,
            ),
        )

    def _handle_settings(self, icon, item):
        """处理设置菜单点击"""
        if self._on_settings:
            self._on_settings()

    def _handle_quit(self, icon, item):
        """处理退出菜单点击"""
        if self._on_quit:
            self._on_quit()

    def _on_toggle_service(self, icon, item):
        """切换服务状态"""
        self._service_active = not self._service_active
        if not self._service_active:
            self.set_state(AppState.DISABLED)
        else:
            self.set_state(AppState.IDLE)
        if self._on_toggle:
            self._on_toggle(self._service_active)

    def setup(self):
        """初始化并显示托盘图标"""
        icon_image = self._create_icon(self._state)
        tooltip = self.TOOLTIPS.get(self._state, "").format(hotkey=self._hotkey)

        self._icon = pystray.Icon(
            name="voice_input",
            icon=icon_image,
            title=tooltip,
            menu=self._build_menu(),
        )

        # pystray.run() 会阻塞，所以在后台线程运行
        threading.Thread(target=self._icon.run, daemon=True).start()

    def set_state(self, state: AppState):
        """设置应用状态（更新图标和提示）"""
        self._state = state

        if self._icon:
            self._icon.icon = self._create_icon(state)
            tooltip = self.TOOLTIPS.get(state, "")
            if state == AppState.IDLE:
                tooltip = tooltip.format(hotkey=self._hotkey)
            self._icon.title = tooltip

        # 更新状态文本
        status_map = {
            AppState.IDLE: "状态: 就绪",
            AppState.RECORDING: "状态: 录音中...",
            AppState.PROCESSING: "状态: 识别中...",
            AppState.DISABLED: "状态: 已停止",
        }
        self._status_text = status_map.get(state, "状态: 未知")

    def show_notification(self, title: str, message: str, duration: int = 3000):
        """显示系统通知"""
        if self._icon:
            self._icon.notify(message, title)

    def update_hotkey_display(self, hotkey: str):
        """更新快捷键显示文本"""
        self._hotkey = hotkey
        if self._icon and self._state == AppState.IDLE:
            self._icon.title = self.TOOLTIPS[AppState.IDLE].format(hotkey=hotkey)

    def cleanup(self):
        """清理托盘图标"""
        if self._icon:
            self._icon.stop()
            self._icon = None
