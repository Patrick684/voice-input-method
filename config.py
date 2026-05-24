"""语音输入法配置管理模块"""

import json
import os
from pathlib import Path
from typing import Any, Optional


class Config:
    """应用配置管理器，支持持久化存储"""

    DEFAULT_CONFIG = {
        # 快捷键设置
        "hotkey": "right alt",
        "hotkey_mode": "hold",  # hold: 按住录音, toggle: 切换录音

        # 语音识别设置
        "model_size": "base",  # tiny, base, small, medium, large
        "language": "zh",  # zh: 中文, en: 英文, None: 自动检测
        "beam_size": 5,
        "compute_type": "int8",  # int8, float16, float32

        # 音频设置
        "sample_rate": 16000,
        "audio_device": None,  # None 表示使用默认设备

        # 文本输入设置
        "input_method": "clipboard",  # clipboard: 剪贴板粘贴
        "restore_clipboard": True,  # 恢复原始剪贴板内容

        # UI 设置
        "start_minimized": True,
        "auto_start": False,
        "show_notifications": True,

        # 热词设置
        "hotwords": [],
        "hotword_weight": 1.5,

        # 标点优化
        "punctuation_optimization": True,
        "auto_paragraph": False,

        # Emoji 设置
        "emoji_enabled": True,
        "emoji_density": "medium",  # low, medium, high

        # 高级设置
        "vad_filter": True,
        "vad_threshold": 0.5,
    }

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.join(
                os.environ.get("APPDATA", os.path.expanduser("~")),
                "VoiceInput"
            )
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self._config = dict(self.DEFAULT_CONFIG)
        self._load()

    def _load(self):
        """从文件加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._config.update(saved)
            except (json.JSONDecodeError, IOError):
                pass

    def save(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"保存配置失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        """设置配置项并自动保存"""
        self._config[key] = value
        self.save()

    def reset(self, key: Optional[str] = None):
        """重置配置项为默认值"""
        if key:
            if key in self.DEFAULT_CONFIG:
                self._config[key] = self.DEFAULT_CONFIG[key]
        else:
            self._config = dict(self.DEFAULT_CONFIG)
        self.save()

    @property
    def model_cache_dir(self) -> Path:
        """模型缓存目录"""
        cache_dir = self.config_dir / "models"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir

    @property
    def hotword_file(self) -> Path:
        """热词文件路径"""
        return self.config_dir / "hotwords.json"
