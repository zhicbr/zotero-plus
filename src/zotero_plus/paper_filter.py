from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .models import (
    FilterDecision,
    KeywordHitRecord,
    PaperRecord,
    PaperSearchRecord,
    PdfSearchHitRecord,
)


@dataclass(slots=True)
class FilterRules:
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    scope: str = "all"  # "all" | "abstract" | "pdf"
    min_text_length: int = 0
    snippet_radius: int = 100
    max_snippets_per_keyword: int = 3
    only_matched: bool = True


def extract_keyword_snippets(
    text: str,
    keyword: str,
    snippet_radius: int = 100,
    max_snippets: int = 3,
) -> tuple[int, list[str]]:
    """Find occurrences of keyword in text (case-insensitive) and extract context snippets."""
    if not text or not keyword:
        return 0, []

    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    matches = list(pattern.finditer(text))
    count = len(matches)
    if count == 0:
        return 0, []

    snippets: list[str] = []
    for match in matches[:max_snippets]:
        start = max(0, match.start() - snippet_radius)
        end = min(len(text), match.end() + snippet_radius)
        raw_snippet = text[start:end]
        cleaned = re.sub(r"\s+", " ", raw_snippet).strip()
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        snippets.append(f"{prefix}{cleaned}{suffix}")

    return count, snippets


def search_text_keywords(
    text: str,
    keywords: list[str],
    snippet_radius: int = 100,
    max_snippets: int = 3,
) -> list[KeywordHitRecord]:
    """Search multiple keywords in a text block, returning hit records for matching keywords."""
    hits: list[KeywordHitRecord] = []
    for kw in keywords:
        kw_clean = kw.strip()
        if not kw_clean:
            continue
        count, snippets = extract_keyword_snippets(
            text=text,
            keyword=kw_clean,
            snippet_radius=snippet_radius,
            max_snippets=max_snippets,
        )
        if count > 0:
            hits.append(KeywordHitRecord(keyword=kw_clean, count=count, snippets=snippets))
    return hits


class PaperSearchEngine:
    """Searches abstracts and cached PDF texts for papers matching keyword criteria."""

    def __init__(self, pdf_cache_dir: Path) -> None:
        self._pdf_cache_dir = pdf_cache_dir

    def search_paper(self, paper: PaperRecord, rules: FilterRules) -> PaperSearchRecord:
        # 1. Check exclude keywords
        if rules.exclude_keywords:
            for excl in rules.exclude_keywords:
                excl_clean = excl.strip()
                if not excl_clean:
                    continue
                # Check abstract
                if paper.abstract and re.search(re.escape(excl_clean), paper.abstract, re.IGNORECASE):
                    return PaperSearchRecord(
                        paper_key=paper.key,
                        title=paper.title,
                        year=paper.year,
                        authors=paper.authors,
                        matched=False,
                        excluded=True,
                        exclude_reason=f"Excluded by keyword '{excl_clean}' in abstract",
                    )
                # Check cached PDFs
                for att in paper.attachments:
                    if att.is_pdf:
                        pdf_txt = self._pdf_cache_dir / f"{att.key}.txt"
                        if pdf_txt.exists():
                            content = pdf_txt.read_text(encoding="utf-8", errors="replace")
                            if re.search(re.escape(excl_clean), content, re.IGNORECASE):
                                return PaperSearchRecord(
                                    paper_key=paper.key,
                                    title=paper.title,
                                    year=paper.year,
                                    authors=paper.authors,
                                    matched=False,
                                    excluded=True,
                                    exclude_reason=f"Excluded by keyword '{excl_clean}' in PDF {att.key}",
                                )

        abstract_hits: list[KeywordHitRecord] = []
        pdf_hits: list[PdfSearchHitRecord] = []
        pdf_cache_status = "no_pdf"

        # 2. Search abstract
        if rules.scope in ("all", "abstract") and paper.abstract:
            abstract_hits = search_text_keywords(
                text=paper.abstract,
                keywords=rules.include_keywords,
                snippet_radius=rules.snippet_radius,
                max_snippets=rules.max_snippets_per_keyword,
            )

        # 3. Search cached PDF text
        pdf_attachments = [att for att in paper.attachments if att.is_pdf]
        if pdf_attachments:
            any_cached = False
            for att in pdf_attachments:
                pdf_txt = self._pdf_cache_dir / f"{att.key}.txt"
                if pdf_txt.exists():
                    any_cached = True
                    if rules.scope in ("all", "pdf"):
                        content = pdf_txt.read_text(encoding="utf-8", errors="replace")
                        kw_hits = search_text_keywords(
                            text=content,
                            keywords=rules.include_keywords,
                            snippet_radius=rules.snippet_radius,
                            max_snippets=rules.max_snippets_per_keyword,
                        )
                        if kw_hits:
                            pdf_hits.append(
                                PdfSearchHitRecord(
                                    attachment_key=att.key,
                                    attachment_title=att.title,
                                    total_hits=sum(h.count for h in kw_hits),
                                    hits=kw_hits,
                                )
                            )
            pdf_cache_status = "cached" if any_cached else "not_cached"

        # 4. Aggregations
        hit_keywords_set: set[str] = set()
        total_hits = 0

        for h in abstract_hits:
            hit_keywords_set.add(h.keyword)
            total_hits += h.count

        for p_hit in pdf_hits:
            for h in p_hit.hits:
                hit_keywords_set.add(h.keyword)
                total_hits += h.count

        matched = len(hit_keywords_set) > 0 if rules.include_keywords else True

        return PaperSearchRecord(
            paper_key=paper.key,
            title=paper.title,
            year=paper.year,
            authors=paper.authors,
            matched=matched,
            total_hits=total_hits,
            hit_keywords=sorted(hit_keywords_set),
            abstract_hits=abstract_hits,
            pdf_hits=pdf_hits,
            pdf_cache_status=pdf_cache_status,
            excluded=False,
            exclude_reason=None,
        )

    def search_papers(self, papers: list[PaperRecord], rules: FilterRules) -> list[PaperSearchRecord]:
        results: list[PaperSearchRecord] = []
        for paper in papers:
            record = self.search_paper(paper, rules)
            if rules.only_matched and not record.matched:
                continue
            results.append(record)

        # Sort by total hits descending, then by number of unique keywords matched descending
        results.sort(key=lambda r: (r.total_hits, len(r.hit_keywords)), reverse=True)
        return results


class BasicPaperFilter:
    """Legacy filter retained for backward compatibility."""

    def __init__(self, rules: FilterRules) -> None:
        self._rules = rules

    def evaluate(self, text: str) -> FilterDecision:
        reasons: list[str] = []
        snippets: list[str] = []
        normalized_text = text.lower()

        if len(text.strip()) < self._rules.min_text_length:
            reasons.append(f"Text shorter than min_text_length={self._rules.min_text_length}.")

        include_hits = [
            keyword for keyword in self._rules.include_keywords if keyword.lower() in normalized_text
        ]
        if self._rules.include_keywords and not include_hits:
            reasons.append("No include keywords matched.")
        elif include_hits:
            reasons.append(f"Matched include keywords: {', '.join(include_hits)}.")
            for kw in include_hits:
                _, s = extract_keyword_snippets(text, kw, self._rules.snippet_radius, 3)
                snippets.extend(s)

        exclude_hits = [
            keyword for keyword in self._rules.exclude_keywords if keyword.lower() in normalized_text
        ]
        if exclude_hits:
            reasons.append(f"Matched exclude keywords: {', '.join(exclude_hits)}.")

        matched = bool(include_hits or not self._rules.include_keywords) and not exclude_hits
        if len(text.strip()) < self._rules.min_text_length:
            matched = False

        return FilterDecision(matched=matched, reasons=reasons, snippets=snippets[:5])
