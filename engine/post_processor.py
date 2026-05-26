"""后处理规则引擎 - 对语音识别结果进行文本替换修正"""

import json
import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class ReplaceRule:
    """单条替换规则"""

    def __init__(
        self,
        pattern: str,
        replacement: str,
        is_regex: bool = False,
        enabled: bool = True,
    ):
        """
        初始化替换规则

        Args:
            pattern: 匹配模式（纯文本或正则表达式）
            replacement: 替换文本
            is_regex: 是否为正则模式
            enabled: 是否启用
        """
        self.pattern = pattern
        self.replacement = replacement
        self.is_regex = is_regex
        self.enabled = enabled
        # 预编译正则（如果有）
        self._compiled = None
        if is_regex:
            try:
                self._compiled = re.compile(pattern)
            except re.error:
                logger.warning(f"正则编译失败: {pattern}")

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "pattern": self.pattern,
            "replacement": self.replacement,
            "is_regex": self.is_regex,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReplaceRule":
        """从字典反序列化"""
        return cls(
            pattern=data["pattern"],
            replacement=data["replacement"],
            is_regex=data.get("is_regex", False),
            enabled=data.get("enabled", True),
        )

    def apply(self, text: str) -> str:
        """
        对文本应用本条规则

        Args:
            text: 输入文本

        Returns:
            替换后的文本
        """
        if not self.enabled:
            return text

        if self.is_regex and self._compiled:
            return self._compiled.sub(self.replacement, text)
        else:
            return text.replace(self.pattern, self.replacement)


class PostProcessor:
    """后处理规则引擎，管理替换规则并应用到识别结果"""

    # 预置规则（覆盖 Whisper 常见中文识别错误）
    BUILTIN_RULES: List[dict] = [
        {"pattern": "拍touch", "replacement": "PyTorch"},
        {"pattern": "拍touch", "replacement": "PyTorch"},
        {"pattern": "ten so floor", "replacement": "TensorFlow"},
        {"pattern": "tenso floor", "replacement": "TensorFlow"},
        {"pattern": "VS code", "replacement": "VSCode"},
        {"pattern": "V S code", "replacement": "VSCode"},
        {"pattern": "chat GPT", "replacement": "ChatGPT"},
        {"pattern": "chat G P T", "replacement": "ChatGPT"},
        {"pattern": "GitHub", "replacement": "GitHub"},
        {"pattern": "get hub", "replacement": "GitHub"},
        {"pattern": "git hub", "replacement": "GitHub"},
    ]

    def __init__(self, rules_file: Optional[str] = None):
        """
        初始化后处理器

        Args:
            rules_file: 规则持久化文件路径 (JSON)
        """
        self.rules_file = Path(rules_file) if rules_file else None
        self._rules: List[ReplaceRule] = []
        self._builtin_enabled: bool = True

        if self.rules_file:
            self._load()
        else:
            self._load_builtin_defaults()

    def _load_builtin_defaults(self):
        """加载预置规则"""
        self._rules = [ReplaceRule.from_dict(r) for r in self.BUILTIN_RULES]

    def _load(self):
        """从文件加载规则"""
        if not self.rules_file or not self.rules_file.exists():
            self._load_builtin_defaults()
            return

        try:
            with open(self.rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._builtin_enabled = data.get("builtin_enabled", True)
            self._rules = []

            # 加载预置规则（如果启用）
            if self._builtin_enabled:
                for rule_data in self.BUILTIN_RULES:
                    self._rules.append(ReplaceRule.from_dict(rule_data))

            # 加载用户自定义规则
            for rule_data in data.get("rules", []):
                self._rules.append(ReplaceRule.from_dict(rule_data))

        except (json.JSONDecodeError, IOError, KeyError) as e:
            logger.warning(f"加载后处理规则失败: {e}")
            self._load_builtin_defaults()

    def _save(self):
        """保存规则到文件"""
        if not self.rules_file:
            return

        # 只保存用户自定义规则（预置规则不持久化）
        user_rules = []
        builtin_count = len(self.BUILTIN_RULES) if self._builtin_enabled else 0
        for rule in self._rules[builtin_count:]:
            user_rules.append(rule.to_dict())

        data = {
            "builtin_enabled": self._builtin_enabled,
            "rules": user_rules,
        }

        try:
            self.rules_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.rules_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f"保存后处理规则失败: {e}")

    # ---- 规则管理 ----

    def add_rule(
        self, pattern: str, replacement: str, is_regex: bool = False
    ) -> ReplaceRule:
        """
        添加用户自定义规则

        Args:
            pattern: 匹配模式
            replacement: 替换文本
            is_regex: 是否为正则

        Returns:
            新建的规则对象
        """
        rule = ReplaceRule(pattern, replacement, is_regex=is_regex)
        self._rules.append(rule)
        self._save()
        return rule

    def remove_rule(self, index: int):
        """删除指定索引的规则"""
        builtin_count = len(self.BUILTIN_RULES) if self._builtin_enabled else 0
        if index >= builtin_count and index < len(self._rules):
            self._rules.pop(index)
            self._save()

    def get_rules(self) -> List[ReplaceRule]:
        """获取所有规则（含预置）"""
        return list(self._rules)

    def get_user_rules(self) -> List[ReplaceRule]:
        """仅获取用户自定义规则"""
        builtin_count = len(self.BUILTIN_RULES) if self._builtin_enabled else 0
        return list(self._rules[builtin_count:])

    def set_builtin_enabled(self, enabled: bool):
        """切换预置规则开关"""
        if enabled == self._builtin_enabled:
            return
        self._builtin_enabled = enabled
        # 重新加载规则列表
        user_rules = self.get_user_rules()
        self._rules = []
        if enabled:
            for rule_data in self.BUILTIN_RULES:
                self._rules.append(ReplaceRule.from_dict(rule_data))
        self._rules.extend(user_rules)
        self._save()

    @property
    def builtin_enabled(self) -> bool:
        """预置规则是否启用"""
        return self._builtin_enabled

    def enable_rule(self, index: int):
        """启用指定规则"""
        if 0 <= index < len(self._rules):
            self._rules[index].enabled = True
            self._save()

    def disable_rule(self, index: int):
        """禁用指定规则"""
        if 0 <= index < len(self._rules):
            self._rules[index].enabled = False
            self._save()

    # ---- 文本处理 ----

    def process(self, text: str) -> str:
        """
        对文本依次应用所有启用的替换规则

        Args:
            text: 原始识别文本

        Returns:
            处理后的文本
        """
        if not text:
            return text

        original = text
        for rule in self._rules:
            text = rule.apply(text)

        if text != original:
            logger.info(f"后处理修正: '{original[:30]}' -> '{text[:30]}'")

        return text
