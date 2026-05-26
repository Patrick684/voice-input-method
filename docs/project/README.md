# 语音输入法 (Voice Input Method)

基于本地 Whisper 模型的桌面语音输入法工具。按住快捷键说话，松开后自动将语音转为文字并输入到当前活动窗口。支持 Windows / Linux / macOS。

## 功能特性

- **本地语音识别**: 基于 faster-whisper (OpenAI Whisper 加速版)，无需联网，保护隐私
- **全局快捷键**: 按住右 Alt 键即可录音，松开自动识别并输入
- **热词识别**: 预置词库 + 自定义热词，提升专业术语、人名、地名识别准确率
- **智能后处理**: 规则引擎自动纠正常见中文识别错误
- **智能标点**: 自动优化中文标点，智能补充句末标点
- **语义 Emoji**: 根据说话内容自动添加表情符号
- **识别历史**: 自动保存识别记录，支持搜索和统计
- **系统托盘**: 最小化运行，不干扰日常工作
- **剪贴板友好**: 输入后自动恢复原始剪贴板内容

## 快速开始

### 环境要求

- Windows 10/11, Ubuntu 20.04+, macOS 12+
- Python 3.9+ (推荐 3.12)
- 麦克风设备
- GPU (可选，NVIDIA CUDA 11.8+)

### 安装

```bash
# 克隆仓库
git clone https://github.com/Patrick684/voice-input-method.git
cd voice-input-method

# 创建 Conda 环境
conda create -n voice_input python=3.12 -y
conda activate voice_input

# 安装系统依赖 (Linux)
sudo apt install portaudio19-dev python3-dev ffmpeg

# 安装系统依赖 (macOS)
brew install portaudio ffmpeg

# 安装 Python 依赖
pip install -r requirements.txt
# 国内用户: pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 验证安装
python scripts/verify_compatibility.py

# 快速测试核心功能（模型加载 + 后处理 + 热词）
python scripts/verify_compatibility.py --quick-test
```

### 运行

```bash
# Windows (需要管理员权限以监听全局快捷键)
python main.py

# Linux / macOS
python main.py
```

首次启动会自动下载 Whisper small 模型（约 500MB）。详细安装说明见 [install.md](install.md)。

### 遇到问题？

```bash
# 生成环境报告（自动复制到剪贴板），发给开发者排查
python scripts/verify_compatibility.py --report
```

## 使用方式

1. 启动后，系统托盘会出现绿色麦克风图标
2. 按住 **右 Alt** 键开始录音（图标变红）
3. 对着麦克风说话
4. 松开按键，等待识别完成（图标变蓝）
5. 识别结果会自动输入到当前焦点窗口

## 配置

右键托盘图标 -> 设置，可配置:

- 录音快捷键和触发方式
- 识别模型大小 (tiny/base/small/medium)
- 识别语言
- 热词管理（预置词库 + 自定义）
- 后处理规则开关
- Emoji 开关和密度
- 识别历史记录
- 主题切换 (系统/亮色/暗色)

## 许可证

MIT License
