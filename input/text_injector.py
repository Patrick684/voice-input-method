"""文本输入模块 - 通过剪贴板 + 模拟按键实现文本输入"""

import time
import threading

import pyperclip
import keyboard


class TextInjector:
    """文本输入器，通过剪贴板粘贴方式将文本输入到当前焦点窗口"""

    def __init__(self, restore_clipboard: bool = True):
        """
        初始化文本输入器

        Args:
            restore_clipboard: 输入完成后是否恢复原始剪贴板内容
        """
        self.restore_clipboard = restore_clipboard
        self._lock = threading.Lock()

    def inject_text(self, text: str) -> bool:
        """
        将文本输入到当前焦点窗口

        通过保存剪贴板 -> 设置新内容 -> 模拟粘贴 -> 恢复剪贴板实现

        Args:
            text: 要输入的文本

        Returns:
            True 如果输入成功
        """
        if not text or not text.strip():
            return False

        with self._lock:
            # 保存当前剪贴板内容
            original_clipboard = None
            if self.restore_clipboard:
                try:
                    original_clipboard = pyperclip.paste()
                except Exception:
                    original_clipboard = None

            try:
                # 将识别文本写入剪贴板
                pyperclip.copy(text)

                # 等待剪贴板内容就绪
                time.sleep(0.05)

                # 模拟 Ctrl+V 粘贴
                keyboard.send("ctrl+v")

                # 等待粘贴操作完成
                time.sleep(0.1)

                return True

            except Exception as e:
                print(f"文本输入失败: {e}")
                return False

            finally:
                # 恢复原始剪贴板内容
                if self.restore_clipboard and original_clipboard is not None:
                    try:
                        # 延迟恢复，确保粘贴操作已完成
                        time.sleep(0.2)
                        pyperclip.copy(original_clipboard)
                    except Exception:
                        pass

    def inject_text_with_delay(self, text: str, delay: float = 0.5):
        """
        延迟后输入文本（用于切换窗口焦点等场景）

        Args:
            text: 要输入的文本
            delay: 延迟秒数
        """

        def _delayed_inject():
            time.sleep(delay)
            self.inject_text(text)

        thread = threading.Thread(target=_delayed_inject, daemon=True)
        thread.start()
        return thread
