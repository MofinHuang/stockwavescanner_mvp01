from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .ops_db import OpsDB


@dataclass(frozen=True)
class Step:
    name: str
    env_var: str
    depends_on: tuple[str, ...] = ()


STEPS: tuple[Step, ...] = (
    Step("price", "SWS_STEP_PRICE_CMD"),
    Step("foreign_twse", "SWS_STEP_FOREIGN_TWSE_CMD"),
    Step("foreign_tpex", "SWS_STEP_FOREIGN_TPEX_CMD"),
    Step("tdcc_latest", "SWS_STEP_TDCC_LATEST_CMD"),
    Step(
        "coverage",
        "SWS_STEP_COVERAGE_CMD",
        ("price", "foreign_twse", "foreign_tpex", "tdcc_latest"),
    ),
    Step("ranking", "SWS_STEP_RANKING_CMD", ("coverage",)),
)


def _tail(text: str | None, limit: int = 4000) -> str | None:
    if not text:
        return None
    return text[-limit:]


def _command_for(step: Step, as_of_date: str) -> list[str] | None:
    raw = os.getenv(step.env_var)
    if not raw:
        return None
    # Explicit token substitution; avoids date.today() dependency in orchestration.
    raw = raw.replace("{as_of_date}", as_of_date)
    return shlex.split(raw)


def run_daily(
    db: OpsDB,
    as_of_date: str,
    *,
    workdir: Path | str | None = None,
    resume: bool = True,
    steps: Iterable[Step] = STEPS,
) -> int:
    run_id = db.start_run(as_of_date)
    statuses: dict[str, str] = {}
    failed: list[str] = []

    try:
        for step in steps:
            if any(statuses.get(dep) not in {"SUCCESS", "ALREADY_SUCCESS"} for dep in step.depends_on):
                step_id = db.start_step(run_id, as_of_date, step.name)
                db.finish_step(step_id, "BLOCKED", message="dependency failed or blocked")
                statuses[step.name] = "BLOCKED"
                failed.append(step.name)
                continue

            if resume and db.has_success(as_of_date, step.name):
                step_id = db.start_step(run_id, as_of_date, step.name)
                db.finish_step(step_id, "ALREADY_SUCCESS", message="resume: prior SUCCESS kept")
                statuses[step.name] = "ALREADY_SUCCESS"
                continue

            command = _command_for(step, as_of_date)
            step_id = db.start_step(run_id, as_of_date, step.name)
            if command is None:
                db.finish_step(step_id, "CONFIG_ERROR", message=f"missing {step.env_var}")
                statuses[step.name] = "CONFIG_ERROR"
                failed.append(step.name)
                continue

            result = subprocess.run(
                command,
                cwd=str(workdir) if workdir else None,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                db.finish_step(
                    step_id,
                    "SUCCESS",
                    exit_code=0,
                    stdout_tail=_tail(result.stdout),
                    stderr_tail=_tail(result.stderr),
                )
                statuses[step.name] = "SUCCESS"
            else:
                db.finish_step(
                    step_id,
                    "ERROR",
                    exit_code=result.returncode,
                    message="command failed",
                    stdout_tail=_tail(result.stdout),
                    stderr_tail=_tail(result.stderr),
                )
                statuses[step.name] = "ERROR"
                failed.append(step.name)

        final = "SUCCESS" if not failed else "ERROR"
        db.finish_run(run_id, final, None if not failed else f"failed: {', '.join(failed)}")
        return 0 if final == "SUCCESS" else 1
    except Exception as exc:
        db.finish_run(run_id, "ERROR", f"pipeline exception: {exc}")
        raise
