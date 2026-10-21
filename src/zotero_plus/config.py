from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _get_env_or_winreg(name: str) -> str | None:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg_key:
                val, _ = winreg.QueryValueEx(reg_key, name)
                if val and str(val).strip():
                    return str(val).strip()
        except Exception:
            pass
    return os.getenv(name)


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


@dataclass(slots=True)
class AppConfig:
    zotero_sqlite_path: Path
    zotero_storage_dir: Path
    cache_dir: Path
    output_dir: Path = Path("output")
    zotero_user_id: str | None = None
    zotero_api_key: str | None = None
    zotero_local_api_key: str | None = None
    mutation_backend: str = "auto"
    local_api_url: str = "http://127.0.0.1:23119/api"
    remote_api_url: str = "https://api.zotero.org"

    @property
    def pdf_cache_dir(self) -> Path:
        return self.cache_dir / "pdf_text_cache"

    @property
    def analysis_summary_dir(self) -> Path:
        return self.cache_dir / "analysis_summaries"

    @property
    def backup_dir(self) -> Path:
        return self.cache_dir / "backups"

    @property
    def local_key_file(self) -> Path:
        return self.cache_dir / "local_api_key.txt"

    def get_effective_local_key(self) -> str | None:
        if self.zotero_local_api_key:
            return self.zotero_local_api_key
        if sys.platform == "win32":
            try:
                import winreg

                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as reg_key:
                    val, _ = winreg.QueryValueEx(reg_key, "ZOTERO_LOCAL_API_KEY")
                    if val and str(val).strip():
                        return str(val).strip()
            except Exception:
                pass
        if self.local_key_file.exists():
            content = self.local_key_file.read_text(encoding="utf-8").strip()
            if content:
                return content
        return None

    def save_local_key(self, key: str) -> None:
        cleaned_key = key.strip()
        self.zotero_local_api_key = cleaned_key
        if sys.platform == "win32":
            try:
                import winreg

                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as reg_key:
                    winreg.SetValueEx(reg_key, "ZOTERO_LOCAL_API_KEY", 0, winreg.REG_SZ, cleaned_key)
            except Exception:
                pass

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()

        sqlite_path = os.getenv("ZOTERO_SQLITE_PATH")
        storage_dir = os.getenv("ZOTERO_STORAGE_DIR")
        cache_dir = os.getenv("ZOTERO_CACHE_DIR")
        output_dir = os.getenv("ZOTERO_OUTPUT_DIR", "output")
        user_id = _get_env_or_winreg("ZOTERO_USER_ID")
        api_key = _get_env_or_winreg("ZOTERO_API_KEY")
        local_key = _get_env_or_winreg("ZOTERO_LOCAL_API_KEY")
        backend = os.getenv("ZOTERO_MUTATION_BACKEND", "auto")
        local_api_url = os.getenv("ZOTERO_LOCAL_API_URL", "http://127.0.0.1:23119/api")
        remote_api_url = os.getenv("ZOTERO_REMOTE_API_URL", "https://api.zotero.org")

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

        config = cls(
            zotero_sqlite_path=resolved_sqlite_path,
            zotero_storage_dir=resolved_storage_dir,
            cache_dir=resolved_cache_dir,
            output_dir=Path(output_dir).expanduser(),
            zotero_user_id=user_id,
            zotero_api_key=api_key,
            zotero_local_api_key=local_key,
            mutation_backend=backend,
            local_api_url=local_api_url,
            remote_api_url=remote_api_url,
        )

        if not config.zotero_local_api_key:
            config.zotero_local_api_key = config.get_effective_local_key()

        return config
