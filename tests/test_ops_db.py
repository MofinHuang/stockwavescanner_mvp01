from pathlib import Path
from tempfile import TemporaryDirectory

from mvp01.ops_db import OpsDB


def test_metrics_and_snapshot():
    with TemporaryDirectory() as td:
        db = OpsDB(Path(td) / "ops.sqlite3")
        run_id = db.start_run("2026-08-21")
        step_id = db.start_step(run_id, "2026-08-21", "price")
        db.finish_step(step_id, "SUCCESS")
        db.upsert_metrics("2026-08-21", {"active_stocks": 1979, "final_pass": 0})
        db.finish_run(run_id, "SUCCESS")
        snap = db.latest_snapshot()
        assert snap["run"]["status"] == "SUCCESS"
        assert snap["steps"][0]["status"] == "SUCCESS"
        assert snap["metrics"]["active_stocks"] == 1979
