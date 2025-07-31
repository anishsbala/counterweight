import json
from pathlib import Path
from typing import List

from app.config import DATA_DIR
from app.models import SourceRecord


class SourceBankLoader:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DATA_DIR / "source_bank.json"

    def load(self) -> List[SourceRecord]:
        raw_sources = json.loads(self.path.read_text(encoding="utf-8"))
        return [
            SourceRecord(
                slug=item["slug"],
                title=item["title"],
                url=item["url"],
                organization=item["organization"],
                domain=item["domain"],
                source_type=item.get("source_type", "report"),
                snippet=item["snippet"],
                tags=item["tags"],
                authority_score=float(item["authority_score"]),
            )
            for item in raw_sources
        ]
