# API 参考

## Config (config.py)

```python
class Config:
    def __init__(self, config_dir: str = None)
    def get(self, key: str, default=None) -> Any
    def set(self, key: str, value: Any)      # 自动保存
    def reset(self, key: str = None)          # 重置为默认值
    def save()

    @property model_cache_dir -> Path
    @property hotword_file -> Path
```

## AudioRecorder (audio/recorder.py)

```python
class AudioRecorder:
    def __init__(self, sample_rate=16000, device=None,
                 on_audio_chunk=None, on_volume=None)

    def start_recording() -> bool
    def stop_recording() -> np.ndarray | None
    def cancel_recording()
    def get_audio_duration(audio: np.ndarray) -> float

    @staticmethod list_devices() -> list[dict]
    @property is_recording -> bool
```

## WhisperEngine (engine/whisper_engine.py)

```python
class WhisperEngine:
    def __init__(self, model_size="base", compute_type="int8",
                 device="cpu", cache_dir=None)

    def load_model(on_progress=None)
    def unload_model()
    def transcribe(audio: np.ndarray, language="zh",
                   initial_prompt=None, beam_size=5,
                   vad_filter=True, vad_threshold=0.5) -> str | None
    def transcribe_async(audio, on_complete, **kwargs) -> Thread
    def change_model(model_size: str)

    @property is_loaded -> bool
    @property is_processing -> bool
```

## HotwordManager (engine/hotword_manager.py)

```python
class HotwordManager:
    def __init__(self, hotword_file=None)

    # 全局热词
    def add_global_hotword(word: str)
    def remove_global_hotword(word: str)
    def get_global_hotwords() -> list[str]

    # 分类管理
    def create_category(name: str) -> HotwordCategory
    def delete_category(name: str)
    def add_hotword(category: str, word: str)
    def remove_hotword(category: str, word: str)
    def get_categories() -> list[str]
    def get_hotwords(category: str) -> list[str]

    # 激活/停用
    def activate_category(name: str)
    def deactivate_category(name: str)

    # Whisper prompt 生成
    def build_initial_prompt(weight=1.5) -> str | None

    # 导入/导出
    def export_hotwords(filepath, format="json")
    def import_hotwords(filepath, format="json")
```

## PunctuationProcessor (engine/punctuation_processor.py)

```python
class PunctuationProcessor:
    def __init__(self, auto_paragraph=False, paragraph_threshold=50)

    def process(text: str, language="zh") -> str
```

## EmojiInjector (engine/emoji_injector.py)

```python
class EmojiInjector:
    def __init__(self, enabled=True, density="medium")

    def process(text: str) -> str
    def set_density(density: str)           # low/medium/high
    def add_custom_rule(keywords, emoji, priority=1)
```

## TextInjector (input/text_injector.py)

```python
class TextInjector:
    def __init__(self, restore_clipboard=True)

    def inject_text(text: str) -> bool
    def inject_text_with_delay(text: str, delay=0.5) -> Thread
```

## HotkeyManager (hotkey/hotkey_manager.py)

```python
class HotkeyManager:
    def __init__(self, hotkey="right alt", mode="hold",
                 on_start=None, on_stop=None, on_cancel=None)

    def register()
    def unregister()
    def cancel_recording()
    def change_hotkey(new_hotkey, new_mode=None)
    def set_active(active: bool)

    @property is_recording -> bool
```

## TrayApp (ui/tray_app.py)

```python
class AppState(Enum):
    IDLE, RECORDING, PROCESSING, DISABLED

class TrayApp:
    def __init__(self, hotkey="右Alt", on_settings=None,
                 on_quit=None, on_toggle=None)

    def setup()                             # 初始化并显示托盘
    def set_state(state: AppState)
    def show_notification(title, message, duration=3000)
    def update_hotkey_display(hotkey: str)
    def cleanup()
```

## SettingsWindow (ui/settings_window.py)

```python
class SettingsWindow:
    def __init__(self, config: Config, on_settings_changed=None)

    def show()
    def close()
```
