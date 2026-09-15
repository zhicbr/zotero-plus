from __future__ import annotations

from dataclasses import dataclass, field

from .models import FilterDecision


@dataclass(slots=True)
class FilterRules:
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)
    min_text_length: int = 0
    snippet_radius: int = 120


class BasicPaperFilter:
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
            snippets.extend(self._collect_snippets(text, include_hits))

        exclude_hits = [
            keyword for keyword in self._rules.exclude_keywords if keyword.lower() in normalized_text
        ]
        if exclude_hits:
            reasons.append(f"Matched exclude keywords: {', '.join(exclude_hits)}.")
            snippets.extend(self._collect_snippets(text, exclude_hits))

        matched = bool(include_hits or not self._rules.include_keywords) and not exclude_hits
        if len(text.strip()) < self._rules.min_text_length:
            matched = False

        unique_snippets = []
        for snippet in snippets:
            if snippet not in unique_snippets:
                unique_snippets.append(snippet)

        return FilterDecision(matched=matched, reasons=reasons, snippets=unique_snippets[:5])

    def _collect_snippets(self, text: str, keywords: list[str]) -> list[str]:
        snippets: list[str] = []
        lowered_text = text.lower()
        for keyword in keywords:
            index = lowered_text.find(keyword.lower())
            if index < 0:
                continue
            start = max(0, index - self._rules.snippet_radius)
            end = min(len(text), index + len(keyword) + self._rules.snippet_radius)
            snippets.append(text[start:end].replace("\n", " ").strip())
        return snippets
