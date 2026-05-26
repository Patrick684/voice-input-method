"""流式 VAD 检测器 - 在录音过程中实时检测句子边界

通过能量阈值检测静音段，当静音持续超过设定时间时判定一个句子结束，
将累积的音频送入识别引擎，实现边说边识别的流式体验。
"""

import logging
import numpy as np
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class StreamVAD:
    """流式 VAD 检测器，在录音过程中实时检测句子边界"""

    # 默认参数
    DEFAULT_SILENCE_THRESHOLD = 0.01  # RMS 能量阈值，低于此视为静音
    DEFAULT_SILENCE_DURATION = 0.8  # 连续静音时长（秒）才判定句子结束
    DEFAULT_MIN_SENTENCE_DURATION = 0.5  # 最短句子时长（秒），太短的丢弃

    def __init__(
        self,
        sample_rate: int = 16000,
        silence_threshold: float = DEFAULT_SILENCE_THRESHOLD,
        silence_duration: float = DEFAULT_SILENCE_DURATION,
        min_sentence_duration: float = DEFAULT_MIN_SENTENCE_DURATION,
        on_sentence_end: Optional[Callable[[np.ndarray], None]] = None,
    ):
        """
        初始化流式 VAD 检测器

        Args:
            sample_rate: 音频采样率 (Hz)
            silence_threshold: 静音判定阈值 (RMS 值)
            silence_duration: 连续静音多久判定句子结束 (秒)
            min_sentence_duration: 最短句子时长 (秒)，太短的段丢弃
            on_sentence_end: 句子结束回调，参数为该句的完整音频 (np.ndarray)
        """
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.min_sentence_duration = min_sentence_duration
        self.on_sentence_end = on_sentence_end

        # 内部状态
        self._buffer: list[np.ndarray] = []
        self._buffer_samples = 0  # 缓冲区总采样点数
        self._silence_samples = 0  # 连续静音采样计数
        self._has_voice = False  # 当前句子是否包含过语音

        # 预计算阈值（将秒数转换为采样点数）
        self._silence_threshold_samples = int(silence_duration * sample_rate)
        self._min_sentence_samples = int(min_sentence_duration * sample_rate)

    def feed(self, chunk: np.ndarray):
        """
        接收一个音频 chunk，检测是否出现句子边界

        在音频回调线程中调用，需要尽量轻量。

        Args:
            chunk: 单声道 float32 音频数据
        """
        # 计算 RMS 能量
        rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))

        is_silence = rms < self.silence_threshold

        if is_silence:
            self._silence_samples += len(chunk)

            # 静音持续超过阈值 -> 句子结束
            if (
                self._has_voice
                and self._silence_samples >= self._silence_threshold_samples
            ):
                self._emit_sentence()
        else:
            # 检测到语音，重置静音计数
            self._silence_samples = 0
            self._has_voice = True

        # 将 chunk 加入缓冲区
        self._buffer.append(chunk)
        self._buffer_samples += len(chunk)

    def _emit_sentence(self):
        """发射当前句子（拼接缓冲区音频并触发回调）"""
        if not self._buffer or self._buffer_samples < self._min_sentence_samples:
            # 太短的段，丢弃
            logger.debug(
                f"StreamVAD: 丢弃过短片段 ({self._buffer_samples / self.sample_rate:.2f}s)"
            )
            self._clear_buffer()
            return

        # 拼接音频
        sentence_audio = np.concatenate(self._buffer)
        duration = len(sentence_audio) / self.sample_rate
        logger.info(f"StreamVAD: 检测到句子边界 ({duration:.1f}s)")

        # 清空缓冲区
        self._clear_buffer()

        # 触发回调
        if self.on_sentence_end:
            try:
                self.on_sentence_end(sentence_audio)
            except Exception as e:
                logger.error(f"StreamVAD: 句子回调异常: {e}")

    def _clear_buffer(self):
        """清空缓冲区和状态"""
        self._buffer = []
        self._buffer_samples = 0
        self._silence_samples = 0
        self._has_voice = False

    def flush(self) -> Optional[np.ndarray]:
        """
        录音结束时调用，返回缓冲区中剩余音频（尾句）

        Returns:
            尾句音频数据，如果缓冲区为空或太短则返回 None
        """
        if not self._buffer or not self._has_voice:
            self._clear_buffer()
            return None

        if self._buffer_samples < self._min_sentence_samples:
            logger.debug(
                f"StreamVAD: 尾句过短，丢弃 ({self._buffer_samples / self.sample_rate:.2f}s)"
            )
            self._clear_buffer()
            return None

        sentence_audio = np.concatenate(self._buffer)
        duration = len(sentence_audio) / self.sample_rate
        logger.info(f"StreamVAD: flush 尾句 ({duration:.1f}s)")

        self._clear_buffer()
        return sentence_audio

    def reset(self):
        """重置状态，为下一次录音准备"""
        self._clear_buffer()

    def update_params(
        self,
        silence_duration: Optional[float] = None,
        silence_threshold: Optional[float] = None,
    ):
        """
        动态更新 VAD 参数（用于设置窗口实时调整）

        Args:
            silence_duration: 新的静音切句时长 (秒)
            silence_threshold: 新的静音阈值 (RMS)
        """
        if silence_duration is not None:
            self.silence_duration = silence_duration
            self._silence_threshold_samples = int(silence_duration * self.sample_rate)

        if silence_threshold is not None:
            self.silence_threshold = silence_threshold
