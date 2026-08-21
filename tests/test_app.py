from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from mvp01 import app as app_module
from mvp01.ops_db import OpsDB


def test_dashboard_renders_latest_snapshot(monkeypatch):
    with TemporaryDirectory() as td:
        path = Path(td) / "ops.sqlite3"
        ops = OpsDB(path)
        run_id = ops.start_run("2026-08-21")
        step_id = ops.start_step(run_id, "2026-08-21", "price")
        ops.finish_step(step_id, "SUCCESS")
        ops.upsert_metrics("2026-08-21", {"active_stocks": 1979})
        ops.finish_run(run_id, "SUCCESS")
        monkeypatch.setattr(app_module, "db", lambda: ops)
        client = TestClient(app_module.app)
        response = client.get("/")
        assert response.status_code == 200
        assert "StockWaveScanner" in response.text
        assert "1979" in response.text
