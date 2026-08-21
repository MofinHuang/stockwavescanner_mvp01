import os
from pathlib import Path
from tempfile import TemporaryDirectory

from mvp01.ops_db import OpsDB
from mvp01.pipeline import Step, run_daily


def test_resume_does_not_repeat_successful_step(monkeypatch):
    with TemporaryDirectory() as td:
        db = OpsDB(Path(td) / "ops.sqlite3")
        monkeypatch.setenv("SWS_TEST_CMD", "python -c \"print('ok')\"")
        steps = (Step("test", "SWS_TEST_CMD"),)
        assert run_daily(db, "2026-08-21", workdir=td, steps=steps) == 0
        assert run_daily(db, "2026-08-21", workdir=td, steps=steps) == 0
        snap = db.latest_snapshot()
        assert snap["steps"][0]["status"] == "ALREADY_SUCCESS"
