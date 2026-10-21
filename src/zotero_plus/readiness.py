from __future__ import annotations

from pathlib import Path

from .analysis_store import AnalysisSummaryStore
from .config import AppConfig
from .models import AttachmentRecord, CollectionReadinessRecord, PaperRecord
from .zotero_client import ZoteroLibrary


def assess_collection_readiness(
    library: ZoteroLibrary,
    config: AppConfig,
    summary_store: AnalysisSummaryStore,
    collection_key: str,
    recursive: bool = False,
) -> CollectionReadinessRecord:
    target_col = library.get_collection_by_key(collection_key)
    all_collections = library.list_collections()

    if recursive:
        descendants = library.get_descendant_collections(collection_key)
        subcollection_count = max(0, len(descendants) - 1)
    else:
        direct_children = [c for c in all_collections if c.parent_key == collection_key]
        subcollection_count = len(direct_children)

    papers = library.list_collection_items(collection_key, recursive=recursive)
    total_papers = len(papers)

    papers_with_pdf = 0
    papers_with_abstract = 0
    unique_attachments_dict: dict[str, AttachmentRecord] = {}

    for paper in papers:
        has_pdf = False
        if paper.abstract and paper.abstract.strip():
            papers_with_abstract += 1
        for att in paper.attachments:
            if att.is_pdf:
                has_pdf = True
                if att.key not in unique_attachments_dict:
                    unique_attachments_dict[att.key] = att
        if has_pdf:
            papers_with_pdf += 1

    papers_without_pdf = total_papers - papers_with_pdf
    pdf_attachments = list(unique_attachments_dict.values())
    total_pdf_attachments = len(pdf_attachments)

    local_pdf_attachments = 0
    missing_pdf_attachments = 0
    cached_pdf_texts = 0
    uncached_attachments: list[dict[str, str]] = []

    for att in pdf_attachments:
        has_local = bool(att.local_path and att.local_path.exists())
        if has_local:
            local_pdf_attachments += 1
        else:
            missing_pdf_attachments += 1

        cached_text_path = config.pdf_cache_dir / f"{att.key}.txt"
        if cached_text_path.exists():
            cached_pdf_texts += 1
        else:
            uncached_attachments.append(
                {
                    "attachment_key": att.key,
                    "attachment_title": att.title,
                    "has_local_file": str(has_local).lower(),
                }
            )

    uncached_pdf_texts = len(uncached_attachments)

    # Calculate summaries
    paper_keys = {p.key for p in papers}
    all_summaries = summary_store.list_summaries()
    matching_summaries = [s for s in all_summaries if s.paper_key in paper_keys]
    total_analysis_summaries = len(matching_summaries)
    analyzed_papers_count = len({s.paper_key for s in matching_summaries})

    # Cache percentage & status
    if local_pdf_attachments == 0:
        cache_percentage = 100.0 if total_papers > 0 else 0.0
    else:
        cache_percentage = round((cached_pdf_texts / local_pdf_attachments) * 100, 1)

    if total_papers == 0:
        status = "empty"
    elif local_pdf_attachments == 0:
        status = "ready"
    elif cached_pdf_texts == local_pdf_attachments:
        status = "ready"
    elif cached_pdf_texts > 0:
        status = "partially_cached"
    else:
        status = "no_cache"

    # Generate suggestions
    rec_flag = " -r" if recursive else ""
    suggestions: list[str] = []

    if status == "empty":
        suggestions.append("当前分类无文献条目，请在 Zotero 中向该分类添加文献。")
    else:
        if not recursive and subcollection_count > 0:
            suggestions.append(
                f"当前分类包含 {subcollection_count} 个子分类，可添加 '-r' / '--recursive' 参数进行穿透体检。"
            )

        if missing_pdf_attachments > 0:
            suggestions.append(
                f"有 {missing_pdf_attachments} 个 PDF 附件本地文件缺失（未同步或路径失效），建议在 Zotero 中检查文件。"
            )

        uncached_locals = sum(1 for u in uncached_attachments if u["has_local_file"] == "true")
        if uncached_locals > 0:
            suggestions.append(
                f"有 {uncached_locals} 个本地 PDF 尚未提取全文缓存，建议执行：zotero-skill extract-pdfs {collection_key}{rec_flag}"
            )

        if papers_without_pdf > 0:
            suggestions.append(
                f"有 {papers_without_pdf} 篇文献没有 PDF 附件，仅支持基于标题和摘要进行检索。"
            )

        if status == "ready" and cached_pdf_texts > 0:
            suggestions.append(
                f"所有本地 PDF 已提取就绪（{cached_pdf_texts}/{local_pdf_attachments}），可直接使用 zotero-skill search {collection_key}{rec_flag} --keywords ... 进行全文检索与分析。"
            )

    return CollectionReadinessRecord(
        collection_key=target_col.key,
        collection_name=target_col.name,
        collection_path=target_col.path,
        is_recursive=recursive,
        subcollection_count=subcollection_count,
        total_papers=total_papers,
        papers_with_pdf=papers_with_pdf,
        papers_without_pdf=papers_without_pdf,
        papers_with_abstract=papers_with_abstract,
        total_pdf_attachments=total_pdf_attachments,
        local_pdf_attachments=local_pdf_attachments,
        missing_pdf_attachments=missing_pdf_attachments,
        cached_pdf_texts=cached_pdf_texts,
        uncached_pdf_texts=uncached_pdf_texts,
        total_analysis_summaries=total_analysis_summaries,
        analyzed_papers_count=analyzed_papers_count,
        cache_percentage=cache_percentage,
        status=status,
        suggestions=suggestions,
        uncached_attachments=uncached_attachments,
    )
