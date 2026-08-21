from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    as_of_date TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_daily_runs_date ON daily_runs(as_of_date, id DESC);

CREATE TABLE IF NOT EXISTS daily_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    as_of_date TEXT NOT NULL,
    step_name TEXT NOT NULL,
    request_key TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    exit_code INTEGER,
    message TEXT,
    stdout_tail TEXT,
    stderr_tail TEXT,
    FOREIGN KEY(run_id) REFERENCES daily_runs(id)
);
CREATE INDEX IF NOT EXISTS idx_daily_steps_date_step ON daily_steps(as_of_date, step_name, id DESC);

CREATE TABLE IF NOT EXISTS daily_metrics (
    as_of_date TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    metric_value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(as_of_date, metric_key)
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class OpsDB:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def start_run(self, as_of_date: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO daily_runs(as_of_date,status,started_at) VALUES(?,?,?)",
                (as_of_date, "RUNNING", utc_now()),
            )
            return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, error_message: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE daily_runs SET status=?, finished_at=?, error_message=? WHERE id=?",
                (status, utc_now(), error_message, run_id),
            )

    def start_step(self, run_id: int, as_of_date: str, step_name: str) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO daily_steps(
                    run_id,as_of_date,step_name,request_key,status,started_at
                ) VALUES(?,?,?,?,?,?)""",
                (run_id, as_of_date, step_name, f"DAILY:{as_of_date}:{step_name}", "RUNNING", utc_now()),
            )
            return int(cur.lastrowid)

    def finish_step(
        self,
        step_id: int,
        status: str,
        *,
        exit_code: int | None = None,
        message: str | None = None,
        stdout_tail: str | None = None,
        stderr_tail: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE daily_steps
                   SET status=?, finished_at=?, exit_code=?, message=?, stdout_tail=?, stderr_tail=?
                   WHERE id=?""",
                (status, utc_now(), exit_code, message, stdout_tail, stderr_tail, step_id),
            )

    def has_success(self, as_of_date: str, step_name: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT 1 FROM daily_steps
                   WHERE as_of_date=? AND step_name=? AND status='SUCCESS'
                   ORDER BY id DESC LIMIT 1""",
                (as_of_date, step_name),
            ).fetchone()
            return row is not None

    def upsert_metrics(self, as_of_date: str, metrics: dict[str, Any]) -> None:
        now = utc_now()
        with self.connect() as conn:
            for key, value in metrics.items():
                encoded = json.dumps(value, ensure_ascii=False)
                conn.execute(
                    """INSERT INTO daily_metrics(as_of_date,metric_key,metric_value,updated_at)
                       VALUES(?,?,?,?)
                       ON CONFLICT(as_of_date,metric_key)
                       DO UPDATE SET metric_value=excluded.metric_value, updated_at=excluded.updated_at""",
                    (as_of_date, key, encoded, now),
                )

    def latest_snapshot(self) -> dict[str, Any]:
        with self.connect() as conn:
            run = conn.execute("SELECT * FROM daily_runs ORDER BY id DESC LIMIT 1").fetchone()
            if run is None:
                return {"run": None, "steps": [], "metrics": {}}
            as_of_date = run["as_of_date"]
            steps = conn.execute(
                """SELECT ds.* FROM daily_steps ds
                   JOIN (
                     SELECT step_name, MAX(id) AS max_id
                     FROM daily_steps WHERE as_of_date=? GROUP BY step_name
                   ) latest ON ds.id=latest.max_id
                   ORDER BY ds.id""",
                (as_of_date,),
            ).fetchall()
            metric_rows = conn.execute(
                "SELECT metric_key,metric_value FROM daily_metrics WHERE as_of_date=?",
                (as_of_date,),
            ).fetchall()
            metrics = {r["metric_key"]: json.loads(r["metric_value"]) for r in metric_rows}
            return {
                "run": dict(run),
                "steps": [dict(r) for r in steps],
                "metrics": metrics,
            }
