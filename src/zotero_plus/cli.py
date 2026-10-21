from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .analysis_store import AnalysisSummaryStore
from .config import AppConfig, ConfigError
from .mutator import MutationError, ZoteroMutator
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

    # -------------------------------------------------------------------------
    # Safe Mutations & Local Auth Subcommands
    # -------------------------------------------------------------------------
    backup_parser = subparsers.add_parser(
        "backup",
        help="Create an instant hot snapshot backup of zotero.sqlite and WAL files.",
    )
    backup_parser.add_argument(
        "--max-keep",
        type=int,
        default=10,
        help="Maximum number of historical snapshots to retain (default: 10).",
    )
    backup_parser.add_argument("--json-output", type=Path)

    auth_parser = subparsers.add_parser(
        "auth",
        help="Request write authorization from the running Zotero desktop application (one-time confirmation).",
    )
    auth_parser.add_argument(
        "--app-name",
        default="zotero-plus",
        help="Application name to display in the Zotero desktop authorization prompt.",
    )
    auth_parser.add_argument("--json-output", type=Path)

    create_col_parser = subparsers.add_parser("create-collection", help="Create a new collection.")
    create_col_parser.add_argument("name", help="Name of the new collection.")
    create_col_parser.add_argument("--parent", dest="parent_key", help="Optional parent collection key.")
    create_col_parser.add_argument("--dry-run", action="store_true", help="Preview without making changes.")
    create_col_parser.add_argument("--backend", choices=["local", "remote", "auto"], default=None)
    create_col_parser.add_argument("--json-output", type=Path)

    rename_col_parser = subparsers.add_parser("rename-collection", help="Rename an existing collection.")
    rename_col_parser.add_argument("collection_key", help="Key of the collection to rename.")
    rename_col_parser.add_argument("new_name", help="New name for the collection.")
    rename_col_parser.add_argument("--dry-run", action="store_true", help="Preview without making changes.")
    rename_col_parser.add_argument("--backend", choices=["local", "remote", "auto"], default=None)
    rename_col_parser.add_argument("--json-output", type=Path)

    delete_col_parser = subparsers.add_parser(
        "delete-empty-collection",
        help="Delete an empty collection (strictly refuses if it contains paper items or subcollections).",
    )
    delete_col_parser.add_argument("collection_key", help="Key of the empty collection to delete.")
    delete_col_parser.add_argument("--dry-run", action="store_true", help="Preview without making changes.")
    delete_col_parser.add_argument("--backend", choices=["local", "remote", "auto"], default=None)
    delete_col_parser.add_argument("--json-output", type=Path)

    add_col_parser = subparsers.add_parser("add-to-collection", help="Assign a paper item to a collection.")
    add_col_parser.add_argument("paper_key", help="Key of the paper item.")
    add_col_parser.add_argument("collection_key", help="Key of the collection.")
    add_col_parser.add_argument("--dry-run", action="store_true", help="Preview without making changes.")
    add_col_parser.add_argument("--backend", choices=["local", "remote", "auto"], default=None)
    add_col_parser.add_argument("--json-output", type=Path)

    remove_col_parser = subparsers.add_parser("remove-from-collection", help="Remove a paper item from a collection.")
    remove_col_parser.add_argument("paper_key", help="Key of the paper item.")
    remove_col_parser.add_argument("collection_key", help="Key of the collection.")
    remove_col_parser.add_argument("--dry-run", action="store_true", help="Preview without making changes.")
    remove_col_parser.add_argument("--backend", choices=["local", "remote", "auto"], default=None)
    remove_col_parser.add_argument("--json-output", type=Path)

    move_paper_parser = subparsers.add_parser("move-paper", help="Move a paper item to a target collection.")
    move_paper_parser.add_argument("paper_key", help="Key of the paper item.")
    move_paper_parser.add_argument("--to", dest="to_collection_key", required=True, help="Target collection key.")
    move_paper_parser.add_argument(
        "--from",
        dest="from_collection_key",
        help="Optional source collection key to remove from (defaults to current collection if item is in only one).",
    )
    move_paper_parser.add_argument("--dry-run", action="store_true", help="Preview without making changes.")
    move_paper_parser.add_argument("--backend", choices=["local", "remote", "auto"], default=None)
    move_paper_parser.add_argument("--json-output", type=Path)

    add_tag_parser = subparsers.add_parser("add-tag", help="Add a tag to a paper item.")
    add_tag_parser.add_argument("paper_key", help="Key of the paper item.")
    add_tag_parser.add_argument("tag", help="Tag name to add.")
    add_tag_parser.add_argument("--dry-run", action="store_true", help="Preview without making changes.")
    add_tag_parser.add_argument("--backend", choices=["local", "remote", "auto"], default=None)
    add_tag_parser.add_argument("--json-output", type=Path)

    remove_tag_parser = subparsers.add_parser("remove-tag", help="Remove a tag from a paper item.")
    remove_tag_parser.add_argument("paper_key", help="Key of the paper item.")
    remove_tag_parser.add_argument("tag", help="Tag name to remove.")
    remove_tag_parser.add_argument("--dry-run", action="store_true", help="Preview without making changes.")
    remove_tag_parser.add_argument("--backend", choices=["local", "remote", "auto"], default=None)
    remove_tag_parser.add_argument("--json-output", type=Path)

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
            mutator = ZoteroMutator(config, library)
            local_api_avail = mutator.is_local_api_available()
            local_auth = bool(config.get_effective_local_key())
            backup_count = len(list(config.backup_dir.glob("backup_*"))) if config.backup_dir.exists() else 0
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
                "backup_dir": str(config.backup_dir),
                "backup_count": backup_count,
                "collection_count": len(collections),
                "local_api_available": local_api_avail,
                "local_authorized": local_auth,
                "mutation_backend": config.mutation_backend,
                "remote_configured": bool(config.zotero_user_id and config.zotero_api_key),
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
        elif args.command == "backup":
            mutator = ZoteroMutator(config, library)
            payload = mutator.create_snapshot_backup(max_keep=args.max_keep)
        elif args.command == "auth":
            mutator = ZoteroMutator(config, library)
            payload = mutator.authorize_local(app_name=args.app_name)
        elif args.command == "create-collection":
            mutator = ZoteroMutator(config, library)
            payload = mutator.create_collection(
                name=args.name,
                parent_key=args.parent_key,
                dry_run=args.dry_run,
                backend_override=args.backend,
            )
        elif args.command == "rename-collection":
            mutator = ZoteroMutator(config, library)
            payload = mutator.rename_collection(
                collection_key=args.collection_key,
                new_name=args.new_name,
                dry_run=args.dry_run,
                backend_override=args.backend,
            )
        elif args.command == "delete-empty-collection":
            mutator = ZoteroMutator(config, library)
            payload = mutator.delete_empty_collection(
                collection_key=args.collection_key,
                dry_run=args.dry_run,
                backend_override=args.backend,
            )
        elif args.command == "add-to-collection":
            mutator = ZoteroMutator(config, library)
            payload = mutator.add_to_collection(
                paper_key=args.paper_key,
                collection_key=args.collection_key,
                dry_run=args.dry_run,
                backend_override=args.backend,
            )
        elif args.command == "remove-from-collection":
            mutator = ZoteroMutator(config, library)
            payload = mutator.remove_from_collection(
                paper_key=args.paper_key,
                collection_key=args.collection_key,
                dry_run=args.dry_run,
                backend_override=args.backend,
            )
        elif args.command == "move-paper":
            mutator = ZoteroMutator(config, library)
            payload = mutator.move_paper(
                paper_key=args.paper_key,
                to_collection_key=args.to_collection_key,
                from_collection_key=args.from_collection_key,
                dry_run=args.dry_run,
                backend_override=args.backend,
            )
        elif args.command == "add-tag":
            mutator = ZoteroMutator(config, library)
            payload = mutator.add_tag(
                paper_key=args.paper_key,
                tag=args.tag,
                dry_run=args.dry_run,
                backend_override=args.backend,
            )
        elif args.command == "remove-tag":
            mutator = ZoteroMutator(config, library)
            payload = mutator.remove_tag(
                paper_key=args.paper_key,
                tag=args.tag,
                dry_run=args.dry_run,
                backend_override=args.backend,
            )
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except (ValueError, MutationError) as exc:
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
