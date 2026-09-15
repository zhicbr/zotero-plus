from __future__ import annotations

import shutil
import sqlite3
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from .config import AppConfig
from .models import AttachmentContextRecord, AttachmentRecord, CollectionRecord, PaperRecord


SUPPORTED_PAPER_TYPES = {
    "journalArticle",
    "conferencePaper",
    "preprint",
    "report",
    "thesis",
    "bookSection",
    "book",
    "document",
}


class ZoteroLibrary:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def list_collections(self) -> list[CollectionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.collectionID,
                       c.key,
                       c.collectionName,
                       c.parentCollectionID,
                       parent.key AS parentKey,
                       parent.collectionName AS parentName,
                       COUNT(ci.itemID) AS itemCount
                FROM collections c
                LEFT JOIN collections parent ON parent.collectionID = c.parentCollectionID
                LEFT JOIN collectionItems ci ON ci.collectionID = c.collectionID
                GROUP BY c.collectionID, c.key, c.collectionName, c.parentCollectionID, parent.key, parent.collectionName
                """
            ).fetchall()

        collection_map: dict[str, dict[str, object]] = {}
        for row in rows:
            collection_id, key, name, parent_id, parent_key, parent_name, item_count = row
            collection_map[key] = {
                "id": collection_id,
                "key": key,
                "name": name,
                "parent_id": parent_id,
                "parent_key": parent_key,
                "parent_name": parent_name,
                "item_count": item_count,
            }

        def build_path_keys(collection_key: str) -> list[str]:
            path_keys: list[str] = []
            seen: set[str] = set()
            current_key: str | None = collection_key
            while current_key:
                if current_key in seen:
                    break
                seen.add(current_key)
                record = collection_map.get(current_key)
                if not record:
                    break
                path_keys.append(current_key)
                current_key = record["parent_key"]  # type: ignore[assignment]
            path_keys.reverse()
            return path_keys

        collections: list[CollectionRecord] = []
        for key, record in collection_map.items():
            path_keys = build_path_keys(key)
            path_names = [str(collection_map[path_key]["name"]) for path_key in path_keys if path_key in collection_map]
            collections.append(
                CollectionRecord(
                    id=int(record["id"]),
                    key=str(record["key"]),
                    name=str(record["name"]),
                    parent_id=int(record["parent_id"]) if record["parent_id"] is not None else None,
                    parent_key=str(record["parent_key"]) if record["parent_key"] is not None else None,
                    parent_name=str(record["parent_name"]) if record["parent_name"] is not None else None,
                    path=" / ".join(path_names),
                    path_keys=path_keys,
                    depth=max(len(path_keys) - 1, 0),
                    item_count=int(record["item_count"]),
                )
            )
        return sorted(collections, key=lambda record: (record.path.casefold(), record.key))

    def list_collection_items(self, collection_key: str) -> list[PaperRecord]:
        with self._connect() as conn:
            collection_row = conn.execute(
                "SELECT collectionID FROM collections WHERE key = ?",
                (collection_key,),
            ).fetchone()
            if not collection_row:
                raise ValueError(f"Collection not found: {collection_key}")
            collection_id = collection_row[0]

            rows = conn.execute(
                """
                SELECT i.itemID,
                       i.key,
                       it.typeName,
                       title.value AS title,
                       date_value.value AS dateValue,
                       abstract_value.value AS abstractValue,
                       doi_value.value AS doiValue
                FROM collectionItems ci
                JOIN items i ON i.itemID = ci.itemID
                JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
                LEFT JOIN itemData title_data ON title_data.itemID = i.itemID AND title_data.fieldID = 1
                LEFT JOIN itemDataValues title ON title.valueID = title_data.valueID
                LEFT JOIN itemData date_data ON date_data.itemID = i.itemID AND date_data.fieldID = 6
                LEFT JOIN itemDataValues date_value ON date_value.valueID = date_data.valueID
                LEFT JOIN itemData abstract_data ON abstract_data.itemID = i.itemID AND abstract_data.fieldID = 2
                LEFT JOIN itemDataValues abstract_value ON abstract_value.valueID = abstract_data.valueID
                LEFT JOIN itemData doi_data ON doi_data.itemID = i.itemID AND doi_data.fieldID = 59
                LEFT JOIN itemDataValues doi_value ON doi_value.valueID = doi_data.valueID
                WHERE ci.collectionID = ?
                ORDER BY COALESCE(title.value, '') COLLATE NOCASE, i.key
                """,
                (collection_id,),
            ).fetchall()

            candidate_rows = [row for row in rows if row[2] in SUPPORTED_PAPER_TYPES]
            item_ids = [row[0] for row in candidate_rows]
            authors_by_item = self._fetch_authors(conn, item_ids)
            attachments_by_item = self._fetch_attachments(conn, item_ids)
            collection_keys_by_item = self._fetch_collection_keys(conn, item_ids)

        papers: list[PaperRecord] = []
        for row in candidate_rows:
            item_id, key, item_type, title, date_value, abstract, doi = row
            papers.append(
                PaperRecord(
                    item_id=item_id,
                    key=key,
                    item_type=item_type,
                    title=(title or "").strip() or "(untitled)",
                    year=self._extract_year(date_value),
                    abstract=abstract,
                    doi=doi,
                    authors=authors_by_item.get(item_id, []),
                    collection_keys=collection_keys_by_item.get(item_id, [collection_key]),
                    attachments=attachments_by_item.get(item_id, []),
                )
            )
        return papers

    def list_collection_attachments(self, collection_key: str) -> list[AttachmentRecord]:
        papers = self.list_collection_items(collection_key)
        attachments: list[AttachmentRecord] = []
        for paper in papers:
            attachments.extend(paper.attachments)
        return attachments

    def get_paper_by_key(self, paper_key: str) -> PaperRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT i.itemID,
                       i.key,
                       it.typeName,
                       title.value AS title,
                       date_value.value AS dateValue,
                       abstract_value.value AS abstractValue,
                       doi_value.value AS doiValue
                FROM items i
                JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
                LEFT JOIN itemData title_data ON title_data.itemID = i.itemID AND title_data.fieldID = 1
                LEFT JOIN itemDataValues title ON title.valueID = title_data.valueID
                LEFT JOIN itemData date_data ON date_data.itemID = i.itemID AND date_data.fieldID = 6
                LEFT JOIN itemDataValues date_value ON date_value.valueID = date_data.valueID
                LEFT JOIN itemData abstract_data ON abstract_data.itemID = i.itemID AND abstract_data.fieldID = 2
                LEFT JOIN itemDataValues abstract_value ON abstract_value.valueID = abstract_data.valueID
                LEFT JOIN itemData doi_data ON doi_data.itemID = i.itemID AND doi_data.fieldID = 59
                LEFT JOIN itemDataValues doi_value ON doi_value.valueID = doi_data.valueID
                WHERE i.key = ?
                """,
                (paper_key,),
            ).fetchone()
            if not row:
                raise ValueError(f"Paper not found: {paper_key}")
            if row[2] not in SUPPORTED_PAPER_TYPES:
                raise ValueError(f"Item is not a supported paper type: {paper_key}")

            item_id, key, item_type, title, date_value, abstract, doi = row
            authors_by_item = self._fetch_authors(conn, [item_id])
            attachments_by_item = self._fetch_attachments(conn, [item_id])
            collection_keys_by_item = self._fetch_collection_keys(conn, [item_id])

        return PaperRecord(
            item_id=item_id,
            key=key,
            item_type=item_type,
            title=(title or "").strip() or "(untitled)",
            year=self._extract_year(date_value),
            abstract=abstract,
            doi=doi,
            authors=authors_by_item.get(item_id, []),
            collection_keys=collection_keys_by_item.get(item_id, []),
            attachments=attachments_by_item.get(item_id, []),
        )

    def get_attachment_context(self, attachment_key: str) -> AttachmentContextRecord:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT parent.itemID,
                       parent.key,
                       it.typeName,
                       title.value AS title,
                       date_value.value AS dateValue,
                       abstract_value.value AS abstractValue,
                       doi_value.value AS doiValue
                FROM items attachment_item
                JOIN itemAttachments ia ON ia.itemID = attachment_item.itemID
                JOIN items parent ON parent.itemID = ia.parentItemID
                JOIN itemTypes it ON it.itemTypeID = parent.itemTypeID
                LEFT JOIN itemData title_data ON title_data.itemID = parent.itemID AND title_data.fieldID = 1
                LEFT JOIN itemDataValues title ON title.valueID = title_data.valueID
                LEFT JOIN itemData date_data ON date_data.itemID = parent.itemID AND date_data.fieldID = 6
                LEFT JOIN itemDataValues date_value ON date_value.valueID = date_data.valueID
                LEFT JOIN itemData abstract_data ON abstract_data.itemID = parent.itemID AND abstract_data.fieldID = 2
                LEFT JOIN itemDataValues abstract_value ON abstract_value.valueID = abstract_data.valueID
                LEFT JOIN itemData doi_data ON doi_data.itemID = parent.itemID AND doi_data.fieldID = 59
                LEFT JOIN itemDataValues doi_value ON doi_value.valueID = doi_data.valueID
                WHERE attachment_item.key = ?
                """,
                (attachment_key,),
            ).fetchone()
            if not row:
                raise ValueError(f"Attachment not found: {attachment_key}")

            item_id, paper_key, item_type, title, date_value, abstract, doi = row
            authors_by_item = self._fetch_authors(conn, [item_id])
            attachments_by_item = self._fetch_attachments(conn, [item_id])
            collection_keys_by_item = self._fetch_collection_keys(conn, [item_id])

        paper = PaperRecord(
            item_id=item_id,
            key=paper_key,
            item_type=item_type,
            title=(title or "").strip() or "(untitled)",
            year=self._extract_year(date_value),
            abstract=abstract,
            doi=doi,
            authors=authors_by_item.get(item_id, []),
            collection_keys=collection_keys_by_item.get(item_id, []),
            attachments=attachments_by_item.get(item_id, []),
        )
        for attachment in paper.attachments:
            if attachment.key == attachment_key:
                return AttachmentContextRecord(paper=paper, attachment=attachment)
        raise ValueError(f"Attachment exists but could not be resolved under its parent item: {attachment_key}")

    def get_preferred_pdf_attachment_context(self, paper_key: str) -> AttachmentContextRecord:
        paper = self.get_paper_by_key(paper_key)
        pdf_attachments = [attachment for attachment in paper.attachments if attachment.is_pdf]
        if not pdf_attachments:
            raise ValueError(f"Paper does not have a PDF attachment: {paper_key}")

        preferred = next((attachment for attachment in pdf_attachments if attachment.exists_locally), None)
        if preferred is None:
            raise ValueError(f"Paper has PDF attachments but none exist locally: {paper_key}")

        return AttachmentContextRecord(paper=paper, attachment=preferred)

    def _fetch_authors(self, conn: sqlite3.Connection, item_ids: list[int]) -> dict[int, list[str]]:
        if not item_ids:
            return {}
        placeholders = ",".join("?" for _ in item_ids)
        rows = conn.execute(
            f"""
            SELECT ic.itemID, c.firstName, c.lastName, c.fieldMode, ic.orderIndex
            FROM itemCreators ic
            JOIN creators c ON c.creatorID = ic.creatorID
            WHERE ic.itemID IN ({placeholders})
            ORDER BY ic.itemID, ic.orderIndex
            """,
            item_ids,
        ).fetchall()
        authors: dict[int, list[str]] = defaultdict(list)
        for item_id, first_name, last_name, field_mode, _order_index in rows:
            if field_mode == 1:
                name = (last_name or "").strip()
            else:
                name = " ".join(part for part in ((first_name or "").strip(), (last_name or "").strip()) if part)
            if name:
                authors[item_id].append(name)
        return dict(authors)

    def _fetch_attachments(self, conn: sqlite3.Connection, parent_item_ids: list[int]) -> dict[int, list[AttachmentRecord]]:
        if not parent_item_ids:
            return {}
        placeholders = ",".join("?" for _ in parent_item_ids)
        rows = conn.execute(
            f"""
            SELECT ia.parentItemID,
                   ia.itemID,
                   i.key,
                   ia.linkMode,
                   ia.contentType,
                   ia.path,
                   title.value AS title
            FROM itemAttachments ia
            JOIN items i ON i.itemID = ia.itemID
            LEFT JOIN itemData title_data ON title_data.itemID = ia.itemID AND title_data.fieldID = 1
            LEFT JOIN itemDataValues title ON title.valueID = title_data.valueID
            WHERE ia.parentItemID IN ({placeholders})
            ORDER BY ia.parentItemID, ia.itemID
            """,
            parent_item_ids,
        ).fetchall()
        attachments: dict[int, list[AttachmentRecord]] = defaultdict(list)
        for parent_item_id, item_id, key, link_mode, content_type, raw_path, title in rows:
            local_path = self._resolve_local_path(key, raw_path)
            is_pdf = (content_type or "").lower() == "application/pdf" or str(raw_path).lower().endswith(".pdf")
            attachments[parent_item_id].append(
                AttachmentRecord(
                    item_id=item_id,
                    parent_item_id=parent_item_id,
                    key=key,
                    title=(title or "").strip() or Path(str(raw_path or key)).name,
                    content_type=content_type,
                    link_mode=link_mode,
                    path=raw_path,
                    local_path=local_path,
                    is_pdf=is_pdf,
                    exists_locally=bool(local_path and local_path.exists()),
                )
            )
        return dict(attachments)

    def _fetch_collection_keys(self, conn: sqlite3.Connection, item_ids: list[int]) -> dict[int, list[str]]:
        if not item_ids:
            return {}
        placeholders = ",".join("?" for _ in item_ids)
        rows = conn.execute(
            f"""
            SELECT ci.itemID, c.key
            FROM collectionItems ci
            JOIN collections c ON c.collectionID = ci.collectionID
            WHERE ci.itemID IN ({placeholders})
            ORDER BY ci.itemID, c.key
            """,
            item_ids,
        ).fetchall()
        collection_keys: dict[int, list[str]] = defaultdict(list)
        for item_id, collection_key in rows:
            collection_keys[item_id].append(collection_key)
        return dict(collection_keys)

    def _resolve_local_path(self, attachment_key: str, raw_path: str | None) -> Path | None:
        if not raw_path:
            return None

        if raw_path.startswith("storage:"):
            filename = raw_path.split(":", 1)[1]
            return self._config.zotero_storage_dir / attachment_key / filename

        if raw_path.startswith(("C:\\", "D:\\", "\\\\")) or raw_path.startswith("/"):
            return Path(raw_path).expanduser()

        return None

    @contextmanager
    def _connect(self) -> sqlite3.Connection:
        snapshot_dir = Path(tempfile.mkdtemp(prefix="zotero-sqlite-"))
        try:
            sqlite_path = self._config.zotero_sqlite_path
            snapshot_sqlite_path = snapshot_dir / sqlite_path.name
            shutil.copy2(sqlite_path, snapshot_sqlite_path)

            wal_path = sqlite_path.with_name(f"{sqlite_path.name}-wal")
            shm_path = sqlite_path.with_name(f"{sqlite_path.name}-shm")
            if wal_path.exists():
                shutil.copy2(wal_path, snapshot_dir / wal_path.name)
            if shm_path.exists():
                shutil.copy2(shm_path, snapshot_dir / shm_path.name)

            conn = sqlite3.connect(snapshot_sqlite_path)
            conn.execute("PRAGMA query_only = ON")
            conn.row_factory = None
            try:
                yield conn
            finally:
                conn.close()
        finally:
            shutil.rmtree(snapshot_dir, ignore_errors=True)

    @staticmethod
    def _extract_year(date_value: str | None) -> str | None:
        if not date_value:
            return None
        cleaned = str(date_value).replace("/", "-")
        for token in cleaned.split("-"):
            token = token.strip()
            if len(token) == 4 and token.isdigit():
                return token
        return cleaned[:4] if len(cleaned) >= 4 else cleaned
