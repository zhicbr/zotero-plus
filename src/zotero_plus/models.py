from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CollectionRecord:
    id: int
    key: str
    name: str
    parent_id: int | None
    parent_key: str | None
    parent_name: str | None
    path: str
    path_keys: list[str] = field(default_factory=list)
    depth: int = 0
    item_count: int = 0


@dataclass(slots=True)
class AttachmentRecord:
    item_id: int
    parent_item_id: int | None
    key: str
    title: str
    content_type: str | None
    link_mode: int | None
    path: str | None
    local_path: Path | None
    is_pdf: bool
    exists_locally: bool


@dataclass(slots=True)
class PaperRecord:
    item_id: int
    key: str
    item_type: str
    title: str
    year: str | None
    abstract: str | None = None
    doi: str | None = None
    authors: list[str] = field(default_factory=list)
    collection_keys: list[str] = field(default_factory=list)
    attachments: list[AttachmentRecord] = field(default_factory=list)


@dataclass(slots=True)
class PdfTextRecord:
    attachment_key: str
    file_path: Path
    cache_json_path: Path
    cache_text_path: Path
    page_count: int
    text_length: int
    extracted: bool
    cached: bool
    error: str | None = None


@dataclass(slots=True)
class PdfTocEntryRecord:
    level: int
    title: str
    page: int


@dataclass(slots=True)
class PdfTocRecord:
    attachment_key: str
    file_path: Path
    toc: list[PdfTocEntryRecord] = field(default_factory=list)
    toc_count: int = 0
    has_toc: bool = False


@dataclass(slots=True)
class AttachmentContextRecord:
    paper: PaperRecord
    attachment: AttachmentRecord


@dataclass(slots=True)
class AnalysisSummaryRecord:
    attachment_key: str
    attachment_title: str
    paper_key: str
    paper_title: str
    year: str | None
    authors: list[str] = field(default_factory=list)
    collection_keys: list[str] = field(default_factory=list)
    requirement: str = ""
    requirement_fingerprint: str = ""
    verdict: str = ""
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    source_pdf_path: Path | None = None
    pdf_cache_text_path: Path | None = None
    pdf_cache_json_path: Path | None = None
    storage_path: Path | None = None
    created_at: str = ""
    updated_at: str = ""
