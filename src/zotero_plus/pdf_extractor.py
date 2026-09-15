from __future__ import annotations

import json
from pathlib import Path

import fitz

from .models import AttachmentRecord, PdfTextRecord, PdfTocEntryRecord, PdfTocRecord


class PdfExtractionError(RuntimeError):
    """Raised when a PDF cannot be extracted."""


class PdfTextExtractor:
    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def extract_attachment(self, attachment: AttachmentRecord, force: bool = False) -> PdfTextRecord:
        if not attachment.local_path:
            raise PdfExtractionError(f"Attachment {attachment.key} does not have a local file path.")
        if not attachment.exists_locally:
            raise PdfExtractionError(f"Attachment {attachment.key} does not exist locally: {attachment.local_path}")

        cache_json_path = self._cache_dir / f"{attachment.key}.json"
        cache_text_path = self._cache_dir / f"{attachment.key}.txt"
        if not force and cache_json_path.exists() and cache_text_path.exists():
            payload = json.loads(cache_json_path.read_text(encoding="utf-8"))
            return PdfTextRecord(
                attachment_key=attachment.key,
                file_path=Path(payload["file_path"]),
                cache_json_path=cache_json_path,
                cache_text_path=cache_text_path,
                page_count=payload["page_count"],
                text_length=payload["text_length"],
                extracted=True,
                cached=True,
            )

        try:
            with fitz.open(attachment.local_path) as document:
                page_count = document.page_count
                text = "\n".join(page.get_text("text") for page in document).strip()
        except Exception as exc:
            raise PdfExtractionError(f"Failed to extract PDF '{attachment.local_path}': {exc}") from exc

        cache_text_path.write_text(text, encoding="utf-8")
        payload = {
            "attachment_key": attachment.key,
            "file_path": str(attachment.local_path),
            "page_count": page_count,
            "text_length": len(text),
        }
        cache_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return PdfTextRecord(
            attachment_key=attachment.key,
            file_path=attachment.local_path,
            cache_json_path=cache_json_path,
            cache_text_path=cache_text_path,
            page_count=page_count,
            text_length=len(text),
            extracted=True,
            cached=False,
        )

    def extract_toc(self, attachment: AttachmentRecord) -> PdfTocRecord:
        if not attachment.local_path:
            raise PdfExtractionError(f"Attachment {attachment.key} does not have a local file path.")
        if not attachment.exists_locally:
            raise PdfExtractionError(f"Attachment {attachment.key} does not exist locally: {attachment.local_path}")

        try:
            with fitz.open(attachment.local_path) as document:
                raw_toc = document.get_toc()
        except Exception as exc:
            raise PdfExtractionError(f"Failed to read PDF outline '{attachment.local_path}': {exc}") from exc

        toc = [
            PdfTocEntryRecord(
                level=int(level),
                title=str(title).strip(),
                page=max(int(page), 1),
            )
            for level, title, page in raw_toc
            if str(title).strip()
        ]
        return PdfTocRecord(
            attachment_key=attachment.key,
            file_path=attachment.local_path,
            toc=toc,
            toc_count=len(toc),
            has_toc=bool(toc),
        )
