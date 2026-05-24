# 安装指南

## 系统要求

| 项目 | 最低要求 | 推荐配置 |
|------|----------|----------|
| 操作系统 | Windows 10 | Windows 11 |
| Python | 3.12+ | 3.12.x |
| 内存 | 4 GB | 8 GB+ |
| 磁盘空间 | 500 MB | 2 GB (含模型文件) |
| 音频设备 | 任意麦克风 | 降噪麦克风 |

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

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

核心依赖:
- `faster-whisper` - 语音识别引擎 (基于 CTranslate2 加速)
- `sounddevice` - 音频采集
- `pystray` - 系统托盘
- `customtkinter` - 设置界面
- `Pillow` - 图标绘制
- `keyboard` - 全局快捷键监听
- `pyperclip` - 剪贴板操作

### 5. 验证安装

```bash
python -c "from engine.whisper_engine import WhisperEngine; print('安装成功')"
```

## 首次启动

```bash
# 需要以管理员身份运行（全局快捷键需要管理员权限）
python main.py
```

首次启动时，程序会自动下载 Whisper base 模型（约 150MB）。下载完成后模型会缓存在本地，后续启动无需重复下载。

## 模型选择

程序支持多种 Whisper 模型，可在设置中切换:

| 模型 | 大小 | 速度 | 准确度 | 推荐场景 |
|------|------|------|--------|----------|
| tiny | 75 MB | 最快 | 一般 | 快速测试 |
| base | 150 MB | 快 | 较好 | 日常使用 (默认) |
| small | 500 MB | 中等 | 好 | 对准确度要求高 |
| medium | 1.5 GB | 较慢 | 很好 | 专业场景 |

## 常见问题

### 快捷键不生效
需要以管理员身份运行程序，否则无法监听全局快捷键。

### 无法打开麦克风
检查系统隐私设置中是否允许应用访问麦克风。

### 模型下载失败
确保网络连接正常。模型文件从 Hugging Face 下载，部分地区可能需要配置代理。
