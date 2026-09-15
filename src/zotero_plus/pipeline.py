from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from .models import AttachmentRecord, PdfTextRecord
from .pdf_extractor import PdfExtractionError, PdfTextExtractor
from .zotero_client import ZoteroLibrary


def collect_pdf_attachments(library: ZoteroLibrary, collection_key: str) -> list[AttachmentRecord]:
    return [attachment for attachment in library.list_collection_attachments(collection_key) if attachment.is_pdf]


def extract_collection_pdfs(
    library: ZoteroLibrary,
    extractor: PdfTextExtractor,
    collection_key: str,
    force: bool = False,
) -> list[PdfTextRecord]:
    results: list[PdfTextRecord] = []
    for attachment in collect_pdf_attachments(library, collection_key):
        try:
            results.append(extractor.extract_attachment(attachment, force=force))
        except PdfExtractionError as exc:
            results.append(
                PdfTextRecord(
                    attachment_key=attachment.key,
                    file_path=attachment.local_path or Path("<missing>"),
                    cache_json_path=extractor.cache_dir / f"{attachment.key}.json",
                    cache_text_path=extractor.cache_dir / f"{attachment.key}.txt",
                    page_count=0,
                    text_length=0,
                    extracted=False,
                    cached=False,
                    error=str(exc),
                )
            )
    return results


def save_json(payload: object, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def to_dicts(records: list[object]) -> list[dict]:
    return [asdict(record) for record in records]


def build_export_data(library: ZoteroLibrary, collection_keys: list[str]) -> list[dict]:
    collections = {c.key: c for c in library.list_collections()}
    data: list[dict] = []
    for key in collection_keys:
        collection = collections.get(key)
        if not collection:
            raise ValueError(f"Collection not found: {key}")
        papers = []
        for paper in library.list_collection_items(key):
            entry: dict[str, object] = {"title": paper.title, "abstract": paper.abstract}
            if paper.year:
                entry["year"] = paper.year
            papers.append(entry)
        data.append({"collection_path": collection.path, "papers": papers})
    return data


def format_abstracts_md(data: list[dict]) -> str:
    parts: list[str] = []
    for group in data:
        parts.append(f"# {group['collection_path']}")
        parts.append("")
        for paper in group["papers"]:
            title = paper["title"]
            if paper.get("year"):
                title = f"{title} ({paper['year']})"
            parts.append(f"## {title}")
            parts.append("")
            parts.append(paper.get("abstract") or "(无摘要)")
            parts.append("")
        parts.append("---")
        parts.append("")
    return "\n".join(parts).strip()
