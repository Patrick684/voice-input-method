# 安装指南

## 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 操作系统 | Windows 10 / Ubuntu 20.04 / macOS 12 | Windows 11 / Ubuntu 22.04 / macOS 14 |
| Python | 3.9+ | 3.12.x |
| 内存 | 4 GB | 8 GB+ |
| 磁盘空间 | 500 MB | 2 GB (含模型文件) |
| 音频设备 | 任意麦克风 | 降噪麦克风 |
| GPU (可选) | - | NVIDIA RTX 3060+ (CUDA 11.8+) |

## 安装步骤

### 1. 安装 Python 3.12

推荐使用 [Anaconda](https://www.anaconda.com/download) 管理 Python 环境:

```bash
# 验证 Python 版本
python --version
# 应输出 Python 3.12.x
```

### 2. 创建虚拟环境

```bash
# 使用 Conda 创建独立环境
conda create -n voice_input python=3.12 -y
conda activate voice_input
```

### 3. 克隆项目

```bash
git clone https://github.com/Patrick684/voice-input-method.git
cd voice-input-method
```

### 4. 安装系统依赖

根据操作系统安装必要的系统库:

#### Windows
无需额外系统依赖。

#### Linux (Debian/Ubuntu)
```bash
# 音频支持 + 编译工具
sudo apt update
sudo apt install portaudio19-dev python3-dev ffmpeg
# 文本注入支持 (可选)
sudo apt install xdotool
```

#### macOS
```bash
# 使用 Homebrew 安装音频支持
brew install portaudio ffmpeg
```

### 5. 安装 Python 依赖

```bash
# 标准安装
pip install -r requirements.txt

# 国内用户推荐使用清华镜像源（加速下载）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

核心依赖:
- `faster-whisper` - 语音识别引擎 (基于 CTranslate2 加速)
- `sounddevice` - 音频采集
- `pystray` - 系统托盘
- `customtkinter` - 设置界面
- `Pillow` - 图标绘制
- `keyboard` - 全局快捷键监听
- `pyperclip` - 剪贴板操作

可选依赖:
- `torch` (CUDA 版) - GPU 加速推理
- `pydub` - 音频文件处理

```bash
# GPU 加速 (可选，NVIDIA 显卡)
pip install torch --index-url https://download.pytorch.org/whl/cu121

# 国内镜像 GPU 安装
pip install torch --index-url https://download.pytorch.org/whl/cu121 \
    -f https://mirror.sjtu.edu.cn/pytorch-wheels/torch_stable.html
```

### 6. 验证安装

```bash
# 运行兼容性检查
python scripts/verify_compatibility.py

# 快速验证核心模块
python -c "from engine.whisper_engine import WhisperEngine; print('安装成功')"
```

## 权限配置

### Windows
- 需要以**管理员身份**运行程序，否则无法注册全局快捷键
- 右键快捷方式 -> 以管理员身份运行

### macOS
- 系统设置 -> 隐私与安全性 -> **辅助功能** -> 添加应用
- 系统设置 -> 隐私与安全性 -> **麦克风** -> 允许访问

### Linux
- 确保用户在 `audio` 组: `sudo usermod -aG audio $USER`
- X11 环境通常无需特殊权限
- Wayland 环境可能需要额外配置（建议使用 X11）

## 首次启动

```bash
# Windows (管理员权限)
python main.py

# Linux / macOS
python main.py
```

首次启动时，程序会自动下载 Whisper small 模型（约 500MB）。下载完成后模型会缓存在本地，后续启动无需重复下载。

## 模型下载失败时的手动下载

如果自动下载失败，可手动下载模型文件:

| 模型 | 下载地址 | 大小 |
|------|----------|------|
| small | https://huggingface.co/Systran/faster-whisper-small | 500 MB |
| base | https://huggingface.co/Systran/faster-whisper-base | 150 MB |
| tiny | https://huggingface.co/Systran/faster-whisper-tiny | 75 MB |

或使用项目内镜像下载脚本:
```bash
python download_model_from_mirror.py
```

放置路径:
- Windows: `%APPDATA%\VoiceInput\models\`
- Linux/macOS: `~/.config/VoiceInput/models/`

## 模型选择

程序支持多种 Whisper 模型，可在设置中切换:

| 模型 | 大小 | 速度 | 准确度 | 推荐场景 |
|------|------|------|--------|----------|
| tiny | 75 MB | 最快 | 一般 | 快速测试 |
| base | 150 MB | 快 | 较好 | 日常使用 |
| small | 500 MB | 中等 | 好 | 对准确度要求高 (默认) |
| medium | 1.5 GB | 较慢 | 很好 | 专业场景 |

## 常见问题

### 快捷键不生效
Windows: 需要以管理员身份运行程序。macOS: 在系统设置中开启辅助功能权限。

### 无法打开麦克风
检查系统隐私设置中是否允许应用访问麦克风。Linux 用户确认在 audio 组中。

### 模型下载失败
使用镜像脚本下载: `python download_model_from_mirror.py`，或手动下载后放入模型缓存目录。

### GPU 加速不工作
程序会自动回退到 CPU 模式。如需 GPU 加速，安装 CUDA 版 PyTorch:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### 兼容性检查未通过
运行 `python scripts/verify_compatibility.py`，脚本会输出具体的修复建议。
