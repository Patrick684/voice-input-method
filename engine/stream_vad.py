"""流式 VAD 检测器 - 基于 Silero VAD 的神经网络语音活动检测

通过 Silero VAD 模型检测语音活动段，当语音概率连续低于阈值超过设定时间时
判定一个句子结束，将累积的音频送入识别引擎，实现边说边识别的流式体验。
RMS 能量检测作为后备方案，在 Silero 模型加载失败时自动降级。
"""

import logging
import numpy as np
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class StreamVAD:
    """流式 VAD 检测器，支持 Silero VAD 神经网络模型 + RMS 后备"""

    # 默认参数
    DEFAULT_SILENCE_THRESHOLD = 0.015  # RMS 后备阈值（自适应时会覆盖）
    DEFAULT_SPEECH_PROB_THRESHOLD = 0.35  # Silero VAD 语音概率阈值
    DEFAULT_SILENCE_DURATION = 0.8  # 连续静音时长（秒）才判定句子结束
    DEFAULT_MIN_SENTENCE_DURATION = 0.5  # 最短句子时长（秒），太短的丢弃
    NOISE_CALIBRATION_DURATION = 0.5  # 底噪校准采样时长（秒）
    NOISE_THRESHOLD_MULTIPLIER = 3.0  # 自适应阈值 = 底噪RMS × 此倍数

    # Silero VAD 要求 16kHz 时每次输入 512 个采样点（32ms）
    SILERO_WINDOW_SIZE = 512

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
            sample_rate: 音频采样率 (Hz)，Silero VAD 要求 16000
            silence_threshold: RMS 后备静音阈值（自适应底噪时会覆盖）
            silence_duration: 连续静音多久判定句子结束 (秒)
            min_sentence_duration: 最短句子时长 (秒)，太短的段丢弃
            on_sentence_end: 句子结束回调，参数为该句的完整音频 (np.ndarray)
        """
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.speech_prob_threshold = self.DEFAULT_SPEECH_PROB_THRESHOLD
        self.silence_duration = silence_duration
        self.min_sentence_duration = min_sentence_duration
        self.on_sentence_end = on_sentence_end

        # 内部状态
        self._buffer: list[np.ndarray] = []
        self._buffer_samples = 0  # 缓冲区总采样点数
        self._silence_samples = 0  # 连续静音采样计数
        self._has_voice = False  # 当前句子是否包含过语音
        self._use_silero = False  # 是否使用 Silero VAD
        self._silero_model = None
        self._silero_utils = None
        self._silero_h = None  # Silero VAD 隐藏状态
        self._silero_sr = None  # Silero VAD 采样率张量
        self._leftover: Optional[np.ndarray] = None  # feed 时不够一个窗口的残余

        # 底噪校准状态
        self._noise_calibration = True  # 是否正在校准底噪
        self._noise_samples: list[np.ndarray] = []
        self._noise_samples_count = 0
        self._noise_calibration_target = int(
            self.NOISE_CALIBRATION_DURATION * sample_rate
        )

        # 预计算阈值（将秒数转换为采样点数）
        self._silence_threshold_samples = int(silence_duration * sample_rate)
        self._min_sentence_samples = int(min_sentence_duration * sample_rate)

        # 尝试加载 Silero VAD 模型
        self._load_silero_model()

    def _load_silero_model(self):
        """加载 Silero VAD 模型，失败时降级为 RMS 检测"""
        try:
            import torch

            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                trust_repo=True,
            )
            self._silero_model = model
            self._silero_utils = utils
            self._silero_h = model.reset_states()
            self._silero_sr = torch.tensor(self.sample_rate)
            self._use_silero = True
            logger.info("StreamVAD: Silero VAD 模型加载成功，使用神经网络检测")
        except Exception as e:
            logger.warning(f"StreamVAD: Silero VAD 加载失败 ({e})，降级为 RMS 能量检测")
            self._use_silero = False

    def feed(self, chunk: np.ndarray):
        """
        接收一个音频 chunk，检测是否出现句子边界

        在音频回调线程中调用，需要尽量轻量。

        Args:
            chunk: 单声道 float32 音频数据
        """
        # 底噪校准阶段：收集环境噪音样本
        if self._noise_calibration:
            self._noise_samples.append(chunk)
            self._noise_samples_count += len(chunk)
            if self._noise_samples_count >= self._noise_calibration_target:
                self._finish_noise_calibration()

        if self._use_silero:
            self._feed_silero(chunk)
        else:
            self._feed_rms(chunk)

    def _feed_silero(self, chunk: np.ndarray):
        """使用 Silero VAD 模型检测语音活动"""
        import torch

        # 拼接上次残余 + 当前 chunk
        if self._leftover is not None:
            audio = np.concatenate([self._leftover, chunk])
            self._leftover = None
        else:
            audio = chunk

        # 按 512 采样点窗口处理
        window_size = self.SILERO_WINDOW_SIZE
        total = len(audio)
        pos = 0

        while pos + window_size <= total:
            window = audio[pos : pos + window_size]
            pos += window_size

            # Silero VAD 推理
            tensor = torch.from_numpy(window.astype(np.float32))
            prob = self._silero_model(tensor, self._silero_h, self._silero_sr).item()

            is_speech = prob >= self.speech_prob_threshold

            if is_speech:
                self._silence_samples = 0
                self._has_voice = True
            else:
                self._silence_samples += window_size
                if (
                    self._has_voice
                    and self._silence_samples >= self._silence_threshold_samples
                ):
                    # 句子结束：将全部缓冲（含当前 chunk）拼接后发射
                    self._buffer.append(audio[pos:])  # 剩余部分也放入缓冲
                    self._buffer_samples += len(audio) - pos
                    self._emit_sentence()
                    # 重置 Silero 隐藏状态
                    self._silero_h = self._silero_model.reset_states()
                    return

        # 残余不足一个窗口的数据保存起来
        if pos < total:
            self._leftover = audio[pos:]

        # 将 chunk 加入缓冲区
        self._buffer.append(chunk)
        self._buffer_samples += len(chunk)

    def _feed_rms(self, chunk: np.ndarray):
        """RMS 能量检测后备方案"""
        rms = np.sqrt(np.mean(chunk.astype(np.float64) ** 2))
        is_silence = rms < self.silence_threshold

        if is_silence:
            self._silence_samples += len(chunk)

            if (
                self._has_voice
                and self._silence_samples >= self._silence_threshold_samples
            ):
                self._emit_sentence()
        else:
            self._silence_samples = 0
            self._has_voice = True

        self._buffer.append(chunk)
        self._buffer_samples += len(chunk)

    def _finish_noise_calibration(self):
        """完成底噪校准，自动设置 RMS 阈值"""
        if not self._noise_samples:
            self._noise_calibration = False
            return

        all_noise = np.concatenate(self._noise_samples)
        noise_rms = np.sqrt(np.mean(all_noise.astype(np.float64) ** 2))

        adaptive_threshold = noise_rms * self.NOISE_THRESHOLD_MULTIPLIER
        # 确保阈值在合理范围内 [0.01, 0.1]
        adaptive_threshold = max(0.01, min(0.1, adaptive_threshold))

        logger.info(
            f"StreamVAD: 底噪校准完成 - "
            f"噪音RMS={noise_rms:.4f}, 自适应阈值={adaptive_threshold:.4f}"
        )

        self.silence_threshold = adaptive_threshold
        self._noise_calibration = False
        self._noise_samples = []
        self._noise_samples_count = 0

    def _emit_sentence(self):
        """发射当前句子（拼接缓冲区音频并触发回调）"""
        if not self._buffer or self._buffer_samples < self._min_sentence_samples:
            logger.debug(
                f"StreamVAD: 丢弃过短片段 ({self._buffer_samples / self.sample_rate:.2f}s)"
            )
            self._clear_buffer()
            return

        sentence_audio = np.concatenate(self._buffer)
        duration = len(sentence_audio) / self.sample_rate
        logger.info(f"StreamVAD: 检测到句子边界 ({duration:.1f}s)")

        self._clear_buffer()

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
        self._leftover = None

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
        # 重置底噪校准（每次新录音重新校准）
        self._noise_calibration = True
        self._noise_samples = []
        self._noise_samples_count = 0
        # 重置 Silero 隐藏状态
        if self._use_silero and self._silero_model is not None:
            self._silero_h = self._silero_model.reset_states()

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
