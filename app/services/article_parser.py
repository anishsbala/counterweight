import re
from typing import List


class ArticleParser:
    def __init__(self) -> None:
        self._split_pattern = re.compile(r"(?<=[.!?])\s+")

    def split_sentences(self, article_text: str) -> List[str]:
        text = self._normalize_text(article_text)
        parts = [piece.strip() for piece in self._split_pattern.split(text) if piece.strip()]
        merged: List[str] = []
        for part in parts:
            if merged and len(part.split()) < 5:
                merged[-1] = f"{merged[-1]} {part}".strip()
            else:
                merged.append(part)
        return merged

    def _normalize_text(self, article_text: str) -> str:
        text = article_text.replace("\r", " ").replace("\n", " ")
        text = text.replace("“", '"').replace("”", '"').replace("’", "'")
        text = re.sub(r"\[[^\]]+\]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
