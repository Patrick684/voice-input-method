"""
用途：语音输入法项目兼容性验证脚本，检测运行环境、依赖安装、硬件加速等
示例：python scripts/verify_compatibility.py
      python scripts/verify_compatibility.py --report     # 生成环境报告（用于反馈排查）
      python scripts/verify_compatibility.py --quick-test # 快速测试核心功能
"""

import argparse
import importlib
import os
import platform
import struct
import sys
import time
from pathlib import Path
from typing import Tuple


class CompatibilityChecker:
    """兼容性检查器，执行全面的运行环境验证"""

    # 项目所需的最低 Python 版本
    MIN_PYTHON_VERSION = (3, 9)
    # 项目所需的最高 Python 版本（已测试）
    MAX_PYTHON_VERSION = (3, 12)

    # 核心依赖（必须安装）
    CORE_DEPENDENCIES = [
        "numpy",
        "faster_whisper",
        "sounddevice",
        "pystray",
        "customtkinter",
        "PIL",
        "keyboard",
        "pyperclip",
    ]

    # 可选依赖（缺失时降级运行）
    OPTIONAL_DEPENDENCIES = [
        "torch",  # GPU 加速
        "pydub",  # 音频文件处理
    ]

    # 失败 -> 解决方案映射表
    SOLUTIONS = {
        "python_version": {
            "title": "Python 版本不满足要求",
            "fix": [
                "使用 Conda 创建新环境: conda create -n voice_input python=3.12 -y",
                "或从官网下载 Python 3.12: https://www.python.org/downloads/",
            ],
        },
        "core_dependency": {
            "title": "核心依赖缺失",
            "fix": [
                "标准安装: pip install -r requirements.txt",
                "国内镜像: pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple",
                "Linux 系统依赖: sudo apt install portaudio19-dev python3-dev (Debian/Ubuntu)",
                "macOS 系统依赖: brew install portaudio",
            ],
        },
        "audio_device": {
            "title": "音频设备不可用",
            "fix": [
                "检查麦克风是否已连接并被系统识别",
                "Windows: 设置 -> 系统 -> 声音 -> 输入设备",
                "Linux: 确保用户在 audio 组: sudo usermod -aG audio $USER",
                "macOS: 系统设置 -> 隐私与安全性 -> 麦克风",
            ],
        },
        "gpu_inference": {
            "title": "GPU 推理失败",
            "fix": [
                "CPU 模式可正常工作，GPU 为可选加速",
                "安装 CUDA 版 PyTorch: pip install torch --index-url https://download.pytorch.org/whl/cu121",
                "国内镜像: pip install torch --index-url https://download.pytorch.org/whl/cu121 -f https://mirror.sjtu.edu.cn/pytorch-wheels/torch_stable.html",
            ],
        },
        "whisper_inference": {
            "title": "Whisper 推理失败",
            "fix": [
                "重装 faster-whisper: pip install --force-reinstall faster-whisper",
                "检查模型缓存目录是否完整: 删除后重新下载",
                "手动下载模型: python download_model_from_mirror.py",
            ],
        },
        "file_permission": {
            "title": "文件权限不足",
            "fix": [
                "Windows: 以管理员身份运行命令提示符",
                "Linux: 检查目录权限: chmod -R u+w ~/.config/VoiceInput",
                "macOS: 确保终端有完全磁盘访问权限",
            ],
        },
        "hotkey_permission": {
            "title": "快捷键权限不足",
            "fix": [
                "Windows: 右键快捷方式 -> 以管理员身份运行",
                "macOS: 系统设置 -> 隐私与安全性 -> 辅助功能 -> 添加应用",
                "Linux: 通常无需特殊权限，如遇到 X11 问题可尝试 xhost +local:",
            ],
        },
        "model_download": {
            "title": "模型下载失败/缓慢",
            "fix": [
                "使用镜像下载: python download_model_from_mirror.py",
                "手动下载: https://huggingface.co/Systran/faster-whisper-small",
                "放置路径: %APPDATA%/VoiceInput/models/ (Windows)",
                "放置路径: ~/.config/VoiceInput/models/ (Linux/macOS)",
            ],
        },
    }

    def __init__(self):
        self._results: list[Tuple[str, str, bool]] = []
        self._warnings: list[str] = []
        self._failed_categories: set[str] = set()

    def run_all_checks(self) -> bool:
        """
        执行所有兼容性检查

        Returns:
            所有必选检查是否通过
        """
        print("=" * 60)
        print("语音输入法 - 兼容性验证")
        print("=" * 60)
        print()

        self._check_os()
        self._check_python_version()
        self._check_core_dependencies()
        self._check_optional_dependencies()
        self._check_audio_devices()
        self._check_gpu_acceleration()
        self._check_file_permissions()
        self._check_whisper_inference()

        # 输出汇总
        self._print_summary()
        self._print_solutions()

        passed = all(ok for _, _, ok in self._results if not _.startswith("[可选]"))
        return passed

    # ---- 操作系统检查 ----

    def _check_os(self):
        """检查操作系统和架构"""
        print("--- 操作系统 ---")

        os_name = platform.system()
        os_version = platform.version()
        arch = platform.machine()
        bits = struct.calcsize("P") * 8

        # 支持的操作系统
        supported_os = {"Windows", "Linux", "Darwin"}
        is_supported = os_name in supported_os

        self._record(
            f"操作系统: {os_name} {os_version} ({arch}, {bits}位)",
            is_supported,
            f"不支持的操作系统: {os_name}（支持: {supported_os}）",
        )

        if not is_supported:
            self._failed_categories.add("core_dependency")

        # Windows 特定检查
        if os_name == "Windows":
            # 检查 Windows 版本（需要 Win10+）
            win_ver = platform.win32_ver()
            self._record(f"Windows 版本: {win_ver[0]} ({win_ver[1]})", True)

            # 检查管理员权限
            try:
                import ctypes

                is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                self._record(
                    f"管理员权限: {'是' if is_admin else '否'}",
                    True,
                    warn="非管理员权限可能影响全局快捷键注册",
                )
                if not is_admin:
                    pass  # 非管理员是警告级别，不加入 _failed_categories
            except Exception:
                self._record("管理员权限: 无法检测", True)

        # Linux 特定检查
        elif os_name == "Linux":
            # 检查是否有 X11 或 Wayland
            display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
            self._record(
                f"显示服务器: {display or '未检测到'}",
                bool(display),
                "未检测到显示服务器，GUI 功能不可用",
            )

            # 检查 xdotool（Linux 文本注入需要）
            xdotool = self._command_exists("xdotool")
            self._record(
                f"xdotool: {'已安装' if xdotool else '未安装'}",
                True,
                warn="Linux 下文本注入需要 xdotool" if not xdotool else None,
            )

        # macOS 特定检查
        elif os_name == "Darwin":
            mac_ver = platform.mac_ver()
            self._record(f"macOS 版本: {mac_ver[0]}", True)
            self._record(
                "macOS 兼容性",
                True,
                warn="macOS 下 keyboard 库需要辅助功能权限",
            )

    # ---- Python 版本检查 ----

    def _check_python_version(self):
        """检查 Python 版本是否在支持范围内"""
        print("\n--- Python 版本 ---")

        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"

        # 最低版本检查
        is_above_min = (version.major, version.minor) >= self.MIN_PYTHON_VERSION
        self._record(
            f"Python 版本: {version_str} (最低要求 {self.MIN_PYTHON_VERSION[0]}.{self.MIN_PYTHON_VERSION[1]})",
            is_above_min,
            f"Python 版本过低，需要 {self.MIN_PYTHON_VERSION[0]}.{self.MIN_PYTHON_VERSION[1]}+",
        )
        if not is_above_min:
            self._failed_categories.add("python_version")

        # 最高版本检查（警告级别）
        is_below_max = (version.major, version.minor) <= self.MAX_PYTHON_VERSION
        if not is_below_max:
            self._warnings.append(
                f"Python {version_str} 超出已测试范围 "
                f"(最高 {self.MAX_PYTHON_VERSION[0]}.{self.MAX_PYTHON_VERSION[1]})，"
                "可能存在兼容性问题"
            )

        # 检查是否为 64 位
        is_64bit = struct.calcsize("P") * 8 == 64
        self._record(
            f"Python 位数: {'64位' if is_64bit else '32位'}",
            is_64bit,
            "32位 Python 不支持大型模型加载",
        )

    # ---- 核心依赖检查 ----

    def _check_core_dependencies(self):
        """检查核心依赖是否已安装"""
        print("\n--- 核心依赖 ---")

        for package in self.CORE_DEPENDENCIES:
            try:
                mod = importlib.import_module(package)
                version = getattr(mod, "__version__", "未知版本")
                self._record(f"{package}: {version}", True)
            except ImportError:
                self._record(f"{package}: 未安装", False, f"缺少核心依赖: {package}")
                self._failed_categories.add("core_dependency")

    # ---- 可选依赖检查 ----

    def _check_optional_dependencies(self):
        """检查可选依赖"""
        print("\n--- 可选依赖 ---")

        for package in self.OPTIONAL_DEPENDENCIES:
            try:
                mod = importlib.import_module(package)
                version = getattr(mod, "__version__", "未知版本")
                self._record(f"[可选] {package}: {version}", True)
            except ImportError:
                self._record(
                    f"[可选] {package}: 未安装",
                    True,
                    warn=f"可选依赖 {package} 未安装，部分功能受限",
                )

    # ---- 音频设备检查 ----

    def _check_audio_devices(self):
        """检查音频设备可用性"""
        print("\n--- 音频设备 ---")

        try:
            import sounddevice as sd

            devices = sd.query_devices()
            input_devices = [
                d for i, d in enumerate(devices) if d["max_input_channels"] > 0
            ]

            if input_devices:
                default_input = sd.query_devices(kind="input")
                self._record(
                    f"音频输入设备: {len(input_devices)} 个可用 "
                    f"(默认: {default_input['name'][:30]})",
                    True,
                )
            else:
                self._record("音频输入设备: 无可用设备", False, "未检测到麦克风设备")
                self._failed_categories.add("audio_device")

        except Exception as e:
            self._record(f"音频设备检测失败: {e}", False, f"sounddevice 异常: {e}")
            self._failed_categories.add("audio_device")

    # ---- GPU 加速检查 ----

    def _check_gpu_acceleration(self):
        """检查 GPU 加速支持（NVIDIA/AMD/无 GPU）"""
        print("\n--- GPU 加速 ---")

        # 检测 NVIDIA GPU (CUDA)
        nvidia_ok = self._check_nvidia_gpu()

        # 检测 AMD GPU (ROCm)
        amd_ok = self._check_amd_gpu()

        # CPU 兜底
        if not nvidia_ok and not amd_ok:
            self._record(
                "[可选] CPU 推理模式: 可用 (无 GPU 加速)",
                True,
                warn="未检测到 GPU，将使用 CPU 推理（速度较慢但仍可正常工作）",
            )

    def _check_nvidia_gpu(self) -> bool:
        """检查 NVIDIA CUDA 支持"""
        # 方法1: 检查 CUDA 是否可用 (通过 PyTorch)
        try:
            import torch

            cuda_available = torch.cuda.is_available()
            if cuda_available:
                gpu_name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
                self._record(
                    f"NVIDIA GPU: {gpu_name} (VRAM: {vram:.1f}GB, CUDA: {torch.version.cuda})",
                    True,
                )
                return True
            else:
                self._record("[可选] NVIDIA CUDA: PyTorch 已安装但 CUDA 不可用", True)
        except ImportError:
            self._record("[可选] NVIDIA CUDA: PyTorch 未安装，跳过 CUDA 检测", True)

        # 方法2: 检查 nvidia-smi
        if self._command_exists("nvidia-smi"):
            self._record(
                "[可选] nvidia-smi: 可用 (但 PyTorch CUDA 未启用)",
                True,
                warn="nvidia-smi 存在但 PyTorch 未检测到 CUDA，可能需要安装 CUDA 版 PyTorch",
            )

        return False

    def _check_amd_gpu(self) -> bool:
        """检查 AMD ROCm 支持"""
        # 检查 ROCm
        try:
            import torch

            if hasattr(torch, "hip") and torch.hip.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                self._record(f"AMD GPU (ROCm): {gpu_name}", True)
                return True
        except (ImportError, AttributeError):
            pass

        # 检查 rocm-smi
        if self._command_exists("rocm-smi"):
            self._record("[可选] AMD ROCm: rocm-smi 可用", True)
            return True

        return False

    # ---- 文件权限检查 ----

    def _check_file_permissions(self):
        """检查文件读写权限"""
        print("\n--- 文件权限 ---")

        # 项目根目录
        project_root = self._get_project_root()

        # 检查项目目录是否可访问
        self._record(
            f"项目根目录: {project_root}",
            project_root.exists(),
            "无法访问项目根目录",
        )

        # 检查配置目录可写
        config_dir = Path(
            os.environ.get("APPDATA", os.path.expanduser("~")), "VoiceInput"
        )
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            test_file = config_dir / ".write_test"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            self._record(f"配置目录可写: {config_dir}", True)
        except Exception as e:
            self._record(
                f"配置目录可写: 否 ({e})", False, f"无法写入配置目录: {config_dir}"
            )

        # 检查模型缓存目录
        model_dir = config_dir / "models"
        try:
            model_dir.mkdir(parents=True, exist_ok=True)
            self._record(f"模型缓存目录: {model_dir}", True)
        except Exception as e:
            self._record(f"模型缓存目录: 失败 ({e})", False, str(e))

        # 检查 requirements.txt 存在
        req_file = project_root / "requirements.txt"
        self._record(
            f"requirements.txt: {'存在' if req_file.exists() else '缺失'}",
            req_file.exists(),
            "requirements.txt 缺失，无法安装依赖",
        )

    # ---- Whisper 推理检查 ----

    def _check_whisper_inference(self):
        """检查 Whisper 推理能力（CPU/GPU 模式）"""
        print("\n--- Whisper 推理 ---")

        try:
            import importlib.util

            if importlib.util.find_spec("faster_whisper") is None:
                raise ImportError("not installed")
        except (ImportError, ValueError):
            self._record("faster-whisper: 未安装，跳过推理测试", False)
            return

        # 检查是否已有模型缓存
        config_dir = Path(
            os.environ.get("APPDATA", os.path.expanduser("~")), "VoiceInput"
        )
        model_dir = config_dir / "models"

        # 查找已下载的模型
        available_models = []
        if model_dir.exists():
            for item in model_dir.iterdir():
                if item.is_dir() and item.name.startswith("models--"):
                    model_name = item.name.replace(
                        "models--Systran--faster-whisper-", ""
                    )
                    available_models.append(model_name)

        if not available_models:
            self._record(
                "Whisper 模型: 无已下载模型，跳过推理测试",
                True,
                warn="请先下载模型后重新运行验证",
            )
            return

        self._record(f"已下载模型: {', '.join(available_models)}", True)

        # 尝试加载最小模型进行推理测试
        test_model = "tiny" if "tiny" in available_models else available_models[0]
        self._test_whisper_load(test_model, str(model_dir))

    def _test_whisper_load(self, model_name: str, cache_dir: str):
        """测试 Whisper 模型加载和推理"""
        try:
            from faster_whisper import WhisperModel
            import numpy as np

            # 测试 CPU 推理
            start = time.time()
            model = WhisperModel(
                model_name, device="cpu", compute_type="int8", download_root=cache_dir
            )
            load_time = time.time() - start
            self._record(f"模型加载 ({model_name}, CPU/int8): {load_time:.2f}s", True)

            # 生成 1 秒静音进行测试推理
            silence = np.zeros(16000, dtype=np.float32)
            start = time.time()
            segments, info = model.transcribe(
                silence, language="zh", vad_filter=False, without_timestamps=True
            )
            # 消费迭代器
            _ = list(segments)
            infer_time = time.time() - start
            self._record(f"CPU 推理测试 (1s 静音): {infer_time:.2f}s", True)

            # 如果有 GPU，测试 GPU 推理
            try:
                import torch

                if torch.cuda.is_available():
                    start = time.time()
                    gpu_model = WhisperModel(
                        model_name,
                        device="cuda",
                        compute_type="float16",
                        download_root=cache_dir,
                    )
                    gpu_load_time = time.time() - start
                    self._record(
                        f"模型加载 ({model_name}, CUDA/float16): {gpu_load_time:.2f}s",
                        True,
                    )

                    segments, _ = gpu_model.transcribe(
                        silence,
                        language="zh",
                        vad_filter=False,
                        without_timestamps=True,
                    )
                    _ = list(segments)
                    gpu_infer_time = time.time() - start
                    self._record(f"GPU 推理测试 (1s 静音): {gpu_infer_time:.2f}s", True)
                    del gpu_model
            except ImportError:
                pass
            except Exception as e:
                self._record(
                    f"[可选] GPU 推理测试: 失败 ({e})",
                    True,
                    warn=f"GPU 推理失败，将回退到 CPU: {e}",
                )

            del model

        except Exception as e:
            self._record(
                f"Whisper 推理测试: 失败 ({e})",
                False,
                f"Whisper 推理异常: {e}",
            )
            self._failed_categories.add("whisper_inference")

    # ---- 辅助方法 ----

    def _record(self, message: str, passed: bool, error: str = None, warn: str = None):
        """记录检查结果"""
        is_optional = message.startswith("[可选]")
        prefix = "[可选]" if is_optional else "[必选]"

        if passed:
            if warn:
                status = "WARN"
                self._warnings.append(warn)
                print(f"  {prefix} {message} - {status}: {warn}")
            else:
                status = "PASS"
                print(f"  {prefix} {message} - {status}")
        else:
            status = "FAIL"
            print(f"  {prefix} {message} - {status}: {error}")

        self._results.append((message, error or warn or "", passed))

    def _print_summary(self):
        """打印汇总报告"""
        print("\n" + "=" * 60)
        print("验证汇总")
        print("=" * 60)

        required = [
            (m, e, ok) for m, e, ok in self._results if not m.startswith("[可选]")
        ]
        optional = [(m, e, ok) for m, e, ok in self._results if m.startswith("[可选]")]

        req_passed = sum(1 for _, _, ok in required if ok)
        req_failed = sum(1 for _, _, ok in required if not ok)

        print(f"必选检查: {req_passed} 通过 / {req_failed} 失败")
        print(
            f"可选检查: {sum(1 for _, _, ok in optional if ok)} 通过 / {sum(1 for _, _, ok in optional if not ok)} 跳过"
        )

        if self._warnings:
            print(f"\n警告 ({len(self._warnings)}):")
            for w in self._warnings:
                print(f"  - {w}")

        if req_failed == 0:
            print("\n结论: 所有必选检查通过，环境兼容")
        else:
            print(f"\n结论: {req_failed} 项必选检查失败，请修复后重试")
            for m, e, ok in required:
                if not ok:
                    print(f"  - {e}")

        print("=" * 60)

    def _print_solutions(self):
        """根据失败项输出对应的解决方案"""
        # 警告级别也提供解决方案（如 GPU cuBLAS 缺失、非管理员等）
        warn_categories: set[str] = set()
        for w in self._warnings:
            if "GPU" in w or "cuBLAS" in w or "cuda" in w.lower():
                warn_categories.add("gpu_inference")
            if "管理员" in w or "admin" in w.lower():
                warn_categories.add("hotkey_permission")

        all_categories = self._failed_categories | warn_categories

        if not all_categories:
            return

        print("\n" + "=" * 60)
        print("问题解决方案")
        print("=" * 60)

        for category in sorted(all_categories):
            solution = self.SOLUTIONS.get(category)
            if not solution:
                continue

            status = "失败" if category in self._failed_categories else "警告"
            print(f"\n[{status}] {solution['title']}:")
            for fix in solution["fix"]:
                print(f"  → {fix}")

        if not self._failed_categories:
            print("\n提示: 以上为警告级别建议，不影响基本功能运行")

        print("=" * 60)

    def generate_report(self) -> str:
        """生成一键环境报告，方便用户复制粘贴给开发者排查"""
        if not self._results:
            self.run_all_checks()

        lines: list[str] = []
        lines.append("===== 环境报告 =====")
        lines.append(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # 环境信息
        lines.append(
            f"OS: {platform.system()} {platform.version()} ({platform.machine()})"
        )
        lines.append(f"Python: {sys.version}")
        lines.append(f"可执行文件: {sys.executable}")

        # 核心依赖版本
        lines.append("")
        lines.append("--- 依赖 ---")
        for pkg in self.CORE_DEPENDENCIES:
            try:
                mod = importlib.import_module(pkg)
                ver = getattr(mod, "__version__", "已安装")
                lines.append(f"{pkg}: {ver}")
            except ImportError:
                lines.append(f"{pkg}: 未安装")

        for pkg in self.OPTIONAL_DEPENDENCIES:
            try:
                mod = importlib.import_module(pkg)
                ver = getattr(mod, "__version__", "已安装")
                lines.append(f"{pkg}: {ver} (可选)")
            except ImportError:
                lines.append(f"{pkg}: 未安装 (可选)")

        # GPU 信息
        lines.append("")
        lines.append("--- GPU ---")
        try:
            import torch

            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                lines.append(f"CUDA: {torch.version.cuda}")
                lines.append(
                    f"GPU: {props.name} ({props.total_memory / 1024**3:.1f}GB)"
                )
            else:
                lines.append("CUDA: 不可用 (CPU 模式)")
        except ImportError:
            lines.append("PyTorch: 未安装 (CPU 模式)")

        # 检查结果
        lines.append("")
        lines.append("--- 检测结果 ---")
        for msg, detail, ok in self._results:
            status = "OK" if ok else "FAIL"
            line = f"[{status}] {msg}"
            if detail and not ok:
                line += f" -> {detail}"
            lines.append(line)

        if self._warnings:
            lines.append("")
            lines.append("--- 警告 ---")
            for w in self._warnings:
                lines.append(f"  ! {w}")

        # 结论
        req_passed = sum(
            1 for m, _, ok in self._results if ok and not m.startswith("[可选]")
        )
        req_total = sum(1 for m, _, _ in self._results if not m.startswith("[可选]"))
        lines.append("")
        lines.append(f"结果: {req_passed}/{req_total} 必选检查通过")
        lines.append("==================")

        report = "\n".join(lines)
        return report

    @staticmethod
    def quick_test():
        """极简核心功能测试：加载模型 -> 模拟推理 -> 后处理"""
        print("===== 核心功能快速测试 =====")
        steps = [
            ("导入核心模块", "_test_imports"),
            ("加载 Whisper small 模型", "_test_model_load"),
            ("后处理规则引擎", "_test_post_processor"),
            ("热词管理器", "_test_hotword_manager"),
        ]

        passed = 0
        for name, method in steps:
            try:
                getattr(CompatibilityChecker, method)()
                print(f"  [OK] {name}")
                passed += 1
            except Exception as e:
                print(f"  [FAIL] {name}: {e}")

        print()
        if passed == len(steps):
            print(f"结果: {passed}/{len(steps)} 全部通过，核心功能正常!")
        else:
            print(
                f"结果: {passed}/{len(steps)} 通过，请运行 python scripts/verify_compatibility.py 详细检查"
            )
        print("==============================")

    @staticmethod
    def _test_imports():
        """测试核心模块能否导入"""
        importlib.import_module("faster_whisper")
        importlib.import_module("sounddevice")
        importlib.import_module("keyboard")
        importlib.import_module("pyperclip")

    @staticmethod
    def _test_model_load():
        """测试模型能否加载"""
        from faster_whisper import WhisperModel

        root = CompatibilityChecker._get_project_root()
        sys.path.insert(0, str(root))
        from config import Config

        config = Config()
        model_size = config.get("model_size", "small")
        cache_dir = str(config.model_cache_dir)

        # 通过 faster-whisper 的下载目录加载模型（会自动查找已缓存的模型）
        model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=cache_dir,
        )
        del model

    @staticmethod
    def _test_post_processor():
        """测试后处理规则引擎"""
        root = CompatibilityChecker._get_project_root()
        sys.path.insert(0, str(root))
        from engine.post_processor import ReplaceRule

        rule = ReplaceRule("chat GPT", "ChatGPT")
        result = rule.apply("使用chat GPT对话")
        assert "ChatGPT" in result, f"后处理规则未生效: {result}"

    @staticmethod
    def _test_hotword_manager():
        """测试热词管理器"""
        root = CompatibilityChecker._get_project_root()
        sys.path.insert(0, str(root))
        from engine.hotword_manager import HotwordManager

        # 不传文件路径，仅测试内存中的构建逻辑
        hw = HotwordManager()
        hw._global_hotwords = ["测试"]
        prompt = hw.build_initial_prompt(weight=1.0)
        assert prompt is not None and "测试" in prompt

    @staticmethod
    def _get_project_root() -> Path:
        """获取项目根目录"""
        current = Path(__file__).resolve()
        # 从 scripts/ 回溯到项目根
        for _ in range(3):
            current = current.parent
            if (current / "requirements.txt").exists():
                return current
        return Path.cwd()

    @staticmethod
    def _command_exists(cmd: str) -> bool:
        """检查系统命令是否可用"""
        import shutil

        return shutil.which(cmd) is not None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="语音输入法环境兼容性检查")
    parser.add_argument(
        "--report",
        action="store_true",
        help="运行完整检查后生成环境报告（复制粘贴给开发者排查问题）",
    )
    parser.add_argument(
        "--quick-test",
        action="store_true",
        help="快速测试核心功能（模型加载 + 后处理 + 热词）",
    )
    args = parser.parse_args()

    if args.quick_test:
        CompatibilityChecker.quick_test()
        sys.exit(0)

    checker = CompatibilityChecker()
    success = checker.run_all_checks()

    if args.report:
        report = checker.generate_report()
        print("\n" + report)
        # 复制到剪贴板
        try:
            import pyperclip

            pyperclip.copy(report)
            print("\n报告已复制到剪贴板，可直接粘贴发送给开发者")
        except Exception:
            pass

    sys.exit(0 if success else 1)
