from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    ops_db_path: Path = Path(os.getenv("SWS_OPS_DB", BASE_DIR / "var" / "ops.sqlite3"))
    dashboard_user: str | None = os.getenv("SWS_DASHBOARD_USER")
    dashboard_password: str | None = os.getenv("SWS_DASHBOARD_PASSWORD")
    timezone: str = os.getenv("SWS_TIMEZONE", "Asia/Taipei")


settings = Settings()
