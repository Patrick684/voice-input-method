"""Whisper 语音识别引擎 - 基于 faster-whisper 实现本地语音转文字"""

import threading
import numpy as np
from typing import Callable, Optional
from pathlib import Path


class WhisperEngine:
    """Whisper 语音识别引擎封装"""

    # 支持的模型大小及其特性
    MODEL_INFO = {
        "tiny": {"size_mb": 75, "speed": "最快", "accuracy": "一般"},
        "base": {"size_mb": 150, "speed": "快", "accuracy": "较好"},
        "small": {"size_mb": 500, "speed": "中等", "accuracy": "好"},
        "medium": {"size_mb": 1500, "speed": "较慢", "accuracy": "很好"},
        "large": {"size_mb": 3000, "speed": "慢", "accuracy": "最佳"},
    }

    def __init__(
        self,
        model_size: str = "base",
        compute_type: str = "int8",
        device: str = "cpu",
        cache_dir: Optional[str] = None,
    ):
        """
        初始化 Whisper 引擎

        Args:
            model_size: 模型大小 (tiny/base/small/medium/large)
            compute_type: 计算类型 (int8/float16/float32)
            device: 计算设备 (cpu/cuda)
            cache_dir: 模型缓存目录
        """
        self.model_size = model_size
        self.compute_type = compute_type
        self.device = device
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self._model = None
        self._lock = threading.Lock()
        self._is_processing = False

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._model is not None

    @property
    def is_processing(self) -> bool:
        """是否正在处理音频"""
        return self._is_processing

    def load_model(self, on_progress: Optional[Callable[[str], None]] = None):
        """
        加载 Whisper 模型（首次调用时会自动下载）

        Args:
            on_progress: 进度回调函数
        """
        if self._model is not None:
            return

        if on_progress:
            on_progress(f"正在加载 {self.model_size} 模型...")

        try:
            from faster_whisper import WhisperModel

            download_root = str(self.cache_dir) if self.cache_dir else None

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=download_root,
            )

            if on_progress:
                on_progress("模型加载完成")

        except Exception as e:
            if on_progress:
                on_progress(f"模型加载失败: {e}")
            raise RuntimeError(f"无法加载 Whisper 模型: {e}")

    def unload_model(self):
        """卸载模型以释放内存"""
        with self._lock:
            self._model = None

    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = "zh",
        initial_prompt: Optional[str] = None,
        beam_size: int = 5,
        vad_filter: bool = True,
        vad_threshold: float = 0.5,
    ) -> Optional[str]:
        """
        将音频转换为文字

        Args:
            audio: numpy 数组格式的音频数据 (float32, 16kHz, 单声道)
            language: 语言代码 (zh/en/ja 等)，None 为自动检测
            initial_prompt: 初始提示词（用于热词注入）
            beam_size: 束搜索大小
            vad_filter: 是否启用 VAD 过滤
            vad_threshold: VAD 阈值

        Returns:
            识别出的文字，如果处理失败返回 None
        """
        with self._lock:
            if self._model is None:
                raise RuntimeError("模型未加载，请先调用 load_model()")

            self._is_processing = True

        try:
            # 确保音频格式正确
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # 检查音频是否为空或太短
            if len(audio) < 1600:  # 少于 0.1 秒
                return None

            # 执行识别
            segments, info = self._model.transcribe(
                audio,
                language=language,
                initial_prompt=initial_prompt,
                beam_size=beam_size,
                vad_filter=vad_filter,
                vad_parameters={"threshold": vad_threshold} if vad_filter else None,
                without_timestamps=True,
            )

            # 拼接所有片段
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text)

            text = "".join(text_parts).strip()
            return text if text else None

        except Exception as e:
            print(f"语音识别错误: {e}")
            return None

        finally:
            with self._lock:
                self._is_processing = False

    def transcribe_async(
        self,
        audio: np.ndarray,
        on_complete: Callable[[Optional[str]], None],
        **kwargs,
    ):
        """
        异步执行语音识别

        Args:
            audio: 音频数据
            on_complete: 完成回调，参数为识别结果
            **kwargs: 传递给 transcribe 的其他参数
        """
        def _worker():
            try:
                result = self.transcribe(audio, **kwargs)
                on_complete(result)
            except Exception as e:
                print(f"异步识别错误: {e}")
                on_complete(None)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return thread

    def change_model(self, model_size: str):
        """
        切换模型大小

        Args:
            model_size: 新的模型大小
        """
        if model_size == self.model_size and self._model is not None:
            return

        self.unload_model()
        self.model_size = model_size
