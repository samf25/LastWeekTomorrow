from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RankedPaper:
    rank: int
    arxiv_id: str
    category: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "arxiv_id": self.arxiv_id,
            "category": self.category,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RankedPaper":
        return cls(
            rank=int(data["rank"]),
            arxiv_id=str(data["arxiv_id"]),
            category=str(data.get("category", "")),
            score=float(data.get("score", 0.0)),
        )


@dataclass(slots=True)
class RunManifest:
    run_date: str
    source_message_id: str | None = None
    extracted_at_utc: str | None = None
    papers: list[RankedPaper] = field(default_factory=list)
    selected_ids: list[str] = field(default_factory=list)
    downloaded_files: list[str] = field(default_factory=list)
    notebook_url: str | None = None
    notebook_id: str | None = None
    notebook_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_date": self.run_date,
            "source_message_id": self.source_message_id,
            "extracted_at_utc": self.extracted_at_utc,
            "papers": [paper.to_dict() for paper in self.papers],
            "selected_ids": list(self.selected_ids),
            "downloaded_files": list(self.downloaded_files),
            "notebook_url": self.notebook_url,
            "notebook_id": self.notebook_id,
            "notebook_status": self.notebook_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunManifest":
        return cls(
            run_date=str(data["run_date"]),
            source_message_id=data.get("source_message_id"),
            extracted_at_utc=data.get("extracted_at_utc"),
            papers=[RankedPaper.from_dict(p) for p in data.get("papers", [])],
            selected_ids=[str(v) for v in data.get("selected_ids", [])],
            downloaded_files=[str(v) for v in data.get("downloaded_files", [])],
            notebook_url=data.get("notebook_url"),
            notebook_id=data.get("notebook_id"),
            notebook_status=data.get("notebook_status"),
        )
