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


@dataclass(slots=True)
class FilterDecision:
    matched: bool
    reasons: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)


@dataclass(slots=True)
class KeywordHitRecord:
    keyword: str
    count: int
    snippets: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PdfSearchHitRecord:
    attachment_key: str
    attachment_title: str
    total_hits: int
    hits: list[KeywordHitRecord] = field(default_factory=list)


@dataclass(slots=True)
class PaperSearchRecord:
    paper_key: str
    title: str
    year: str | None
    authors: list[str] = field(default_factory=list)
    matched: bool = False
    total_hits: int = 0
    hit_keywords: list[str] = field(default_factory=list)
    abstract_hits: list[KeywordHitRecord] = field(default_factory=list)
    pdf_hits: list[PdfSearchHitRecord] = field(default_factory=list)
    pdf_cache_status: str = "no_pdf"  # "cached" | "not_cached" | "no_pdf"
    excluded: bool = False
    exclude_reason: str | None = None


@dataclass(slots=True)
class CollectionReadinessRecord:
    collection_key: str
    collection_name: str
    collection_path: str
    is_recursive: bool
    subcollection_count: int
    total_papers: int
    papers_with_pdf: int
    papers_without_pdf: int
    papers_with_abstract: int
    total_pdf_attachments: int
    local_pdf_attachments: int
    missing_pdf_attachments: int
    cached_pdf_texts: int
    uncached_pdf_texts: int
    total_analysis_summaries: int
    analyzed_papers_count: int
    cache_percentage: float
    status: str  # "ready" | "partially_cached" | "no_cache" | "empty"
    suggestions: list[str] = field(default_factory=list)
    uncached_attachments: list[dict[str, str]] = field(default_factory=list)
