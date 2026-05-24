import os

# ==============================================
# 强制开启国内镜像源（解决HF拉黑、0进度、下载慢）
# 不需要VPN！不需要注册！不需要TOKEN！
# ==============================================
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from huggingface_hub import snapshot_download

# 下载路径：优先使用命令行参数，否则使用 APPDATA 默认路径
if len(os.sys.argv) > 1:
    CACHE_DIR = os.sys.argv[1]
else:
    CACHE_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "VoiceInput", "Models")

# ======================
# 下载 small 模型
# ======================
print("开始下载 faster-whisper-small 模型（国内镜像加速）...")

model_path = snapshot_download(
    "Systran/faster-whisper-small",
    cache_dir=CACHE_DIR,
    resume_download=True      # 支持断点续传
)

print("=" * 50)
print("✅ small 模型下载完成！路径：")
print(model_path)
print("=" * 50)