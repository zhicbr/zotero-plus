from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .models import AnalysisSummaryRecord, AttachmentContextRecord


class AnalysisSummaryStore:
    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def save_summary(
        self,
        context: AttachmentContextRecord,
        requirement: str,
        verdict: str,
        summary: str,
        evidence: list[str] | None = None,
        pdf_cache_text_path: Path | None = None,
        pdf_cache_json_path: Path | None = None,
    ) -> AnalysisSummaryRecord:
        normalized_requirement = self._normalize_requirement(requirement)
        if not normalized_requirement:
            raise ValueError("Requirement must not be empty.")

        normalized_summary = summary.strip()
        if not normalized_summary:
            raise ValueError("Summary must not be empty.")

        fingerprint = self.requirement_fingerprint(requirement)
        storage_path = self._summary_path(context.attachment.key, fingerprint)
        timestamp = self._now_iso()
        created_at = timestamp
        if storage_path.exists():
            created_at = self._load_from_path(storage_path).created_at or timestamp

        record = AnalysisSummaryRecord(
            attachment_key=context.attachment.key,
            attachment_title=context.attachment.title,
            paper_key=context.paper.key,
            paper_title=context.paper.title,
            year=context.paper.year,
            authors=context.paper.authors,
            collection_keys=context.paper.collection_keys,
            requirement=requirement.strip(),
            requirement_fingerprint=fingerprint,
            verdict=verdict,
            summary=normalized_summary,
            evidence=[item.strip() for item in (evidence or []) if item.strip()],
            source_pdf_path=context.attachment.local_path,
            pdf_cache_text_path=pdf_cache_text_path,
            pdf_cache_json_path=pdf_cache_json_path,
            storage_path=storage_path,
            created_at=created_at,
            updated_at=timestamp,
        )

        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_text(
            json.dumps(asdict(record), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return record

    def list_summaries(
        self,
        collection_key: str | None = None,
        attachment_key: str | None = None,
        requirement: str | None = None,
        search: str | None = None,
    ) -> list[AnalysisSummaryRecord]:
        records = [self._load_from_path(path) for path in sorted(self._cache_dir.glob("*/*.json"))]

        if collection_key:
            records = [record for record in records if collection_key in record.collection_keys]
        if attachment_key:
            records = [record for record in records if record.attachment_key == attachment_key]
        if requirement:
            target = self._normalize_requirement(requirement)
            records = [
                record
                for record in records
                if self._normalize_requirement(record.requirement) == target
            ]
        if search:
            normalized_search = search.casefold()
            records = [
                record
                for record in records
                if normalized_search in record.requirement.casefold()
                or normalized_search in record.summary.casefold()
                or any(normalized_search in evidence.casefold() for evidence in record.evidence)
            ]
        return sorted(records, key=lambda record: (record.updated_at, record.attachment_key), reverse=True)

    @staticmethod
    def requirement_fingerprint(requirement: str) -> str:
        normalized = AnalysisSummaryStore._normalize_requirement(requirement)
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]

    def _summary_path(self, attachment_key: str, requirement_fingerprint: str) -> Path:
        return self._cache_dir / attachment_key / f"{requirement_fingerprint}.json"

    @staticmethod
    def _normalize_requirement(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().casefold()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat()

    @staticmethod
    def _load_from_path(path: Path) -> AnalysisSummaryRecord:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return AnalysisSummaryRecord(
            attachment_key=payload["attachment_key"],
            attachment_title=payload["attachment_title"],
            paper_key=payload["paper_key"],
            paper_title=payload["paper_title"],
            year=payload.get("year"),
            authors=payload.get("authors", []),
            collection_keys=payload.get("collection_keys", []),
            requirement=payload["requirement"],
            requirement_fingerprint=payload["requirement_fingerprint"],
            verdict=payload["verdict"],
            summary=payload["summary"],
            evidence=payload.get("evidence", []),
            source_pdf_path=Path(payload["source_pdf_path"]) if payload.get("source_pdf_path") else None,
            pdf_cache_text_path=Path(payload["pdf_cache_text_path"]) if payload.get("pdf_cache_text_path") else None,
            pdf_cache_json_path=Path(payload["pdf_cache_json_path"]) if payload.get("pdf_cache_json_path") else None,
            storage_path=Path(payload["storage_path"]) if payload.get("storage_path") else path,
            created_at=payload.get("created_at", ""),
            updated_at=payload.get("updated_at", ""),
        )
