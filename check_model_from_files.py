import os

model_path = r"C:\Users\16574\AppData\Roaming\VoiceInput\Models\models--Systran--faster-whisper-small"

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