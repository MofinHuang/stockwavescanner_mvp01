# StockWaveScanner MVP-01

Goal: make daily data collection self-running and make operational status readable from a phone, without changing strategy semantics.

## What this layer does

- Runs existing project entrypoints in a fixed dependency order.
- Passes an explicit `{as_of_date}` into every mapped command.
- Keeps a separate SQLite operational log with `RUNNING / SUCCESS / ERROR / BLOCKED / CONFIG_ERROR`.
- Uses `DAILY:<date>:<step>` request keys.
- Resume mode does not execute a step again after a prior `SUCCESS` for the same date.
- Provides a responsive FastAPI dashboard and JSON status endpoint.
- Accepts published coverage/strategy summary metrics without changing strategy logic.

It intentionally does **not** reimplement Price, Foreign, TDCC, ranking, or strategy rules. Existing verified project code remains the source of truth, including Raw-first behavior and TPEx/TDCC semantics.

## Integration

1. Copy this directory into the repository root (or copy its files into matching paths).
2. Create a virtualenv and install `requirements-mvp01.txt`.
3. Copy `.env.example` to `.env`.
4. Replace each `SWS_STEP_*_CMD` value with the repository's real, already verified command.
5. Make those scripts accept an explicit `--date` / `--as-of-date`; do not silently fall back to `date.today()` inside snapshot/backtest logic.
6. Run one historical-safe smoke test:

   `python scripts/run_daily_mvp.py --date 2026-08-21`

7. Publish metrics after validation/ranking by writing a JSON object and running:

   `python scripts/publish_daily_summary.py --date 2026-08-21 --json /path/to/summary.json`

8. Start the dashboard locally:

   `uvicorn mvp01.app:app --host 127.0.0.1 --port 8000`

## Expected summary JSON

```json
{
  "active_stocks": 1979,
  "price_ready": 1951,
  "foreign_ready": 1977,
  "tdcc_ready": 1979,
  "ranking_rows": 1950,
  "sleep_pass": 661,
  "foreign_pass": 24,
  "tdcc_pass": 87,
  "chip_pass": 2,
  "breakout_pass": 30,
  "final_pass": 0
}
```

These numbers are examples from the supplied 2026-08-14 snapshot, not hard-coded expectations.

## Server deployment

The included systemd units use:

- 18:30 Asia/Taipei primary run on weekdays.
- 20:30 Asia/Taipei retry. Resume mode keeps prior successful steps and only attempts incomplete work.
- Dashboard bound to `127.0.0.1:8000` so it can sit behind an HTTPS reverse proxy.

For phone access, expose only the HTTPS reverse proxy. Set `SWS_DASHBOARD_USER` and `SWS_DASHBOARD_PASSWORD` at minimum; do not expose the raw Uvicorn port publicly.

## Safety boundaries from AGENTS.md

- No strategy threshold changes.
- No TDCC history refetch is introduced here.
- No TPEx zero-inference is performed here.
- This layer never invents `foreign_buy` / `foreign_sell`.
- Latest TDCC and historical TDCC remain separate existing crawlers.
- Raw-first remains enforced by the actual crawler commands; this orchestrator only records command outcomes.
