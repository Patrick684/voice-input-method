"""
用途：CI 环境下的模块导入验证脚本
示例：python .github/scripts/verify_imports.py
"""

import importlib
import sys

# 必须成功的纯 Python 模块（无系统依赖）
REQUIRED_MODULES = [
    ("config", "Config"),
    ("engine.hotword_manager", "HotwordManager"),
    ("engine.punctuation_processor", "PunctuationProcessor"),
    ("engine.emoji_injector", "EmojiInjector"),
    ("engine.whisper_engine", "WhisperEngine"),
]

# 可选模块（依赖系统库，CI 环境可能缺失）
OPTIONAL_MODULES = [
    ("audio.recorder", "AudioRecorder"),
    ("input.text_injector", "TextInjector"),
    ("hotkey.hotkey_manager", "HotkeyManager"),
    ("ui.tray_app", "TrayApp"),
    ("ui.settings_window", "SettingsWindow"),
]

errors = 0

print("=== 必选模块验证 ===")
for module_name, class_name in REQUIRED_MODULES:
    try:
        mod = importlib.import_module(module_name)
        getattr(mod, class_name)
        print(f"  {class_name} OK")
    except Exception as e:
        print(f"  {class_name} FAIL: {e}")
        errors += 1

print("\n=== 可选模块验证 ===")
for module_name, class_name in OPTIONAL_MODULES:
    try:
        mod = importlib.import_module(module_name)
        getattr(mod, class_name)
        print(f"  {class_name} OK")
    except Exception as e:
        print(f"  {class_name} SKIP (缺少系统依赖): {e}")

if errors > 0:
    print(f"\n验证失败: {errors} 个必选模块导入错误")
    sys.exit(1)
else:
    print("\n全部必选模块验证通过")
