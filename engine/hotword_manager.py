"""热词管理模块 - 支持自定义热词表提升识别准确率"""

import json
from pathlib import Path
from typing import List, Dict, Optional


class HotwordCategory:
    """热词分类"""

    def __init__(self, name: str, hotwords: Optional[List[str]] = None):
        self.name = name
        self.hotwords = hotwords or []

    def to_dict(self) -> dict:
        return {"name": self.name, "hotwords": self.hotwords}

    @classmethod
    def from_dict(cls, data: dict) -> "HotwordCategory":
        return cls(name=data["name"], hotwords=data.get("hotwords", []))


class HotwordManager:
    """热词管理器，管理用户自定义热词以提升 Whisper 识别准确率"""

    def __init__(self, hotword_file: Optional[str] = None):
        """
        初始化热词管理器

        Args:
            hotword_file: 热词持久化文件路径 (JSON)
        """
        self.hotword_file = Path(hotword_file) if hotword_file else None
        self._categories: Dict[str, HotwordCategory] = {}
        self._active_categories: List[str] = []
        self._global_hotwords: List[str] = []

        if self.hotword_file:
            self._load()

    def _load(self):
        """从文件加载热词"""
        if not self.hotword_file or not self.hotword_file.exists():
            return

        try:
            with open(self.hotword_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._global_hotwords = data.get("global_hotwords", [])
            self._active_categories = data.get("active_categories", [])

            for cat_data in data.get("categories", []):
                cat = HotwordCategory.from_dict(cat_data)
                self._categories[cat.name] = cat

        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"加载热词失败: {e}")

    def _save(self):
        """保存热词到文件"""
        if not self.hotword_file:
            return

        data = {
            "global_hotwords": self._global_hotwords,
            "active_categories": self._active_categories,
            "categories": [cat.to_dict() for cat in self._categories.values()],
        }

        try:
            self.hotword_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.hotword_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            print(f"保存热词失败: {e}")

    # ---- 全局热词管理 ----

    def add_global_hotword(self, word: str):
        """添加全局热词（所有场景生效）"""
        word = word.strip()
        if word and word not in self._global_hotwords:
            self._global_hotwords.append(word)
            self._save()

    def remove_global_hotword(self, word: str):
        """移除全局热词"""
        if word in self._global_hotwords:
            self._global_hotwords.remove(word)
            self._save()

    def get_global_hotwords(self) -> List[str]:
        """获取所有全局热词"""
        return list(self._global_hotwords)

    # ---- 分类热词管理 ----

    def create_category(self, name: str) -> HotwordCategory:
        """创建热词分类"""
        if name not in self._categories:
            self._categories[name] = HotwordCategory(name)
            self._save()
        return self._categories[name]

    def delete_category(self, name: str):
        """删除热词分类"""
        if name in self._categories:
            del self._categories[name]
            if name in self._active_categories:
                self._active_categories.remove(name)
            self._save()

    def add_hotword(self, category: str, word: str):
        """向指定分类添加热词"""
        if category not in self._categories:
            self.create_category(category)

        word = word.strip()
        if word and word not in self._categories[category].hotwords:
            self._categories[category].hotwords.append(word)
            self._save()

    def remove_hotword(self, category: str, word: str):
        """从指定分类移除热词"""
        if category in self._categories:
            cat = self._categories[category]
            if word in cat.hotwords:
                cat.hotwords.remove(word)
                self._save()

    def get_categories(self) -> List[str]:
        """获取所有分类名称"""
        return list(self._categories.keys())

    def get_hotwords(self, category: str) -> List[str]:
        """获取指定分类的热词"""
        if category in self._categories:
            return list(self._categories[category].hotwords)
        return []

    # ---- 激活/停用分类 ----

    def activate_category(self, name: str):
        """激活热词分类"""
        if name in self._categories and name not in self._active_categories:
            self._active_categories.append(name)
            self._save()

    def deactivate_category(self, name: str):
        """停用热词分类"""
        if name in self._active_categories:
            self._active_categories.remove(name)
            self._save()

    def get_active_categories(self) -> List[str]:
        """获取已激活的分类"""
        return list(self._active_categories)

    # ---- Whisper initial_prompt 生成 ----

    def build_initial_prompt(self, weight: float = 1.5) -> Optional[str]:
        """
        构建 Whisper 的 initial_prompt 字符串

        通过 initial_prompt 参数注入热词上下文，可以显著提升
        特定词汇（人名、术语、地名等）的识别准确率。

        Args:
            weight: 热词权重（通过重复次数体现）

        Returns:
            initial_prompt 字符串，如果没有热词则返回 None
        """
        all_hotwords = list(self._global_hotwords)

        # 添加已激活分类的热词
        for cat_name in self._active_categories:
            if cat_name in self._categories:
                all_hotwords.extend(self._categories[cat_name].hotwords)

        if not all_hotwords:
            return None

        # 去重
        all_hotwords = list(dict.fromkeys(all_hotwords))

        # 构建 prompt：重复热词以增加权重
        # Whisper 对 initial_prompt 中的词汇有更高识别倾向
        repeat_count = max(1, int(weight))
        prompt_words = []
        for word in all_hotwords:
            prompt_words.extend([word] * repeat_count)

        # 用逗号分隔，Whisper 对这种格式识别效果好
        prompt = "，".join(prompt_words)
        return prompt

    # ---- 导入/导出 ----

    def export_hotwords(self, filepath: str, format: str = "json"):
        """
        导出热词到文件

        Args:
            filepath: 导出文件路径
            format: 导出格式 (json/txt)
        """
        if format == "json":
            data = {
                "global_hotwords": self._global_hotwords,
                "categories": {
                    name: cat.hotwords
                    for name, cat in self._categories.items()
                },
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        elif format == "txt":
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("# 全局热词\n")
                for word in self._global_hotwords:
                    f.write(f"{word}\n")
                f.write("\n")
                for name, cat in self._categories.items():
                    f.write(f"# [{name}]\n")
                    for word in cat.hotwords:
                        f.write(f"{word}\n")
                    f.write("\n")

    def import_hotwords(self, filepath: str, format: str = "json"):
        """
        从文件导入热词

        Args:
            filepath: 导入文件路径
            format: 导入格式 (json/txt)
        """
        if format == "json":
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._global_hotwords.extend(data.get("global_hotwords", []))
            self._global_hotwords = list(dict.fromkeys(self._global_hotwords))

            for cat_name, words in data.get("categories", {}).items():
                if cat_name not in self._categories:
                    self.create_category(cat_name)
                for word in words:
                    if word not in self._categories[cat_name].hotwords:
                        self._categories[cat_name].hotwords.append(word)

        elif format == "txt":
            current_category = None
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        if line.startswith("# [") and line.endswith("]"):
                            current_category = line[3:-1]
                            self.create_category(current_category)
                        continue
                    if current_category:
                        self.add_hotword(current_category, line)
                    else:
                        self.add_global_hotword(line)

        self._save()
