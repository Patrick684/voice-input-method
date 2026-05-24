"""语义表情符号识别模块 - 根据语音内容自动添加 emoji"""

import re
from typing import Optional, List


class EmojiRule:
    """Emoji 匹配规则"""

    def __init__(
        self,
        keywords: List[str],
        emoji: str,
        priority: int = 0,
    ):
        """
        Args:
            keywords: 触发关键词列表
            emoji: 对应的 emoji
            priority: 优先级（越高越优先）
        """
        self.keywords = keywords
        self.emoji = emoji
        self.priority = priority


class EmojiInjector:
    """
    语义表情符号注入器

    基于规则引擎分析文本语义，在合适位置自动插入 emoji。
    支持三种密度模式: low（少量）, medium（适量）, high（丰富）
    """

    # Emoji 规则库（按语义分类）
    RULES = [
        # 情感 - 开心
        EmojiRule(
            ["开心", "高兴", "快乐", "愉快", "幸福", "兴奋", "哈哈", "嘻嘻"],
            "😊",
            priority=2,
        ),
        # 情感 - 悲伤
        EmojiRule(
            ["难过", "伤心", "悲伤", "哭", "失望", "沮丧", "郁闷", "呜呜"],
            "😢",
            priority=2,
        ),
        # 情感 - 生气
        EmojiRule(
            ["生气", "愤怒", "气死", "火大", "讨厌", "烦人"],
            "😡",
            priority=2,
        ),
        # 情感 - 惊讶
        EmojiRule(
            ["惊讶", "震惊", "天哪", "我的天", "不会吧", "真的吗", "啊"],
            "😮",
            priority=1,
        ),
        # 情感 - 喜爱
        EmojiRule(
            ["喜欢", "爱", "心动", "迷恋", "好爱", "太爱"],
            "❤️",
            priority=2,
        ),
        # 鼓励
        EmojiRule(
            ["加油", "努力", "坚持", "奋斗", "拼搏", "冲冲冲"],
            "💪",
            priority=2,
        ),
        # 赞同
        EmojiRule(
            ["好的", "可以", "没问题", "行", "赞同", "同意", "没错"],
            "👍",
            priority=1,
        ),
        # 感谢
        EmojiRule(
            ["谢谢", "感谢", "多谢", "感恩", "太感谢"],
            "🙏",
            priority=2,
        ),
        # 道歉
        EmojiRule(
            ["抱歉", "对不起", "不好意思", "sorry"],
            "🙇",
            priority=2,
        ),
        # 赞美
        EmojiRule(
            ["厉害", "棒", "优秀", "厉害了我的", "太强了", "牛", "大佬"],
            "👏",
            priority=1,
        ),
        # 思考
        EmojiRule(
            ["想想", "考虑", "思考", "嗯", "让我想", "琢磨"],
            "🤔",
            priority=1,
        ),
        # 庆祝
        EmojiRule(
            ["恭喜", "祝贺", "庆祝", "万岁", "太棒了", "耶"],
            "🎉",
            priority=2,
        ),
        # 食物
        EmojiRule(
            ["吃饭", "美食", "好吃", "饭", "火锅", "烧烤", "奶茶", "咖啡"],
            "🍽️",
            priority=1,
        ),
        # 工作
        EmojiRule(
            ["工作", "上班", "加班", "开会", "项目", "需求", "deadline"],
            "💼",
            priority=1,
        ),
        # 学习
        EmojiRule(
            ["学习", "考试", "作业", "论文", "研究", "读书"],
            "📚",
            priority=1,
        ),
        # 天气 - 晴天
        EmojiRule(
            ["天气好", "晴天", "太阳", "阳光", "暖和"],
            "☀️",
            priority=1,
        ),
        # 天气 - 雨天
        EmojiRule(
            ["下雨", "雨天", "暴雨", "淋雨", "打伞"],
            "🌧️",
            priority=1,
        ),
        # 睡眠
        EmojiRule(
            ["睡觉", "晚安", "困了", "累了想睡", "好困"],
            "😴",
            priority=1,
        ),
        # 旅行
        EmojiRule(
            ["旅游", "旅行", "出去玩", "度假", "风景", "景点"],
            "✈️",
            priority=1,
        ),
        # 金钱
        EmojiRule(
            ["赚钱", "工资", "发财", "红包", "奖金", "涨薪"],
            "💰",
            priority=1,
        ),
        # 音乐
        EmojiRule(
            ["音乐", "唱歌", "听歌", "好听", "歌曲", "旋律"],
            "🎵",
            priority=1,
        ),
        # 运动
        EmojiRule(
            ["跑步", "健身", "运动", "打球", "游泳", "篮球", "足球"],
            "🏃",
            priority=1,
        ),
        # 时间 - 早上
        EmojiRule(
            ["早上好", "早安", "起床", "清晨", "早晨"],
            "🌅",
            priority=1,
        ),
        # 时间 - 晚上
        EmojiRule(
            ["晚上好", "晚安", "夜晚", "月亮"],
            "🌙",
            priority=1,
        ),
    ]

    # 密度配置: 每 N 个句子允许插入一个 emoji
    DENSITY_CONFIG = {
        "low": {"max_per_text": 1, "min_sentences": 3},
        "medium": {"max_per_text": 2, "min_sentences": 2},
        "high": {"max_per_text": 5, "min_sentences": 1},
    }

    def __init__(
        self,
        enabled: bool = True,
        density: str = "medium",
    ):
        """
        初始化 Emoji 注入器

        Args:
            enabled: 是否启用
            density: emoji 密度 (low/medium/high)
        """
        self.enabled = enabled
        self.density = density

        # 构建关键词索引（加速匹配）
        self._keyword_index: dict = {}
        for rule in self.RULES:
            for keyword in rule.keywords:
                if keyword not in self._keyword_index:
                    self._keyword_index[keyword] = []
                self._keyword_index[keyword].append(rule)

    def process(self, text: str) -> str:
        """
        处理文本，在合适位置插入 emoji

        Args:
            text: 原始文本

        Returns:
            插入 emoji 后的文本
        """
        if not self.enabled or not text:
            return text

        density_config = self.DENSITY_CONFIG.get(
            self.density, self.DENSITY_CONFIG["medium"]
        )

        # 按句子分割
        sentences = self._split_sentences(text)

        # 为每个句子匹配 emoji
        results = []
        emoji_count = 0
        max_emojis = density_config["max_per_text"]

        for sentence in sentences:
            if not sentence.strip():
                results.append(sentence)
                continue

            if emoji_count >= max_emojis:
                results.append(sentence)
                continue

            matched_emoji = self._match_emoji(sentence)
            if matched_emoji:
                # 在句末标点前插入 emoji
                sentence = self._insert_emoji(sentence, matched_emoji)
                emoji_count += 1

            results.append(sentence)

        return "".join(results)

    def _split_sentences(self, text: str) -> List[str]:
        """将文本分割为句子（保留标点）"""
        # 使用正则分割，保留标点
        parts = re.split(r"(?<=[。！？；\n])", text)
        return [p for p in parts if p]

    def _match_emoji(self, sentence: str) -> Optional[str]:
        """为句子匹配最合适的 emoji"""
        matched_rules: List[EmojiRule] = []

        for keyword, rules in self._keyword_index.items():
            if keyword in sentence:
                matched_rules.extend(rules)

        if not matched_rules:
            return None

        # 按优先级排序，选择最高优先级的
        matched_rules.sort(key=lambda r: r.priority, reverse=True)
        return matched_rules[0].emoji

    def _insert_emoji(self, sentence: str, emoji: str) -> str:
        """在句子中合适位置插入 emoji"""
        sentence = sentence.rstrip()

        # 在句末标点之前插入
        if sentence and sentence[-1] in "。！？；":
            return sentence[:-1] + emoji + sentence[-1]

        # 没有句末标点则追加
        return sentence + emoji

    def set_density(self, density: str):
        """设置 emoji 密度"""
        if density in self.DENSITY_CONFIG:
            self.density = density

    def add_custom_rule(self, keywords: List[str], emoji: str, priority: int = 1):
        """
        添加自定义 emoji 规则

        Args:
            keywords: 触发关键词
            emoji: 对应的 emoji
            priority: 优先级
        """
        rule = EmojiRule(keywords, emoji, priority)
        self.RULES.append(rule)

        # 更新索引
        for keyword in keywords:
            if keyword not in self._keyword_index:
                self._keyword_index[keyword] = []
            self._keyword_index[keyword].append(rule)
