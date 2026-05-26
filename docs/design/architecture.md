# 系统架构

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                            │
│                   VoiceInputApp                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ hotkey/  │ │ audio/   │ │ engine/  │ │  input/   │  │
│  │HotkeyMgr │→│Recorder  │→│ Pipeline │→│ TextInj.  │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
│  ┌──────────┐ ┌──────────────────────────────────────┐  │
│  │   ui/    │ │         Worker Thread                │  │
│  │ TrayApp  │ │  ┌─────────────────────────────┐     │  │
│  │ Settings │ │  │ WhisperEngine.transcribe()  │     │  │
│  └──────────┘ │  │ PunctuationProcessor        │     │  │
│               │  │ EmojiInjector               │     │  │
│               │  │ PostProcessor               │     │  │
│               │  └─────────────────────────────┘     │  │
│               └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 模块职责

| 模块 | 文件 | 职责 |
|------|------|------|
| config | `config.py` | 配置管理，JSON 持久化存储 |
| audio | `audio/recorder.py` | 麦克风音频采集，sounddevice 封装 |
| engine | `engine/whisper_engine.py` | Whisper 语音识别引擎封装 |
| engine | `engine/hotword_manager.py` | 热词管理，initial_prompt 构建 |
| engine | `engine/punctuation_processor.py` | 中文标点优化后处理 |
| engine | `engine/emoji_injector.py` | 语义 emoji 注入 |
| engine | `engine/post_processor.py` | 后处理规则替换引擎 |
| engine | `engine/stream_vad.py` | 流式 VAD 检测器，实时切句 |
| engine | `engine/transcriber.py` | 文件转写引擎，音视频转字幕 |
| input | `input/text_injector.py` | 剪贴板+粘贴文本输入 |
| hotkey | `hotkey/hotkey_manager.py` | 全局快捷键监听 |
| ui | `ui/tray_app.py` | 系统托盘图标和菜单 |
| ui | `ui/settings_window.py` | 设置窗口 UI（含热词管理/历史面板） |
| ui | `ui/transcribe_window.py` | 文件转写窗口 UI |
| utils | `utils/history.py` | 识别历史记录管理 |

## 线程模型

```
主线程                    Worker 线程               快捷键线程
────────                  ───────────               ──────────
pystray 事件循环           模型加载                   keyboard 监听
  ↓                         ↓                         ↓
设置窗口显示               等待任务 (queue.get)        按键事件
  ↓                         ↓                         ↓
                          语音识别                   → on_start 回调
                          标点处理                   → on_stop 回调
                          emoji 注入                  → on_cancel 回调
                          规则替换
                          结果返回 (queue.put)
                            ↓
主线程接收结果
保存历史记录
文本注入
状态更新
```

## 状态机

```
        ┌──────────┐
        │   IDLE   │ ←────────────────────┐
        │  (绿色)  │                      │
        └────┬─────┘                      │
             │ 按下快捷键                   │ 识别完成/失败
             ↓                             │
        ┌──────────┐    松开快捷键    ┌────────────┐
        │RECORDING │ ──────────────→ │ PROCESSING │
        │  (红色)  │                 │   (蓝色)   │
        └──────────┘                 └────────────┘
             │                            │
             │ 按住<0.15s                 │
             ↓                            │
        ┌──────────┐                      │
        │  CANCEL  │──────────────────────┘
        └──────────┘

        ┌──────────┐
        │ DISABLED │ ← 用户手动停止服务
        │  (灰色)  │
        └──────────┘
```

## 配置存储

配置文件位于 `%APPDATA%/VoiceInput/config.json`:

```json
{
  "hotkey": "right alt",
  "model_size": "base",
  "language": "zh",
  "beam_size": 5,
  "compute_type": "int8",
  "vad_filter": true,
  "emoji_enabled": true,
  "emoji_density": "medium"
}
```

热词文件: `%APPDATA%/VoiceInput/hotwords.json`
模型缓存: `%APPDATA%/VoiceInput/models/`

## 依赖关系

```
main.py
├── config.py (配置管理)
├── audio/recorder.py
│   └── sounddevice, numpy
├── engine/
│   ├── whisper_engine.py → faster-whisper
│   ├── hotword_manager.py
│   ├── punctuation_processor.py
│   ├── emoji_injector.py
│   ├── post_processor.py
│   ├── stream_vad.py → numpy
│   └── transcriber.py → pydub, faster-whisper
├── input/text_injector.py
│   └── pyperclip, keyboard
├── hotkey/hotkey_manager.py
│   └── keyboard, winsound
├── utils/
│   └── history.py
└── ui/
    ├── tray_app.py → pystray, Pillow
    └── settings_window.py → customtkinter
```

## 兼容性测试

项目提供兼容性验证脚本（位于 `scripts/verify_compatibility.py`），新设备首次运行前建议执行：

```bash
python scripts/verify_compatibility.py
```

检测项目：

| 检测类别 | 检测内容 | 失败级别 |
|----------|----------|----------|
| 操作系统 | Windows/Linux/macOS, 架构, 权限 | 必选 |
| Python 版本 | 3.9~3.12, 64位 | 必选 |
| 核心依赖 | numpy, faster-whisper, sounddevice 等 8 个包 | 必选 |
| 可选依赖 | torch, pydub | 警告 |
| 音频设备 | 麦克风设备检测 | 必选 |
| GPU 加速 | NVIDIA CUDA / AMD ROCm / CPU 兜底 | 可选 |
| 文件权限 | 配置目录/模型缓存可写 | 必选 |
| Whisper 推理 | 模型加载 + CPU/GPU 推理测试 | 必选 |
