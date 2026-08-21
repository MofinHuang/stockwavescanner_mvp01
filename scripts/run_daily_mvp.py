#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mvp01.ops_db import OpsDB
from mvp01.pipeline import run_daily
from mvp01.settings import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run StockWaveScanner daily pipeline")
    parser.add_argument(
        "--date",
        dest="as_of_date",
        default=datetime.now(ZoneInfo(settings.timezone)).date().isoformat(),
    )
    parser.add_argument("--workdir", default=os.getenv("SWS_PROJECT_DIR", str(ROOT)))
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    db = OpsDB(settings.ops_db_path)
    return run_daily(db, args.as_of_date, workdir=args.workdir, resume=not args.no_resume)


if __name__ == "__main__":
    raise SystemExit(main())
