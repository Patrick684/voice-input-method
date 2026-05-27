import os
import urllib.request

# ====================== 配置 ======================
# 下载目录（你指定的路径）
SAVE_DIR = r"C:\Users\16574\AppData\Roaming\VoiceInput\models\medium"

# 模型文件列表（官方源，直连下载，不需要镜像）
FILES = [
    "https://huggingface.co/guillaumekln/faster-whisper-medium/resolve/main/config.json",
    "https://huggingface.co/guillaumekln/faster-whisper-medium/resolve/main/model.bin",
    "https://huggingface.co/guillaumekln/faster-whisper-medium/resolve/main/tokenizer.json",
    "https://huggingface.co/guillaumekln/faster-whisper-medium/resolve/main/vocabulary.txt",
]

# ===================================================

# 创建目录
os.makedirs(SAVE_DIR, exist_ok=True)
print(f"文件将下载到：{SAVE_DIR}\n")


# 下载函数
def download_file(url, save_path):
    if os.path.exists(save_path):
        print(f"✅ 已存在，跳过：{os.path.basename(save_path)}")
        return

    print(f"⏬ 开始下载：{os.path.basename(save_path)}")

    def show_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        percent = downloaded * 100 / total_size
        print(f"\r进度：{percent:.1f}%", end="")

    try:
        urllib.request.urlretrieve(url, save_path, show_progress)
        print(f"\n✅ 下载完成：{os.path.basename(save_path)}\n")
    except Exception as e:
        print(f"\n❌ 下载失败：{e}\n")


# 批量下载
for url in FILES:
    filename = url.split("/")[-1]
    save_path = os.path.join(SAVE_DIR, filename)
    download_file(url, save_path)

print("🎉 所有文件下载完成！")
print("📂 路径：" + SAVE_DIR)
