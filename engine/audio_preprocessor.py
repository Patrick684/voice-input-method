"""音频预处理模块 - 提升 Whisper 输入音频的信噪比

提供高通滤波和简单降噪功能，在音频送入 Whisper 之前进行预处理，
去除低频噪音（空调、风扇等）和稳态底噪，提升识别精度。
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


class AudioPreprocessor:
    """音频预处理器：高通滤波 + 谱减降噪"""

    # 默认参数
    DEFAULT_HIGH_PASS_FREQ = 80  # 高通滤波截止频率 (Hz)
    DEFAULT_FILTER_ORDER = 4  # 滤波器阶数
    DEFAULT_NOISE_DURATION = 0.5  # 噪声估算时长 (秒)
    DEFAULT_NOISE_REDUCTION_STRENGTH = 1.0  # 降噪强度 (0.0~2.0)

    def __init__(
        self,
        sample_rate: int = 16000,
        high_pass_freq: float = DEFAULT_HIGH_PASS_FREQ,
        filter_order: int = DEFAULT_FILTER_ORDER,
        noise_reduction: bool = True,
        noise_reduction_strength: float = DEFAULT_NOISE_REDUCTION_STRENGTH,
        enabled: bool = True,
    ):
        """
        初始化音频预处理器

        Args:
            sample_rate: 音频采样率 (Hz)
            high_pass_freq: 高通滤波截止频率 (Hz)，去除低于此频率的噪音
            filter_order: 滤波器阶数（越高滚降越陡，但计算量更大）
            noise_reduction: 是否启用谱减降噪
            noise_reduction_strength: 降噪强度 (0.0~2.0)，1.0 为标准降噪
            enabled: 是否启用预处理
        """
        self._sample_rate = sample_rate
        self._high_pass_freq = high_pass_freq
        self._filter_order = filter_order
        self._noise_reduction = noise_reduction
        self._noise_reduction_strength = noise_reduction_strength
        self._enabled = enabled

        # 预计算滤波器系数（惰性加载）
        self._sos = None

    @property
    def enabled(self) -> bool:
        """预处理是否启用"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        对音频执行预处理流水线

        流程: 高通滤波 -> 谱减降噪

        Args:
            audio: 输入音频 (float32, 16kHz, 单声道)

        Returns:
            预处理后的音频
        """
        if not self._enabled:
            return audio

        if len(audio) < 160:  # 少于 10ms 不处理
            return audio

        original_dtype = audio.dtype
        audio = audio.astype(np.float64)  # scipy 内部用 float64 精度更好

        # 高通滤波
        audio = self._apply_high_pass_filter(audio)

        # 谱减降噪
        if self._noise_reduction:
            audio = self._apply_spectral_subtraction(audio)

        return audio.astype(original_dtype)

    def _get_filter_sos(self):
        """惰性获取高通滤波器系数（缓存）"""
        if self._sos is not None:
            return self._sos

        try:
            from scipy.signal import butter

            self._sos = butter(
                self._filter_order,
                self._high_pass_freq,
                btype="high",
                fs=self._sample_rate,
                output="sos",
            )
            logger.info(
                f"高通滤波器已初始化: {self._high_pass_freq}Hz, "
                f"阶数={self._filter_order}"
            )
            return self._sos
        except ImportError:
            logger.warning("scipy 未安装，高通滤波不可用")
            return None

    def _apply_high_pass_filter(self, audio: np.ndarray) -> np.ndarray:
        """
        应用高通滤波，去除低频噪音

        使用 Butterworth 高通滤波器，去除 80Hz 以下的低频成分，
        包括空调嗡鸣、风扇噪音、电磁干扰等。

        Args:
            audio: 输入音频 (float64)

        Returns:
            滤波后的音频
        """
        sos = self._get_filter_sos()
        if sos is None:
            return audio

        try:
            from scipy.signal import sosfilt

            # 双向滤波（零相位），避免引入相位延迟
            filtered = sosfilt(sos, audio)
            # 反向再滤一次，实现零相位
            filtered = sosfilt(sos, filtered[::-1])[::-1]

            return filtered.astype(np.float64)
        except Exception as e:
            logger.warning(f"高通滤波失败: {e}")
            return audio

    def _apply_spectral_subtraction(self, audio: np.ndarray) -> np.ndarray:
        """
        简单谱减降噪

        利用音频前 noise_duration 秒估算噪声功率谱，
        然后从整个音频中减去噪声谱，恢复干净语音。

        适用于稳态噪音（如空调、风扇），对非稳态噪音效果有限。

        Args:
            audio: 输入音频 (float64)

        Returns:
            降噪后的音频
        """
        n_samples = len(audio)
        if n_samples < self._sample_rate:
            # 音频太短（<1秒），无法准确估算噪声，跳过降噪
            return audio

        try:
            # 估算噪声段（取前 noise_duration 秒）
            noise_samples = int(
                self._noise_reduction_strength * self._sample_rate * 0.5
            )
            noise_samples = min(noise_samples, n_samples // 4)  # 最多用 1/4 的音频

            if noise_samples < 160:
                return audio

            noise_segment = audio[:noise_samples]

            # STFT 参数
            frame_size = 512  # 32ms @ 16kHz
            hop_size = frame_size // 2

            # 计算噪声功率谱
            noise_spectrum = self._estimate_noise_spectrum(
                noise_segment, frame_size, hop_size
            )

            # 对整个音频做 STFT
            stft_matrix = self._stft(audio, frame_size, hop_size)

            # 谱减
            magnitude = np.abs(stft_matrix)
            phase = np.angle(stft_matrix)

            # 减去噪声谱（带过减因子防止音乐噪声）
            alpha = max(1.0, self._noise_reduction_strength)  # 过减因子
            beta = 0.02  # 谱底限（防止负值）

            clean_magnitude = magnitude - alpha * noise_spectrum[:, np.newaxis]
            clean_magnitude = np.maximum(clean_magnitude, beta * magnitude)

            # 重建
            clean_stft = clean_magnitude * np.exp(1j * phase)
            clean_audio = self._istft(clean_stft, frame_size, hop_size, n_samples)

            return clean_audio

        except Exception as e:
            logger.warning(f"谱减降噪失败: {e}")
            return audio

    @staticmethod
    def _estimate_noise_spectrum(
        noise: np.ndarray, frame_size: int, hop_size: int
    ) -> np.ndarray:
        """
        估算噪声的平均功率谱

        Args:
            noise: 噪声段音频
            frame_size: STFT 帧大小
            hop_size: STFT 帧移

        Returns:
            平均噪声功率谱 (n_freq_bins,)
        """
        n_frames = max(1, (len(noise) - frame_size) // hop_size + 1)
        window = np.hanning(frame_size)

        spectra = []
        for i in range(n_frames):
            start = i * hop_size
            end = start + frame_size
            if end > len(noise):
                break
            frame = noise[start:end] * window
            spectrum = np.abs(np.fft.rfft(frame))
            spectra.append(spectrum)

        if not spectra:
            return np.zeros(frame_size // 2 + 1)

        # 平均功率谱
        return np.mean(np.array(spectra), axis=0)

    @staticmethod
    def _stft(signal: np.ndarray, frame_size: int, hop_size: int) -> np.ndarray:
        """
        短时傅里叶变换 (STFT)

        Args:
            signal: 输入信号
            frame_size: 帧大小
            hop_size: 帧移

        Returns:
            STFT 矩阵 (n_freq_bins, n_frames)
        """
        window = np.hanning(frame_size)
        n_frames = max(1, (len(signal) - frame_size) // hop_size + 1)

        # 零填充
        padded = np.pad(signal, (0, frame_size), mode="constant")

        stft_matrix = np.zeros((frame_size // 2 + 1, n_frames), dtype=complex)
        for i in range(n_frames):
            start = i * hop_size
            frame = padded[start : start + frame_size] * window
            stft_matrix[:, i] = np.fft.rfft(frame)

        return stft_matrix

    @staticmethod
    def _istft(
        stft_matrix: np.ndarray,
        frame_size: int,
        hop_size: int,
        original_length: int,
    ) -> np.ndarray:
        """
        逆短时傅里叶变换 (ISTFT)，使用 overlap-add 重建

        Args:
            stft_matrix: STFT 矩阵
            frame_size: 帧大小
            hop_size: 帧移
            original_length: 原始信号长度

        Returns:
            重建的信号
        """
        window = np.hanning(frame_size)
        n_frames = stft_matrix.shape[1]

        # 输出缓冲
        output = np.zeros(original_length + frame_size)
        window_sum = np.zeros(original_length + frame_size)

        for i in range(n_frames):
            start = i * hop_size
            frame = np.fft.irfft(stft_matrix[:, i])[:frame_size]
            output[start : start + frame_size] += frame * window
            window_sum[start : start + frame_size] += window**2

        # 除以窗口函数的平方和（补偿重叠）
        nonzero = window_sum > 1e-8
        output[nonzero] /= window_sum[nonzero]

        return output[:original_length]
