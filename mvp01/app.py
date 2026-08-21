from __future__ import annotations

import hmac
import json
from html import escape

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .ops_db import OpsDB
from .settings import settings

app = FastAPI(title="StockWaveScanner", version="mvp01")
security = HTTPBasic(auto_error=False)


def db() -> OpsDB:
    return OpsDB(settings.ops_db_path)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    user = settings.dashboard_user
    password = settings.dashboard_password
    if not user and not password:
        return
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Basic"})
    ok = hmac.compare_digest(credentials.username, user or "") and hmac.compare_digest(
        credentials.password, password or ""
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Basic"})


def badge(status_text: str) -> str:
    klass = "ok" if status_text in {"SUCCESS", "ALREADY_SUCCESS"} else "run" if status_text == "RUNNING" else "bad"
    return f'<span class="badge {klass}">{escape(status_text)}</span>'


def metric(metrics: dict, key: str) -> str:
    value = metrics.get(key, "-")
    if isinstance(value, (dict, list)):
        return escape(json.dumps(value, ensure_ascii=False))
    return escape(str(value))


@app.get("/healthz")
def healthz() -> JSONResponse:
    snap = db().latest_snapshot()
    return JSONResponse({"ok": True, "latest_run_status": snap["run"]["status"] if snap["run"] else None})


@app.get("/api/daily/latest", dependencies=[Depends(require_auth)])
def latest() -> JSONResponse:
    return JSONResponse(db().latest_snapshot())


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
def home() -> HTMLResponse:
    snap = db().latest_snapshot()
    run = snap["run"]
    steps = snap["steps"]
    metrics = snap["metrics"]

    if run is None:
        body = "<div class='empty'>尚無 daily run。先執行 scripts/run_daily_mvp.py。</div>"
        title = "No data"
    else:
        title = escape(run["as_of_date"])
        step_html = "".join(
            f"<div class='row'><div><b>{escape(s['step_name'])}</b><small>{escape(s.get('message') or '')}</small></div>{badge(s['status'])}</div>"
            for s in steps
        )
        cards = [
            ("Active", "active_stocks"),
            ("Price ready", "price_ready"),
            ("Foreign ready", "foreign_ready"),
            ("TDCC ready", "tdcc_ready"),
            ("Ranking", "ranking_rows"),
            ("Sleep PASS", "sleep_pass"),
            ("Foreign PASS", "foreign_pass"),
            ("TDCC PASS", "tdcc_pass"),
            ("Chip PASS", "chip_pass"),
            ("Breakout PASS", "breakout_pass"),
            ("Final PASS", "final_pass"),
        ]
        card_html = "".join(
            f"<div class='card'><span>{escape(label)}</span><strong>{metric(metrics, key)}</strong></div>"
            for label, key in cards
        )
        error = f"<p class='error'>{escape(run.get('error_message') or '')}</p>" if run.get("error_message") else ""
        body = f"""
        <section><div class='headline'><div><small>Trading date</small><h2>{title}</h2></div>{badge(run['status'])}</div>{error}</section>
        <section><h3>Daily Sync</h3><div class='panel'>{step_html}</div></section>
        <section><h3>Coverage & Strategy</h3><div class='grid'>{card_html}</div></section>
        """

    html = f"""<!doctype html>
<html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>StockWaveScanner</title>
<style>
:root{{--bg:#f5f7fb;--panel:#fff;--text:#172033;--muted:#748096;--line:#e5eaf2;--ok:#16794b;--bad:#b42318;--run:#a15c00}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:760px;margin:auto;padding:18px}}header{{padding:8px 2px 16px}}h1{{font-size:24px;margin:0}}h2{{font-size:26px;margin:2px 0}}h3{{font-size:15px;margin:22px 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
section,.panel,.card{{background:var(--panel);border:1px solid var(--line);border-radius:16px}}section{{padding:16px;margin-bottom:12px}}section .panel{{border:0;border-radius:0;padding:0}}
.headline,.row{{display:flex;align-items:center;justify-content:space-between;gap:12px}}.row{{padding:12px 0;border-bottom:1px solid var(--line)}}.row:last-child{{border:0}}small{{display:block;color:var(--muted);font-size:12px;margin-top:3px}}
.badge{{font-size:12px;font-weight:700;padding:5px 9px;border-radius:999px;background:#f1f3f6}}.badge.ok{{color:var(--ok);background:#eaf7f0}}.badge.bad{{color:var(--bad);background:#fef0ef}}.badge.run{{color:var(--run);background:#fff5e6}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.card{{padding:14px}}.card span{{display:block;color:var(--muted);font-size:12px}}.card strong{{display:block;font-size:22px;margin-top:4px}}.error{{color:var(--bad);font-size:13px}}.empty{{padding:24px;background:white;border-radius:16px}}
@media(min-width:640px){{.grid{{grid-template-columns:repeat(3,1fr)}}}}
</style></head><body><main><header><h1>StockWaveScanner</h1><small>MVP-01 Daily Data Platform</small></header>{body}</main></body></html>"""
    return HTMLResponse(html)
