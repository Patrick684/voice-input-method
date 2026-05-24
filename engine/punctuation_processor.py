"""智能标点识别模块 - 优化中文语音识别结果的标点符号"""

import re
from typing import Optional


class PunctuationProcessor:
    """中文标点优化处理器，修正 Whisper 识别结果中的标点问题"""

    # 英文标点到中文标点的映射
    EN_TO_ZH_PUNCT = {
        ".": "。",
        ",": "，",
        "!": "！",
        "?": "？",
        ";": "；",
        ":": "：",
        "(": "（",
        ")": "）",
    }

    # 中文疑问词列表（用于智能判断问号）
    QUESTION_WORDS = [
        "吗", "呢", "什么", "怎么", "为什么", "哪里", "哪个",
        "谁", "几", "多少", "是否", "能不能", "可以吗", "好不好",
        "对不对", "是不是", "有没有", "行不行",
    ]

    # 中文感叹词（用于智能判断感叹号）
    EXCLAMATION_WORDS = [
        "啊", "呀", "哇", "哦", "嗯", "嘿", "哎", "唉",
        "太棒了", "太好了", "厉害", "不错", "真好", "加油",
        "恭喜", "谢谢", "感谢",
    ]

    def __init__(
        self,
        auto_paragraph: bool = False,
        paragraph_threshold: int = 50,
    ):
        """
        初始化标点处理器

        Args:
            auto_paragraph: 是否自动分段
            paragraph_threshold: 自动分段字数阈值
        """
        self.auto_paragraph = auto_paragraph
        self.paragraph_threshold = paragraph_threshold

    def process(self, text: str, language: Optional[str] = "zh") -> str:
        """
        处理文本标点

        Args:
            text: 原始识别文本
            language: 语言 (zh/en)

        Returns:
            处理后的文本
        """
        if not text:
            return text

        if language == "zh" or language is None:
            text = self._process_chinese(text)

        return text

    def _process_chinese(self, text: str) -> str:
        """处理中文标点"""
        # 1. 英文标点转中文标点
        text = self._convert_punctuation(text)

        # 2. 修正重复标点
        text = self._fix_duplicate_punctuation(text)

        # 3. 智能补充句末标点
        text = self._add_sentence_ending(text)

        # 4. 修正标点前后空格
        text = self._fix_spacing(text)

        # 5. 自动分段
        if self.auto_paragraph:
            text = self._auto_paragraph(text)

        return text

    def _convert_punctuation(self, text: str) -> str:
        """将中文语境中的英文标点转换为中文标点"""
        result = []
        chars = list(text)

        for i, char in enumerate(chars):
            if char in self.EN_TO_ZH_PUNCT:
                # 判断是否在中文语境中
                if self._is_chinese_context(chars, i):
                    result.append(self.EN_TO_ZH_PUNCT[char])
                else:
                    result.append(char)
            else:
                result.append(char)

        return "".join(result)

    def _is_chinese_context(self, chars: list, pos: int) -> bool:
        """判断标点位置是否处于中文语境中"""
        # 检查前后字符是否为中文字符
        def is_chinese(c):
            return "\u4e00" <= c <= "\u9fff" or c in "，。！？；：""''（）"

        prev_chinese = False
        next_chinese = False

        if pos > 0:
            prev_chinese = is_chinese(chars[pos - 1])
        if pos < len(chars) - 1:
            next_chinese = is_chinese(chars[pos + 1])

        # 如果前后有中文字符，认为是中文语境
        return prev_chinese or next_chinese

    def _fix_duplicate_punctuation(self, text: str) -> str:
        """修正重复标点符号"""
        # 多个句号 -> 一个
        text = re.sub(r"[。]{2,}", "。", text)
        # 多个逗号 -> 一个
        text = re.sub(r"[，]{2,}", "，", text)
        # 多个感叹号保留最多一个（口语中多个感叹号通常是无意义的）
        text = re.sub(r"[！]{2,}", "！", text)
        # 多个问号保留最多一个
        text = re.sub(r"[？]{2,}", "？", text)
        return text

    def _add_sentence_ending(self, text: str) -> str:
        """智能补充句末标点"""
        text = text.strip()
        if not text:
            return text

        # 如果已经有句末标点，不处理
        if text[-1] in "。！？…":
            return text

        # 根据语义判断应添加的标点类型
        # 检查是否是疑问句
        for word in self.QUESTION_WORDS:
            if word in text:
                return text + "？"

        # 检查是否是感叹句
        for word in self.EXCLAMATION_WORDS:
            if word in text:
                return text + "！"

        # 默认添加句号
        return text + "。"

    def _fix_spacing(self, text: str) -> str:
        """修正标点前后的空格"""
        # 中文标点后不应有空格
        text = re.sub(r"([，。！？；：])\s+", r"\1", text)
        # 中文标号前不应有空格
        text = re.sub(r"\s+([，。！？；：])", r"\1", text)
        return text

    def _auto_paragraph(self, text: str) -> str:
        """根据句子长度自动分段"""
        # 按句号、感叹号、问号分割
        sentences = re.split(r"(?<=[。！？])", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            return text

        # 累积字数超过阈值时分段
        result = []
        current_paragraph = []
        char_count = 0

        for sentence in sentences:
            current_paragraph.append(sentence)
            char_count += len(sentence)

            if char_count >= self.paragraph_threshold:
                result.append("".join(current_paragraph))
                current_paragraph = []
                char_count = 0

        if current_paragraph:
            result.append("".join(current_paragraph))

        return "\n\n".join(result)
