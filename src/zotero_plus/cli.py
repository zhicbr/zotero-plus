from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .analysis_store import AnalysisSummaryStore
from .config import AppConfig, ConfigError
from .paper_filter import FilterRules, PaperSearchEngine
from .pdf_extractor import PdfExtractionError, PdfTextExtractor
from .pipeline import build_export_data, format_abstracts_md
from .readiness import assess_collection_readiness
from .zotero_client import ZoteroLibrary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zotero-plus",
        description="Local-first Zotero tools for collections, items, attachments, PDF text extraction, and AI-written analysis summaries.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Check the local Zotero skill environment and database access.")
    doctor_parser.add_argument("--json-output", type=Path)

    collections_parser = subparsers.add_parser("collections", help="List all Zotero collections from the local sqlite database.")
    collections_parser.add_argument("--json-output", type=Path)

    items_parser = subparsers.add_parser("items", help="List paper items in a collection.")
    items_parser.add_argument("collection_key")
    items_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively include items from all descendant collections.",
    )
    items_parser.add_argument("--json-output", type=Path)

    abstract_parser = subparsers.add_parser("abstract", help="Get the stored abstract for one paper by paper key.")
    abstract_parser.add_argument("paper_key")
    abstract_parser.add_argument("--json-output", type=Path)

    toc_parser = subparsers.add_parser("toc", help="Get the PDF table of contents for one attachment by attachment key.")
    toc_parser.add_argument("attachment_key")
    toc_parser.add_argument("--json-output", type=Path)

    toc_from_paper_parser = subparsers.add_parser("toc-from-paper", help="Get the PDF table of contents for one paper by paper key.")
    toc_from_paper_parser.add_argument("paper_key")
    toc_from_paper_parser.add_argument("--json-output", type=Path)

    attachments_parser = subparsers.add_parser("attachments", help="List attachments for all paper items in a collection.")
    attachments_parser.add_argument("collection_key")
    attachments_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively list attachments from all descendant collections.",
    )
    attachments_parser.add_argument("--json-output", type=Path)
    attachments_parser.add_argument("--pdf-only", action="store_true")

    extract_parser = subparsers.add_parser("extract-pdfs", help="Extract and cache PDF text for a collection.")
    extract_parser.add_argument("collection_key")
    extract_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively extract PDFs from all descendant collections.",
    )
    extract_parser.add_argument("--force", action="store_true", help="Re-extract PDFs even if cached text already exists.")
    extract_parser.add_argument("--json-output", type=Path)

    summaries_parser = subparsers.add_parser(
        "summaries",
        help="List cached requirement-specific analysis summaries written by an AI.",
    )
    summaries_parser.add_argument("--collection-key")
    summaries_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively match summaries across all descendant subcollections.",
    )
    summaries_parser.add_argument("--attachment-key")
    summaries_parser.add_argument("--requirement")
    summaries_parser.add_argument("--search")
    summaries_parser.add_argument("--json-output", type=Path)

    save_summary_parser = subparsers.add_parser(
        "save-summary",
        help="Save or update an AI-written requirement-specific summary for one PDF attachment.",
    )
    save_summary_parser.add_argument("--attachment-key", required=True)
    save_summary_parser.add_argument("--requirement", required=True)
    save_summary_parser.add_argument(
        "--verdict",
        required=True,
        choices=["match", "maybe", "not_match", "unknown"],
    )
    summary_group = save_summary_parser.add_mutually_exclusive_group(required=True)
    summary_group.add_argument("--summary")
    summary_group.add_argument("--summary-file", type=Path)
    save_summary_parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="Short supporting note. Repeat for multiple evidence items.",
    )
    save_summary_parser.add_argument("--json-output", type=Path)

    export_parser = subparsers.add_parser("export-abstracts", help="Export paper titles and abstracts from one or more collections.")
    export_parser.add_argument("collection_keys", nargs="+")
    export_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively export papers from all descendant collections.",
    )
    export_parser.add_argument("--format", choices=["md", "json", "both"], default="md")
    export_parser.add_argument("--output", type=Path)

    search_parser = subparsers.add_parser(
        "search",
        help="Search keywords in abstracts and cached PDF texts within a collection or a specific paper.",
    )
    search_parser.add_argument("collection_key", help="Collection key to search in.")
    search_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively search in all descendant collections.",
    )
    search_parser.add_argument("--paper-key", help="Optional: limit search to a single paper key.")
    search_parser.add_argument("--keywords", nargs="+", required=True, help="One or more keywords to search.")
    search_parser.add_argument("--exclude", nargs="+", default=[], help="Exclude papers containing these keywords.")
    search_parser.add_argument(
        "--scope",
        choices=["all", "pdf", "abstract"],
        default="all",
        help="Search scope: all, abstract, or pdf (default: all).",
    )
    search_parser.add_argument(
        "--snippet-radius",
        type=int,
        default=100,
        help="Context character radius for snippet extraction (default: 100).",
    )
    search_parser.add_argument(
        "--all-papers",
        action="store_true",
        help="Include papers with 0 keyword matches in results (default: only matched papers).",
    )
    search_parser.add_argument("--json-output", type=Path)

    status_parser = subparsers.add_parser(
        "cache-status",
        help="Diagnose PDF extraction and summary readiness for a collection.",
    )
    status_parser.add_argument("collection_key", help="Collection key to diagnose.")
    status_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively diagnose all descendant subcollections.",
    )
    status_parser.add_argument("--json-output", type=Path)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        config = AppConfig.from_env()
    except ConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    library = ZoteroLibrary(config)
    summary_store = AnalysisSummaryStore(config.analysis_summary_dir)

    try:
        if args.command == "doctor":
            collections = library.list_collections()
            payload = {
                "status": "ok",
                "sqlite_path": str(config.zotero_sqlite_path),
                "sqlite_exists": config.zotero_sqlite_path.exists(),
                "storage_dir": str(config.zotero_storage_dir),
                "storage_exists": config.zotero_storage_dir.exists(),
                "cache_dir": str(config.cache_dir),
                "cache_dir_exists": config.cache_dir.exists(),
                "output_dir": str(config.output_dir),
                "pdf_cache_dir": str(config.pdf_cache_dir),
                "analysis_summary_dir": str(config.analysis_summary_dir),
                "collection_count": len(collections),
            }
        elif args.command == "collections":
            payload = [asdict(record) for record in library.list_collections()]
        elif args.command == "items":
            payload = [asdict(record) for record in library.list_collection_items(args.collection_key, recursive=args.recursive)]
        elif args.command == "abstract":
            paper = library.get_paper_by_key(args.paper_key)
            payload = {
                "paper_key": paper.key,
                "title": paper.title,
                "year": paper.year,
                "abstract": paper.abstract,
                "doi": paper.doi,
                "authors": paper.authors,
                "collection_keys": paper.collection_keys,
            }
        elif args.command == "toc":
            extractor = PdfTextExtractor(config.pdf_cache_dir)
            context = library.get_attachment_context(args.attachment_key)
            payload = asdict(extractor.extract_toc(context.attachment))
        elif args.command == "toc-from-paper":
            extractor = PdfTextExtractor(config.pdf_cache_dir)
            context = library.get_preferred_pdf_attachment_context(args.paper_key)
            toc_record = extractor.extract_toc(context.attachment)
            payload = {
                "paper_key": context.paper.key,
                "title": context.paper.title,
                "year": context.paper.year,
                "selected_attachment_key": context.attachment.key,
                "selected_attachment_title": context.attachment.title,
                "pdf_attachment_keys": [attachment.key for attachment in context.paper.attachments if attachment.is_pdf],
                "toc": [asdict(entry) for entry in toc_record.toc],
                "toc_count": toc_record.toc_count,
                "has_toc": toc_record.has_toc,
                "file_path": str(toc_record.file_path),
            }
        elif args.command == "attachments":
            attachments = library.list_collection_attachments(args.collection_key, recursive=args.recursive)
            if args.pdf_only:
                attachments = [attachment for attachment in attachments if attachment.is_pdf]
            payload = [asdict(record) for record in attachments]
        elif args.command == "extract-pdfs":
            extractor = PdfTextExtractor(config.pdf_cache_dir)
            results = []
            for attachment in library.list_collection_attachments(args.collection_key, recursive=args.recursive):
                if not attachment.is_pdf:
                    continue
                try:
                    results.append(asdict(extractor.extract_attachment(attachment, force=args.force)))
                except PdfExtractionError as exc:
                    results.append(
                        {
                            "attachment_key": attachment.key,
                            "file_path": str(attachment.local_path) if attachment.local_path else None,
                            "cache_json_path": str(config.pdf_cache_dir / f"{attachment.key}.json"),
                            "cache_text_path": str(config.pdf_cache_dir / f"{attachment.key}.txt"),
                            "page_count": 0,
                            "text_length": 0,
                            "extracted": False,
                            "cached": False,
                            "error": str(exc),
                        }
                    )
            payload = results
        elif args.command == "summaries":
            if args.collection_key and args.recursive:
                descendants = library.get_descendant_collections(args.collection_key)
                descendant_keys = {c.key for c in descendants}
                summaries = summary_store.list_summaries(
                    collection_key=None,
                    attachment_key=args.attachment_key,
                    requirement=args.requirement,
                    search=args.search,
                )
                payload = [
                    asdict(record)
                    for record in summaries
                    if any(k in record.collection_keys for k in descendant_keys)
                ]
            else:
                payload = [
                    asdict(record)
                    for record in summary_store.list_summaries(
                        collection_key=args.collection_key,
                        attachment_key=args.attachment_key,
                        requirement=args.requirement,
                        search=args.search,
                    )
                ]
        elif args.command == "save-summary":
            context = library.get_attachment_context(args.attachment_key)
            summary_text = args.summary
            if args.summary_file:
                summary_text = args.summary_file.read_text(encoding="utf-8")

            pdf_cache_text_path = config.pdf_cache_dir / f"{args.attachment_key}.txt"
            pdf_cache_json_path = config.pdf_cache_dir / f"{args.attachment_key}.json"
            payload = asdict(
                summary_store.save_summary(
                    context=context,
                    requirement=args.requirement,
                    verdict=args.verdict,
                    summary=summary_text or "",
                    evidence=args.evidence,
                    pdf_cache_text_path=pdf_cache_text_path if pdf_cache_text_path.exists() else None,
                    pdf_cache_json_path=pdf_cache_json_path if pdf_cache_json_path.exists() else None,
                )
            )
        elif args.command == "export-abstracts":
            data = build_export_data(library, args.collection_keys, recursive=args.recursive)

            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                if args.format == "both":
                    md_path = args.output.with_suffix(".md")
                    json_path = args.output.with_suffix(".json")
                    md_path.write_text(format_abstracts_md(data), encoding="utf-8")
                    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
                elif args.format == "md":
                    args.output.write_text(format_abstracts_md(data), encoding="utf-8")
                else:
                    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

            if not args.output and args.format == "md":
                sys.stdout.buffer.write(format_abstracts_md(data).encode("utf-8"))
                sys.stdout.buffer.write(b"\n")
                return 0

            payload = data
        elif args.command == "search":
            search_engine = PaperSearchEngine(config.pdf_cache_dir)
            rules = FilterRules(
                include_keywords=args.keywords,
                exclude_keywords=args.exclude,
                scope=args.scope,
                snippet_radius=args.snippet_radius,
                only_matched=not args.all_papers,
            )
            if args.paper_key:
                paper = library.get_paper_by_key(args.paper_key)
                search_record = search_engine.search_paper(paper, rules)
                payload = asdict(search_record)
            else:
                papers = library.list_collection_items(args.collection_key, recursive=args.recursive)
                records = search_engine.search_papers(papers, rules)
                payload = [asdict(record) for record in records]
        elif args.command == "cache-status":
            readiness_record = assess_collection_readiness(
                library=library,
                config=config,
                summary_store=summary_store,
                collection_key=args.collection_key,
                recursive=args.recursive,
            )
            payload = asdict(readiness_record)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    if getattr(args, "json_output", None):
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
