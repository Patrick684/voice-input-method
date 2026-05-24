# 语音输入法 (Voice Input Method)

基于本地 Whisper 模型的桌面语音输入法工具。按住快捷键说话，松开后自动将语音转为文字并输入到当前活动窗口。

## 功能特性

- **本地语音识别**: 基于 faster-whisper (OpenAI Whisper 加速版)，无需联网，保护隐私
- **全局快捷键**: 按住右 Alt 键即可录音，松开自动识别并输入
- **热词识别**: 支持自定义热词表，提升专业术语、人名、地名识别准确率
- **智能标点**: 自动优化中文标点，智能补充句末标点
- **语义 Emoji**: 根据说话内容自动添加表情符号
- **系统托盘**: 最小化运行，不干扰日常工作
- **剪贴板友好**: 输入后自动恢复原始剪贴板内容

## 快速开始

### 环境要求

- Windows 10/11
- Python 3.12+
- 麦克风设备

### 安装

```bash
# 克隆仓库
git clone https://github.com/Patrick684/voice-input-method.git
cd voice-input-method

# 创建 Conda 环境
conda create -n voice_input python=3.12 -y
conda activate voice_input

# 安装依赖
pip install -r requirements.txt
```

### 运行

```bash
# 需要管理员权限以监听全局快捷键
python main.py
```

首次启动会自动下载 Whisper base 模型（约 150MB）。

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
- 热词管理
- Emoji 开关和密度

## 许可证

MIT License
