from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(slots=True)
class AppConfig:
    zotero_sqlite_path: Path
    zotero_storage_dir: Path
    cache_dir: Path
    output_dir: Path = Path("output")

    @property
    def pdf_cache_dir(self) -> Path:
        return self.cache_dir / "pdf_text_cache"

    @property
    def analysis_summary_dir(self) -> Path:
        return self.cache_dir / "analysis_summaries"

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()

        sqlite_path = os.getenv("ZOTERO_SQLITE_PATH")
        storage_dir = os.getenv("ZOTERO_STORAGE_DIR")
        cache_dir = os.getenv("ZOTERO_CACHE_DIR")
        output_dir = os.getenv("ZOTERO_OUTPUT_DIR", "output")

        missing = [
            name
            for name, value in (
                ("ZOTERO_SQLITE_PATH", sqlite_path),
                ("ZOTERO_STORAGE_DIR", storage_dir),
            )
            if not value
        ]
        if missing:
            raise ConfigError(f"Missing required environment variables: {', '.join(missing)}")

        resolved_sqlite_path = Path(sqlite_path).expanduser()
        resolved_storage_dir = Path(storage_dir).expanduser()

        if not resolved_sqlite_path.exists():
            raise ConfigError(f"ZOTERO_SQLITE_PATH does not exist: {resolved_sqlite_path}")
        if not resolved_storage_dir.exists():
            raise ConfigError(f"ZOTERO_STORAGE_DIR does not exist: {resolved_storage_dir}")

        if cache_dir:
            resolved_cache_dir = Path(cache_dir).expanduser()
        else:
            resolved_cache_dir = resolved_storage_dir.parent / "zotero_plus_cache"

        return cls(
            zotero_sqlite_path=resolved_sqlite_path,
            zotero_storage_dir=resolved_storage_dir,
            cache_dir=resolved_cache_dir,
            output_dir=Path(output_dir).expanduser(),
        )
