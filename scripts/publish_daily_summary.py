#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mvp01.ops_db import OpsDB
from mvp01.settings import settings

ALLOWED = {
    "active_stocks", "price_ready", "foreign_ready", "tdcc_ready", "ranking_rows",
    "sleep_pass", "foreign_pass", "tdcc_pass", "chip_pass", "breakout_pass", "final_pass",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish coverage/strategy metrics to MVP-01 dashboard")
    parser.add_argument("--date", required=True)
    parser.add_argument("--json", required=True, help="Path to a JSON object")
    args = parser.parse_args()

    data = json.loads(Path(args.json).read_text(encoding="utf-8"))
    unknown = set(data) - ALLOWED
    if unknown:
        raise SystemExit(f"unsupported metric keys: {', '.join(sorted(unknown))}")
    OpsDB(settings.ops_db_path).upsert_metrics(args.date, data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
