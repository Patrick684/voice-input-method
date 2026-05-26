"""文件转写引擎 - 支持音频/视频文件转文字并输出带时间戳的字幕"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionSegment:
    """单条转写片段（含时间戳）"""

    start: float  # 开始时间（秒）
    end: float  # 结束时间（秒）
    text: str  # 文本内容


class FileTranscriber:
    """文件转写引擎，支持音频和视频文件"""

    # 支持的音频格式
    SUPPORTED_AUDIO = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".wma", ".aac"}
    # 支持的视频格式
    SUPPORTED_VIDEO = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"}
    # 所有支持格式
    SUPPORTED_FORMATS = SUPPORTED_AUDIO | SUPPORTED_VIDEO

    # Whisper 模型对应的引导提示词
    LANGUAGE_PROMPTS = {
        "zh": "以下是普通话的句子，请使用简体中文转录，注意正确使用逗号、句号等标点符号。",
        "en": "The following is English speech. Use proper punctuation including commas and periods.",
        "ja": "以下は日本語の音声です。",
    }

    def __init__(
        self,
        model_size: str = "small",
        cache_dir: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        """
        初始化文件转写引擎

        Args:
            model_size: Whisper 模型大小
            cache_dir: 模型缓存目录
            device: 计算设备 (cpu/cuda)
            compute_type: 计算类型 (int8/float16/float32)
        """
        self.model_size = model_size
        self.cache_dir = cache_dir
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _ensure_model(self):
        """确保模型已加载"""
        if self._model is not None:
            return

        try:
            from faster_whisper import WhisperModel

            download_root = self.cache_dir if self.cache_dir else None
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=download_root,
            )
        except Exception as e:
            raise RuntimeError(f"模型加载失败: {e}")

    @staticmethod
    def check_ffmpeg() -> tuple[bool, str]:
        """
        检测 ffmpeg 是否可用

        Returns:
            (可用, 信息描述)
        """
        try:
            import shutil

            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                return True, f"ffmpeg 已安装: {ffmpeg_path}"
            return False, "未找到 ffmpeg，转写功能需要安装 ffmpeg"
        except Exception as e:
            return False, f"ffmpeg 检测异常: {e}"

    def extract_audio(self, file_path: str) -> np.ndarray:
        """
        用 pydub 提取音频为 16kHz 单声道 float32 numpy 数组

        Args:
            file_path: 音频或视频文件路径

        Returns:
            numpy float32 音频数组 (16kHz, mono)

        Raises:
            ImportError: pydub 未安装
            FileNotFoundError: 文件不存在
            ValueError: 不支持的文件格式
            RuntimeError: ffmpeg 未安装或解码失败
        """
        from pydub import AudioSegment

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        ext = path.suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"不支持的文件格式: {ext}")

        logger.info(f"提取音频: {path.name} ({ext})")

        try:
            # pydub 自动处理音视频格式
            audio = AudioSegment.from_file(str(path))
        except FileNotFoundError:
            raise RuntimeError(
                "未找到 ffmpeg。请安装 ffmpeg 后重试:\n"
                "  Windows: winget install ffmpeg 或 choco install ffmpeg\n"
                "  Linux: sudo apt install ffmpeg\n"
                "  macOS: brew install ffmpeg"
            )
        except Exception as e:
            error_msg = str(e)
            if "ffmpeg" in error_msg.lower() or "ffprobe" in error_msg.lower():
                raise RuntimeError(
                    f"音频解码失败，可能缺少 ffmpeg: {error_msg}\n"
                    "请安装 ffmpeg: winget install ffmpeg"
                )
            raise RuntimeError(f"音频解码失败: {error_msg}")

        # 转为 Whisper 所需格式
        audio = audio.set_frame_rate(16000).set_channels(1)

        # 转为 numpy float32
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

        # pydub 的 get_array_of_samples 返回 int16，需要归一化到 [-1, 1]
        max_val = float(2**15)  # int16 最大值
        samples = samples / max_val

        duration = len(samples) / 16000
        logger.info(f"音频提取完成: {duration:.1f}s, {len(samples)} 采样点")

        return samples

    def transcribe(
        self,
        file_path: str,
        language: Optional[str] = "zh",
        beam_size: int = 5,
        on_progress: Optional[Callable[[str, float], None]] = None,
    ) -> list[TranscriptionSegment]:
        """
        转写音频/视频文件

        Args:
            file_path: 文件路径
            language: 语言代码 (zh/en/ja)，None 为自动检测
            beam_size: 束搜索大小
            on_progress: 进度回调 (status_text, progress_0_to_1)

        Returns:
            带时间戳的转写片段列表
        """

        def _report(text: str, progress: float = 0.0):
            if on_progress:
                on_progress(text, progress)

        # 步骤 1: 提取音频
        _report("提取音频中...", 0.05)
        audio = self.extract_audio(file_path)
        _report("音频提取完成", 0.15)

        # 步骤 2: 加载模型
        _report("加载模型中...", 0.2)
        self._ensure_model()
        _report("模型加载完成", 0.3)

        # 步骤 3: 转写
        _report("转写中...", 0.35)

        # 构建引导提示词
        prompt = None
        if language and language in self.LANGUAGE_PROMPTS:
            prompt = self.LANGUAGE_PROMPTS[language]

        segments_iter, info = self._model.transcribe(
            audio,
            language=language,
            initial_prompt=prompt,
            beam_size=beam_size,
            vad_filter=True,
            without_timestamps=False,  # 需要时间戳
        )

        _report(
            f"检测到语言: {info.language} (概率 {info.language_probability:.2f})", 0.4
        )

        # 步骤 4: 收集片段
        results: list[TranscriptionSegment] = []
        total_duration = info.duration if info.duration > 0 else 1.0

        for segment in segments_iter:
            text = segment.text.strip()
            if text:
                results.append(
                    TranscriptionSegment(
                        start=segment.start,
                        end=segment.end,
                        text=text,
                    )
                )

            # 更新进度（转写阶段占 0.4 ~ 0.95）
            progress = 0.4 + 0.55 * min(1.0, segment.end / total_duration)
            _report(
                f"转写中 ({segment.end:.0f}s / {total_duration:.0f}s)",
                progress,
            )

        _report(f"转写完成，共 {len(results)} 个片段", 1.0)
        logger.info(f"转写完成: {len(results)} 个片段, 总时长 {total_duration:.1f}s")

        return results

    @staticmethod
    def segments_to_srt(segments: list[TranscriptionSegment]) -> str:
        """
        将片段列表转为 SRT 字幕格式

        格式示例:
            1
            00:00:01,200 --> 00:00:05,400
            大家好

            2
            00:00:05,800 --> 00:00:10,200
            今天我们来聊一下
        """
        lines: list[str] = []

        for i, seg in enumerate(segments, 1):
            # SRT 时间格式: HH:MM:SS,mmm
            start_str = FileTranscriber._format_srt_time(seg.start)
            end_str = FileTranscriber._format_srt_time(seg.end)

            lines.append(str(i))
            lines.append(f"{start_str} --> {end_str}")
            lines.append(seg.text)
            lines.append("")  # 空行分隔

        return "\n".join(lines)

    @staticmethod
    def segments_to_txt(segments: list[TranscriptionSegment]) -> str:
        """将片段列表转为纯文本格式（每行一句）"""
        return "\n".join(seg.text for seg in segments)

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """将秒数格式化为 SRT 时间 (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def get_file_filter_string() -> str:
        """获取文件选择过滤字符串（用于 filedialog）"""
        all_exts = " ".join(
            f"*{ext}" for ext in sorted(FileTranscriber.SUPPORTED_FORMATS)
        )
        audio_exts = " ".join(
            f"*{ext}" for ext in sorted(FileTranscriber.SUPPORTED_AUDIO)
        )
        video_exts = " ".join(
            f"*{ext}" for ext in sorted(FileTranscriber.SUPPORTED_VIDEO)
        )
        return (
            f"所有支持格式 ({all_exts})|音频文件 ({audio_exts})|视频文件 ({video_exts})"
        )
