from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
TAX_RATE = Decimal("0.19")


def user_data_dir(
    platform: str,
    environ: Mapping[str, str],
    home: Path,
) -> Path:
    if platform == "win32":
        local = environ.get("LOCALAPPDATA")
        base = Path(local) if local else home / "AppData" / "Local"
        return base / "Crypto-PIT"
    if platform == "darwin":
        return home / "Library" / "Application Support" / "Crypto-PIT"
    xdg = environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else home / ".local" / "share"
    return base / "crypto-pit"


def resolve_db_path(
    *,
    project_root: Path,
    platform: str,
    environ: Mapping[str, str],
    home: Path,
) -> Path:
    legacy = project_root / "data" / "crypto_pit.db"
    if legacy.is_file():
        return legacy
    return user_data_dir(platform, environ, home) / "crypto_pit.db"


DEFAULT_DB_PATH = resolve_db_path(
    project_root=PROJECT_ROOT,
    platform=sys.platform,
    environ=os.environ,
    home=Path.home(),
)
