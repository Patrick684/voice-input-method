"""手动下载 Whisper 模型（通过代理）"""

import os
import sys
import urllib.request

PROXY = "http://127.0.0.1:7890"
CACHE_DIR = os.path.join(os.environ.get("APPDATA", ""), "VoiceInput", "models")

# 支持的模型配置（仓库、revision、文件及大小）
MODELS = {
    "base": {
        "repo": "Systran/faster-whisper-base",
        "revision": "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66",
        "files": {
            "config.json": 2309,
            "tokenizer.json": 2203239,
            "vocabulary.txt": 459861,
            "model.bin": 145217532,
        },
    },
    "small": {
        "repo": "Systran/faster-whisper-small",
        "revision": "536b0662742c02347bc0e980a01041f333bce120",
        "files": {
            "config.json": 2309,
            "tokenizer.json": 2203239,
            "vocabulary.txt": 459861,
            "model.bin": 500188928,
        },
    },
    "medium": {
        "repo": "Systran/faster-whisper-medium",
        "revision": "08e178d48790749d25932bbc082711ddcfdfbc4f",
        "files": {
            "config.json": 2257,
            "tokenizer.json": 2203239,
            "vocabulary.txt": 459861,
            "model.bin": 1528865420,
        },
    },
}


def download_file(filename, expected_size, opener, repo, revision, snap_dir):
    url = f"https://huggingface.co/{repo}/resolve/{revision}/{filename}?download=true"
    snap_path = os.path.join(snap_dir, filename)

    # Check if already downloaded
    if os.path.exists(snap_path) and os.path.getsize(snap_path) == expected_size:
        print(f"[SKIP] {filename} already exists ({expected_size} bytes)")
        return True

    print(f"[DOWNLOAD] {filename} ({expected_size / 1024 / 1024:.1f} MB)")
    try:
        req = urllib.request.Request(url)
        response = opener.open(req, timeout=600)

        # Stream download with progress
        os.makedirs(snap_dir, exist_ok=True)
        total = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        with open(snap_path, "wb") as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                if expected_size:
                    pct = total / expected_size * 100
                    print(
                        f"\r  {total / 1024 / 1024:.1f} / {expected_size / 1024 / 1024:.1f} MB ({pct:.0f}%)",
                        end="",
                        flush=True,
                    )

        print(f"\n  Done: {total} bytes")

        if expected_size and total != expected_size:
            print(f"  WARNING: Size mismatch! Expected {expected_size}, got {total}")
            return False

        return True
    except Exception as e:
        print(f"\n  FAILED: {e}")
        return False


def main():
    # 命令行参数：模型名称（默认 small）
    model_name = sys.argv[1] if len(sys.argv) > 1 else "small"

    if model_name not in MODELS:
        print(f"未知模型: {model_name}，支持: {', '.join(MODELS.keys())}")
        sys.exit(1)

    model_cfg = MODELS[model_name]
    repo = model_cfg["repo"]
    revision = model_cfg["revision"]
    files = model_cfg["files"]

    blob_dir = os.path.join(CACHE_DIR, f"models--{repo.replace('/', '--')}", "blobs")
    snap_dir = os.path.join(
        CACHE_DIR, f"models--{repo.replace('/', '--')}", "snapshots", revision
    )

    proxy = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
    opener = urllib.request.build_opener(proxy)

    print(f"模型: {model_name} ({repo})")
    print(f"代理: {PROXY}")
    print(f"缓存目录: {CACHE_DIR}")
    os.makedirs(snap_dir, exist_ok=True)
    os.makedirs(blob_dir, exist_ok=True)

    # 清理不完整文件
    import glob

    for f in glob.glob(os.path.join(blob_dir, "*.incomplete")):
        os.remove(f)
        print(f"已清理: {os.path.basename(f)}")

    success = True
    for filename, size in files.items():
        if not download_file(filename, size, opener, repo, revision, snap_dir):
            success = False

    if success:
        print(f"\n{model_name} 模型下载完成！")
        for filename, size in files.items():
            path = os.path.join(snap_dir, filename)
            actual = os.path.getsize(path) if os.path.exists(path) else 0
            status = "OK" if actual == size else f"大小不匹配 ({actual} vs {size})"
            print(f"  {filename}: {status}")
    else:
        print("\n部分文件下载失败！")
        sys.exit(1)


if __name__ == "__main__":
    main()
