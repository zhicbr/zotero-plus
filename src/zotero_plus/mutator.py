from __future__ import annotations

import datetime
import json
import shutil
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import AppConfig
from .zotero_client import ZoteroLibrary


class MutationError(RuntimeError):
    """Raised when a mutation operation fails."""


class ZoteroMutator:
    def __init__(self, config: AppConfig, library: ZoteroLibrary | None = None) -> None:
        self.config = config
        self.library = library or ZoteroLibrary(config)
        self._cached_server_id: str | None = None
        self._has_backed_up_this_session: bool = False

    def create_snapshot_backup(self, max_keep: int = 10) -> dict[str, Any]:
        """
        Create a consistent hot snapshot of zotero.sqlite and WAL files.
        Safely copies the database even while Zotero is actively running.
        """
        backup_root = self.config.backup_dir
        backup_root.mkdir(parents=True, exist_ok=True)

        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        snapshot_dir = backup_root / f"backup_{timestamp}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        sqlite_path = self.config.zotero_sqlite_path
        target_sqlite = snapshot_dir / sqlite_path.name
        shutil.copy2(sqlite_path, target_sqlite)

        wal_path = sqlite_path.with_name(f"{sqlite_path.name}-wal")
        shm_path = sqlite_path.with_name(f"{sqlite_path.name}-shm")
        if wal_path.exists():
            shutil.copy2(wal_path, snapshot_dir / wal_path.name)
        if shm_path.exists():
            shutil.copy2(shm_path, snapshot_dir / shm_path.name)

        # Truncate/checkpoint the copied SQLite DB to ensure it's a completely standalone clean DB
        try:
            with sqlite3.connect(target_sqlite) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass

        # Rotate older backups keeping max_keep
        all_backups = sorted(backup_root.glob("backup_*"), key=lambda p: p.name)
        deleted_count = 0
        if len(all_backups) > max_keep:
            for old in all_backups[:-max_keep]:
                shutil.rmtree(old, ignore_errors=True)
                deleted_count += 1

        self._has_backed_up_this_session = True
        return {
            "status": "backup_created",
            "snapshot_dir": str(snapshot_dir),
            "sqlite_file": str(target_sqlite),
            "timestamp": timestamp,
            "total_backups_retained": min(len(all_backups), max_keep),
        }

    def get_server_id(self, force_refresh: bool = False) -> str:
        """Fetch the Zotero-Server-ID header from the local Zotero instance."""
        if self._cached_server_id and not force_refresh:
            return self._cached_server_id

        req = urllib.request.Request(f"{self.config.local_api_url}/", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                server_id = resp.headers.get("Zotero-Server-ID")
                if not server_id:
                    raise MutationError("Local Zotero responded, but Zotero-Server-ID header is missing.")
                self._cached_server_id = server_id
                return server_id
        except Exception as e:
            raise MutationError(
                f"Failed to connect to local Zotero at {self.config.local_api_url}. "
                "Ensure Zotero is running and 'Allow other applications on this computer to communicate with Zotero' is enabled."
            ) from e

    def is_local_api_available(self) -> bool:
        """Check if local Zotero 7/10 HTTP server is responsive."""
        try:
            req = urllib.request.Request(f"{self.config.local_api_url}/", method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def authorize_local(self, app_name: str = "zotero-plus") -> dict[str, Any]:
        """Initiate authorization dialog inside running Zotero desktop and obtain local API key."""
        server_id = self.get_server_id(force_refresh=True)
        url = f"{self.config.local_api_url}/local/authorize"

        payload = json.dumps({"appName": app_name}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Zotero-Server-ID", server_id)

        try:
            # Wait for user confirmation in Zotero desktop UI (dialog may take time)
            with urllib.request.urlopen(req, timeout=120.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                api_key = data.get("key") or data.get("apiKey")
                if not api_key:
                    raise MutationError(f"Unexpected response from authorize: {data}")

                self.config.save_local_key(api_key)
                return {
                    "status": "authorized",
                    "app_name": app_name,
                    "apiKey": api_key,
                    "saved_to": str(self.config.local_key_file),
                }
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise MutationError("Authorization was denied in the Zotero confirmation dialog.") from e
            raise MutationError(f"Local authorization failed with HTTP {e.code}: {e.read().decode('utf-8')}") from e
        except Exception as e:
            raise MutationError(f"Local authorization failed: {e}") from e

    def resolve_backend(self, backend_override: str | None = None) -> tuple[str, str, str, str]:
        """
        Returns (effective_backend, base_url, user_id, api_key).
        effective_backend is either 'local' or 'remote'.
        """
        choice = (backend_override or self.config.mutation_backend).lower()

        if choice == "auto":
            if self.is_local_api_available():
                choice = "local"
            else:
                choice = "remote"

        if choice == "local":
            local_key = self.config.get_effective_local_key()
            if not local_key:
                raise MutationError(
                    "Local API key not found. Please run 'zotero-skill auth' first "
                    "to grant write permissions in your Zotero desktop application."
                )
            base_url = f"{self.config.local_api_url}/users/0"
            return "local", base_url, "0", local_key

        if choice == "remote":
            user_id = self.config.zotero_user_id
            api_key = self.config.zotero_api_key
            if not user_id or not api_key:
                raise MutationError(
                    "Remote backend requires ZOTERO_USER_ID and ZOTERO_API_KEY environment variables."
                )
            base_url = f"{self.config.remote_api_url}/users/{user_id}"
            return "remote", base_url, user_id, api_key

        raise MutationError(f"Unknown mutation backend: {choice}. Valid options: local, remote, auto.")

    def _api_request(
        self,
        method: str,
        path: str,
        payload: dict | list | None = None,
        extra_headers: dict[str, str] | None = None,
        backend_override: str | None = None,
    ) -> tuple[int, Any, dict[str, str]]:
        backend_type, base_url, user_id, api_key = self.resolve_backend(backend_override)

        url = f"{base_url}{path}"
        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None

        req = urllib.request.Request(url, data=data_bytes, method=method)
        req.add_header("Zotero-API-Version", "3")
        req.add_header("Zotero-API-Key", api_key)
        if data_bytes is not None:
            req.add_header("Content-Type", "application/json")

        if backend_type == "local":
            server_id = self.get_server_id()
            req.add_header("Zotero-Server-ID", server_id)

        if extra_headers:
            for k, v in extra_headers.items():
                req.add_header(k, v)

        # Safety auto-backup before any mutation request
        if method.upper() in ("POST", "PATCH", "DELETE") and not self._has_backed_up_this_session:
            self.create_snapshot_backup()

        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                status = resp.status
                resp_headers = {k: v for k, v in resp.headers.items()}
                content = resp.read().decode("utf-8")
                body = json.loads(content) if content.strip() else None
                return status, body, resp_headers
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            if e.code == 401 and backend_type == "local":
                raise MutationError(
                    "Local authorization expired or invalid. Please re-run 'zotero-skill auth'."
                ) from e
            if e.code == 412:
                raise MutationError("Conflict detected: target item or collection was modified elsewhere.") from e
            raise MutationError(f"Zotero API error (HTTP {e.code}): {err_body}") from e
        except Exception as e:
            raise MutationError(f"Request failed ({method} {url}): {e}") from e

    # -------------------------------------------------------------------------
    # Collection Mutations
    # -------------------------------------------------------------------------

    def create_collection(
        self,
        name: str,
        parent_key: str | None = None,
        dry_run: bool = False,
        backend_override: str | None = None,
    ) -> dict[str, Any]:
        if not name or not name.strip():
            raise ValueError("Collection name cannot be empty.")

        if parent_key:
            # Validate parent collection exists
            parent = self.library.get_collection_by_key(parent_key)
            parent_name = parent.name
        else:
            parent_name = None

        if dry_run:
            return {
                "action": "create_collection",
                "name": name,
                "parent_key": parent_key,
                "parent_name": parent_name,
                "dry_run": True,
                "status": "planned",
            }

        payload = [{"name": name.strip(), "parentCollection": parent_key or False}]
        status, body, headers = self._api_request(
            "POST", "/collections", payload=payload, backend_override=backend_override
        )

        new_key = None
        if isinstance(body, dict):
            success = body.get("success", {})
            if "0" in success:
                new_key = success["0"]

        return {
            "action": "create_collection",
            "status": "created",
            "collection_key": new_key,
            "name": name,
            "parent_key": parent_key,
            "parent_name": parent_name,
        }

    def rename_collection(
        self,
        collection_key: str,
        new_name: str,
        dry_run: bool = False,
        backend_override: str | None = None,
    ) -> dict[str, Any]:
        if not new_name or not new_name.strip():
            raise ValueError("New collection name cannot be empty.")

        status, body, headers = self._api_request(
            "GET", f"/collections/{collection_key}", backend_override=backend_override
        )
        if not body:
            raise MutationError(f"Collection {collection_key} not found.")

        old_name = body.get("data", {}).get("name", "")
        version = body.get("version") or headers.get("Last-Modified-Version")

        if dry_run:
            return {
                "action": "rename_collection",
                "collection_key": collection_key,
                "old_name": old_name,
                "new_name": new_name.strip(),
                "dry_run": True,
                "status": "planned",
            }

        patch_payload = {"name": new_name.strip()}
        extra_headers = {"If-Unmodified-Since-Version": str(version)} if version else {}
        self._api_request(
            "PATCH",
            f"/collections/{collection_key}",
            payload=patch_payload,
            extra_headers=extra_headers,
            backend_override=backend_override,
        )

        return {
            "action": "rename_collection",
            "status": "renamed",
            "collection_key": collection_key,
            "old_name": old_name,
            "new_name": new_name.strip(),
        }

    def delete_empty_collection(
        self,
        collection_key: str,
        dry_run: bool = False,
        backend_override: str | None = None,
    ) -> dict[str, Any]:
        # Strict safety check: verify existence and emptiness via API
        status, body, headers = self._api_request(
            "GET", f"/collections/{collection_key}", backend_override=backend_override
        )
        if not body:
            raise MutationError(f"Collection not found: {collection_key}")

        col_name = body.get("data", {}).get("name", collection_key)
        version = body.get("version") or headers.get("Last-Modified-Version")

        # Check subcollections
        _, subcols, _ = self._api_request(
            "GET",
            f"/collections/{collection_key}/collections?limit=1",
            backend_override=backend_override,
        )
        if subcols and len(subcols) > 0:
            raise MutationError(
                f"Collection '{col_name}' ({collection_key}) contains subcollections. "
                "Refusing to delete for safety."
            )

        # Check items
        _, items, _ = self._api_request(
            "GET",
            f"/collections/{collection_key}/items?limit=1",
            backend_override=backend_override,
        )
        if items and len(items) > 0:
            raise MutationError(
                f"Collection '{col_name}' ({collection_key}) contains paper items. "
                "Refusing to delete non-empty collection. Please remove or move items first."
            )

        if dry_run:
            return {
                "action": "delete_empty_collection",
                "collection_key": collection_key,
                "name": col_name,
                "dry_run": True,
                "status": "planned",
            }

        extra_headers = {"If-Unmodified-Since-Version": str(version)} if version else {}
        self._api_request(
            "DELETE",
            f"/collections/{collection_key}",
            extra_headers=extra_headers,
            backend_override=backend_override,
        )

        return {
            "action": "delete_empty_collection",
            "status": "deleted",
            "collection_key": collection_key,
            "name": col_name,
        }

    # -------------------------------------------------------------------------
    # Paper Item Collection Assignment Mutations
    # -------------------------------------------------------------------------

    def add_to_collection(
        self,
        paper_key: str,
        collection_key: str,
        dry_run: bool = False,
        backend_override: str | None = None,
    ) -> dict[str, Any]:
        # Validate target collection exists
        col = self.library.get_collection_by_key(collection_key)

        status, body, headers = self._api_request(
            "GET", f"/items/{paper_key}", backend_override=backend_override
        )
        if not body:
            raise MutationError(f"Paper item {paper_key} not found.")

        item_data = body.get("data", {})
        title = item_data.get("title", "")
        current_cols = item_data.get("collections", [])
        version = body.get("version") or headers.get("Last-Modified-Version")

        if collection_key in current_cols:
            return {
                "action": "add_to_collection",
                "status": "unchanged",
                "paper_key": paper_key,
                "title": title,
                "collection_key": collection_key,
                "collection_name": col.name,
                "message": "Item is already assigned to this collection.",
            }

        new_cols = list(current_cols) + [collection_key]

        if dry_run:
            return {
                "action": "add_to_collection",
                "paper_key": paper_key,
                "title": title,
                "collection_key": collection_key,
                "collection_name": col.name,
                "dry_run": True,
                "status": "planned",
            }

        extra_headers = {"If-Unmodified-Since-Version": str(version)} if version else {}
        self._api_request(
            "PATCH",
            f"/items/{paper_key}",
            payload={"collections": new_cols},
            extra_headers=extra_headers,
            backend_override=backend_override,
        )

        return {
            "action": "add_to_collection",
            "status": "added",
            "paper_key": paper_key,
            "title": title,
            "collection_key": collection_key,
            "collection_name": col.name,
        }

    def remove_from_collection(
        self,
        paper_key: str,
        collection_key: str,
        dry_run: bool = False,
        backend_override: str | None = None,
    ) -> dict[str, Any]:
        col = self.library.get_collection_by_key(collection_key)

        status, body, headers = self._api_request(
            "GET", f"/items/{paper_key}", backend_override=backend_override
        )
        if not body:
            raise MutationError(f"Paper item {paper_key} not found.")

        item_data = body.get("data", {})
        title = item_data.get("title", "")
        current_cols = item_data.get("collections", [])
        version = body.get("version") or headers.get("Last-Modified-Version")

        if collection_key not in current_cols:
            return {
                "action": "remove_from_collection",
                "status": "unchanged",
                "paper_key": paper_key,
                "title": title,
                "collection_key": collection_key,
                "collection_name": col.name,
                "message": "Item is not in this collection.",
            }

        new_cols = [k for k in current_cols if k != collection_key]

        if dry_run:
            return {
                "action": "remove_from_collection",
                "paper_key": paper_key,
                "title": title,
                "collection_key": collection_key,
                "collection_name": col.name,
                "dry_run": True,
                "status": "planned",
            }

        extra_headers = {"If-Unmodified-Since-Version": str(version)} if version else {}
        self._api_request(
            "PATCH",
            f"/items/{paper_key}",
            payload={"collections": new_cols},
            extra_headers=extra_headers,
            backend_override=backend_override,
        )

        return {
            "action": "remove_from_collection",
            "status": "removed",
            "paper_key": paper_key,
            "title": title,
            "collection_key": collection_key,
            "collection_name": col.name,
        }

    def move_paper(
        self,
        paper_key: str,
        to_collection_key: str,
        from_collection_key: str | None = None,
        dry_run: bool = False,
        backend_override: str | None = None,
    ) -> dict[str, Any]:
        to_col = self.library.get_collection_by_key(to_collection_key)

        status, body, headers = self._api_request(
            "GET", f"/items/{paper_key}", backend_override=backend_override
        )
        if not body:
            raise MutationError(f"Paper item {paper_key} not found.")

        item_data = body.get("data", {})
        title = item_data.get("title", "")
        current_cols = item_data.get("collections", [])
        version = body.get("version") or headers.get("Last-Modified-Version")

        # Determine source collection if omitted
        effective_from = from_collection_key
        if not effective_from:
            if len(current_cols) == 1 and current_cols[0] != to_collection_key:
                effective_from = current_cols[0]
            elif to_collection_key in current_cols and len(current_cols) == 1:
                return {
                    "action": "move_paper",
                    "status": "unchanged",
                    "paper_key": paper_key,
                    "title": title,
                    "to_collection": to_collection_key,
                    "message": "Item is already only in target collection.",
                }

        from_col_name = None
        if effective_from:
            try:
                from_col = self.library.get_collection_by_key(effective_from)
                from_col_name = from_col.name
            except Exception:
                from_col_name = effective_from

        # Calculate new collection list
        if effective_from:
            new_cols = [k for k in current_cols if k != effective_from]
        else:
            new_cols = list(current_cols)

        if to_collection_key not in new_cols:
            new_cols.append(to_collection_key)

        if dry_run:
            return {
                "action": "move_paper",
                "paper_key": paper_key,
                "title": title,
                "from_collection_key": effective_from,
                "from_collection_name": from_col_name,
                "to_collection_key": to_collection_key,
                "to_collection_name": to_col.name,
                "dry_run": True,
                "status": "planned",
            }

        extra_headers = {"If-Unmodified-Since-Version": str(version)} if version else {}
        self._api_request(
            "PATCH",
            f"/items/{paper_key}",
            payload={"collections": new_cols},
            extra_headers=extra_headers,
            backend_override=backend_override,
        )

        return {
            "action": "move_paper",
            "status": "moved",
            "paper_key": paper_key,
            "title": title,
            "from_collection_key": effective_from,
            "from_collection_name": from_col_name,
            "to_collection_key": to_collection_key,
            "to_collection_name": to_col.name,
        }

    # -------------------------------------------------------------------------
    # Tag Mutations
    # -------------------------------------------------------------------------

    def add_tag(
        self,
        paper_key: str,
        tag: str,
        dry_run: bool = False,
        backend_override: str | None = None,
    ) -> dict[str, Any]:
        clean_tag = tag.strip()
        if not clean_tag:
            raise ValueError("Tag name cannot be empty.")

        status, body, headers = self._api_request(
            "GET", f"/items/{paper_key}", backend_override=backend_override
        )
        if not body:
            raise MutationError(f"Paper item {paper_key} not found.")

        item_data = body.get("data", {})
        title = item_data.get("title", "")
        current_tags = item_data.get("tags", [])
        version = body.get("version") or headers.get("Last-Modified-Version")

        for t in current_tags:
            if t.get("tag", "").casefold() == clean_tag.casefold():
                return {
                    "action": "add_tag",
                    "status": "unchanged",
                    "paper_key": paper_key,
                    "title": title,
                    "tag": clean_tag,
                    "message": "Tag already assigned to item.",
                }

        new_tags = list(current_tags) + [{"tag": clean_tag}]

        if dry_run:
            return {
                "action": "add_tag",
                "paper_key": paper_key,
                "title": title,
                "tag": clean_tag,
                "dry_run": True,
                "status": "planned",
            }

        extra_headers = {"If-Unmodified-Since-Version": str(version)} if version else {}
        self._api_request(
            "PATCH",
            f"/items/{paper_key}",
            payload={"tags": new_tags},
            extra_headers=extra_headers,
            backend_override=backend_override,
        )

        return {
            "action": "add_tag",
            "status": "added",
            "paper_key": paper_key,
            "title": title,
            "tag": clean_tag,
        }

    def remove_tag(
        self,
        paper_key: str,
        tag: str,
        dry_run: bool = False,
        backend_override: str | None = None,
    ) -> dict[str, Any]:
        clean_tag = tag.strip()
        if not clean_tag:
            raise ValueError("Tag name cannot be empty.")

        status, body, headers = self._api_request(
            "GET", f"/items/{paper_key}", backend_override=backend_override
        )
        if not body:
            raise MutationError(f"Paper item {paper_key} not found.")

        item_data = body.get("data", {})
        title = item_data.get("title", "")
        current_tags = item_data.get("tags", [])
        version = body.get("version") or headers.get("Last-Modified-Version")

        matched = any(t.get("tag", "").casefold() == clean_tag.casefold() for t in current_tags)
        if not matched:
            return {
                "action": "remove_tag",
                "status": "unchanged",
                "paper_key": paper_key,
                "title": title,
                "tag": clean_tag,
                "message": "Tag not found on this item.",
            }

        new_tags = [t for t in current_tags if t.get("tag", "").casefold() != clean_tag.casefold()]

        if dry_run:
            return {
                "action": "remove_tag",
                "paper_key": paper_key,
                "title": title,
                "tag": clean_tag,
                "dry_run": True,
                "status": "planned",
            }

        extra_headers = {"If-Unmodified-Since-Version": str(version)} if version else {}
        self._api_request(
            "PATCH",
            f"/items/{paper_key}",
            payload={"tags": new_tags},
            extra_headers=extra_headers,
            backend_override=backend_override,
        )

        return {
            "action": "remove_tag",
            "status": "removed",
            "paper_key": paper_key,
            "title": title,
            "tag": clean_tag,
        }
