# settings_window.py 设计文档

## 模块定位

设置窗口是语音输入法的核心配置界面，基于 CustomTkinter 构建，提供所有功能的可视化管理入口。

## 类结构

```
SettingsWindow(ctk.CTkToplevel)
├── 构造函数 __init__()
│   ├── 接收 Config, HotwordManager, PostProcessor, RecognitionHistory
│   └── 窗口初始化 (560x580, 置顶)
│
├── UI 构建 (_setup_ui)
│   ├── _create_general_tab()    — 基本设置: 快捷键/触发模式/语言/开关/主题
│   ├── _create_engine_tab()     — 语音识别: 模型/精度/束搜索/音频设备
│   ├── _create_hotwords_tab()   — 热词管理: 预置词库开关 + 用户自定义编辑
│   ├── _create_advanced_tab()   — 高级设置: VAD/剪贴板/Emoji/后处理/历史
│   └── _create_history_tab()    — 识别历史: 统计/搜索/浏览/清空
│
├── 数据加载/保存
│   ├── _load_settings()         — 从 Config 加载到 UI 变量
│   └── _save_settings()         — 从 UI 变量保存到 Config + 回调
│
├── 热词管理
│   └── _builtin_switches dict   — 预置词库分类开关状态
│
├── 历史管理
│   ├── _refresh_history()       — 刷新历史列表显示
│   ├── _search_history()        — 关键词搜索
│   └── _clear_history()         — 清空确认+执行
│
├── 主题
│   └── _on_theme_changed()      — 实时切换 system/light/dark
│
└── 重置
    └── _reset_settings()        — 输入 'reset' 确认后恢复默认
```

## 选项卡布局

| 选项卡 | 控件数 | 数据绑定 |
|--------|--------|----------|
| 基本设置 | 8 | hotkey, mode, language, auto_start, minimized, notify, theme |
| 语音识别 | 5 | model_size, compute_type, beam_size, audio_device |
| 热词管理 | 4+N | builtin_switches[], global_hotwords (文本框) |
| 高级设置 | 8 | vad_filter, vad_threshold, clipboard, emoji, density, post_process, history |
| 识别历史 | 5 | stats_label, search_entry, history_textbox |

## 数据流

```
用户操作 UI
    ↓
_save_settings() 收集变更
    ↓
Config.set() 持久化到 JSON
    ↓
on_settings_changed(changes) 回调
    ↓
main.py._on_settings_changed()
    ↓
各模块运行时更新 (HotkeyManager/Engine/Processor...)
```

## 依赖关系

- `config.Config`: 配置读写
- `audio.recorder.AudioRecorder`: 设备列表获取
- `engine.hotword_manager.HotwordManager`: 热词管理 (可选注入)
- `engine.post_processor.PostProcessor`: 规则引擎 (可选注入)
- `utils.history.RecognitionHistory`: 识别历史 (可选注入)

## 扩展点

- 新增选项卡: 在 `_setup_ui()` 中调用 `_create_xxx_tab()`
- 新增配置项: 在 `_load_settings()` 和 `_save_settings()` 中添加映射
- 主题定制: 通过 `_on_theme_changed()` 扩展自定义主题
