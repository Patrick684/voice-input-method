"""全局快捷键管理模块 - 使用 keyboard 库监听全局按键"""

import time
import threading
import winsound
from typing import Callable, Optional

import keyboard


class HotkeyManager:
    """全局快捷键管理器，支持按住录音和切换录音两种模式"""

    # 提示音频率 (Hz) 和时长 (ms)
    BEEP_START_FREQ = 880
    BEEP_START_DURATION = 100
    BEEP_STOP_FREQ = 440
    BEEP_STOP_DURATION = 100

    def __init__(
        self,
        hotkey: str = "right alt",
        mode: str = "hold",
        on_start: Optional[Callable[[], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        """
        初始化快捷键管理器

        Args:
            hotkey: 快捷键名称 (如 "right alt", "f4" 等)
            mode: 触发模式 "hold"(按住) 或 "toggle"(切换)
            on_start: 开始录音回调
            on_stop: 停止录音回调
            on_cancel: 取消录音回调
        """
        self.hotkey = hotkey
        self.mode = mode
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_cancel = on_cancel

        self._active = False
        self._recording = False
        self._press_time: float = 0
        self._registered = False

        # 防抖设置
        self._min_hold_duration = 0.15  # 最短按住时间（秒），防止误触
        self._debounce_lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    def register(self):
        """注册全局快捷键"""
        if self._registered:
            return

        if self.mode == "hold":
            keyboard.on_press_key(self.hotkey, self._on_key_press)
            keyboard.on_release_key(self.hotkey, self._on_key_release)
        else:  # toggle 模式
            keyboard.add_hotkey(self.hotkey, self._on_toggle)

        self._registered = True
        self._active = True

    def unregister(self):
        """注销全局快捷键"""
        if not self._registered:
            return

        try:
            if self.mode == "hold":
                keyboard.unhook_all()
            else:
                keyboard.remove_hotkey(self.hotkey)
        except Exception:
            pass

        self._registered = False
        self._active = False

    def _on_key_press(self, event):
        """按住模式 - 按键按下处理"""
        if not self._active:
            return

        with self._debounce_lock:
            if self._recording:
                return

            self._press_time = time.time()
            self._recording = True

        # 播放开始提示音
        self._play_beep(self.BEEP_START_FREQ, self.BEEP_START_DURATION)

        if self.on_start:
            self.on_start()

    def _on_key_release(self, event):
        """按住模式 - 按键释放处理"""
        if not self._active or not self._recording:
            return

        with self._debounce_lock:
            hold_duration = time.time() - self._press_time

            if hold_duration < self._min_hold_duration:
                # 按住时间太短，取消录音
                self._recording = False
                if self.on_cancel:
                    self.on_cancel()
                return

            self._recording = False

        # 播放停止提示音
        self._play_beep(self.BEEP_STOP_FREQ, self.BEEP_STOP_DURATION)

        if self.on_stop:
            self.on_stop()

    def _on_toggle(self):
        """切换模式 - 按键切换处理"""
        if not self._active:
            return

        if self._recording:
            self._recording = False
            self._play_beep(self.BEEP_STOP_FREQ, self.BEEP_STOP_DURATION)
            if self.on_stop:
                self.on_stop()
        else:
            self._recording = True
            self._play_beep(self.BEEP_START_FREQ, self.BEEP_START_DURATION)
            if self.on_start:
                self.on_start()

    def cancel_recording(self):
        """手动取消当前录音"""
        if self._recording:
            self._recording = False
            if self.on_cancel:
                self.on_cancel()

    @staticmethod
    def _play_beep(frequency: int, duration: int):
        """播放提示音（异步）"""
        try:
            # 使用线程避免阻塞
            threading.Thread(
                target=winsound.Beep,
                args=(frequency, duration),
                daemon=True,
            ).start()
        except Exception:
            pass

    def change_hotkey(self, new_hotkey: str, new_mode: Optional[str] = None):
        """
        更改快捷键

        Args:
            new_hotkey: 新的快捷键
            new_mode: 新的触发模式（可选）
        """
        was_registered = self._registered
        if was_registered:
            self.unregister()

        self.hotkey = new_hotkey
        if new_mode:
            self.mode = new_mode

        if was_registered:
            self.register()

    def set_active(self, active: bool):
        """设置快捷键是否激活"""
        self._active = active
