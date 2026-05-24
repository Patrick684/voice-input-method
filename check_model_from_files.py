"""
用途：检查 Whisper 模型是否已下载完整
示例：python check_model_from_files.py [模型名称] [缓存目录]
"""
import os
import sys

# 支持命令行参数，否则使用默认路径
model_name = sys.argv[1] if len(sys.argv) > 1 else "small"
cache_base = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "VoiceInput", "Models"
)
model_path = os.path.join(cache_base, f"models--Systran--faster-whisper-{model_name}")

print("检查模型路径：", model_path)

if os.path.exists(model_path):
    files = os.listdir(model_path)
    print(f"目录存在，包含 {len(files)} 个项目")

    size = 0
    for root, dirs, files_in_dir in os.walk(model_path):
        for f in files_in_dir:
            fp = os.path.join(root, f)
            size += os.path.getsize(fp)

    size_mb = size / 1024 / 1024
    print(f"模型总大小：{size_mb:.2f} MB")

    if size_mb > 100:
        print("✅ 模型已下载完成")
    else:
        print("❌ 模型未下载完成或不完整")
else:
    print("❌ 模型目录不存在，未下载")