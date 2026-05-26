"""
用途：验证音视频转写流水线是否正常工作
"""
import sys
import time
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.transcriber import FileTranscriber
from config import Config


def main():
    config = Config()
    mp3_path = Path(__file__).resolve().parent.parent / ".qoder" / "scripts" / "057689500453-2404121807.mp3"

    if not mp3_path.exists():
        print(f"错误: 测试文件不存在: {mp3_path}")
        return

    print(f"测试文件: {mp3_path}")
    print(f"模型大小: {config.get('model_size')}")
    print(f"模型缓存: {config.model_cache_dir}")
    print()

    # 1. 检查 ffmpeg
    ok, msg = FileTranscriber.check_ffmpeg()
    print(f"[1/3] ffmpeg 检查: {msg}")
    if not ok:
        return

    # 2. 创建转写器
    print("[2/3] 初始化 FileTranscriber...")
    transcriber = FileTranscriber(
        model_size=config.get("model_size"),
        device="cpu",
        compute_type=config.get("compute_type"),
        cache_dir=str(config.model_cache_dir),
    )
    print("      初始化完成")

    # 3. 转写（extract_audio + transcribe 合为一体）
    print("[3/3] 开始转写（包含音频提取 + 模型加载 + 识别）...")

    def on_progress(text, progress):
        print(f"      [{progress*100:.0f}%] {text}")

    t0 = time.time()
    segments = transcriber.transcribe(
        str(mp3_path),
        language="zh",
        beam_size=config.get("beam_size"),
        on_progress=on_progress,
    )
    elapsed = time.time() - t0
    print(f"      转写完成: {elapsed:.1f}s")
    print()

    # 输出结果
    full_text = FileTranscriber.segments_to_txt(segments)
    srt_text = FileTranscriber.segments_to_srt(segments)
    print(f"=== 纯文本 ({len(segments)} 个片段) ===")
    print(full_text)
    print()
    print("=== SRT 字幕 ===")
    print(srt_text[:500], "..." if len(srt_text) > 500 else "")


if __name__ == "__main__":
    main()
