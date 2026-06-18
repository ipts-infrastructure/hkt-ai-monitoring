from datetime import datetime, timezone
from typing import Optional

from prometheus_client import Counter, Gauge

DAILY_TRACES = Gauge(
    "langfuse_daily_traces",
    "Trace count for a calendar day",
    ["project", "date"],
)
DAILY_OBSERVATIONS = Gauge(
    "langfuse_daily_observations",
    "Observation count for a calendar day",
    ["project", "date"],
)
DAILY_COST_USD = Gauge(
    "langfuse_daily_cost_usd",
    "Total cost in USD for a calendar day",
    ["project", "date"],
)
TOKENS_TOTAL = Gauge(
    "langfuse_tokens_total",
    "Total tokens used",
    ["project", "date", "model"],
)
TOKENS_INPUT = Gauge(
    "langfuse_tokens_input",
    "Input tokens used",
    ["project", "date", "model"],
)
TOKENS_OUTPUT = Gauge(
    "langfuse_tokens_output",
    "Output tokens used",
    ["project", "date", "model"],
)
MODEL_COST_USD = Gauge(
    "langfuse_model_cost_usd",
    "Cost in USD per model",
    ["project", "date", "model"],
)
MODEL_TRACES = Gauge(
    "langfuse_model_traces",
    "Trace count per model",
    ["project", "date", "model"],
)
MODEL_OBSERVATIONS = Gauge(
    "langfuse_model_observations",
    "Observation count per model",
    ["project", "date", "model"],
)

SCRAPE_SUCCESS = Gauge(
    "langfuse_exporter_last_scrape_success",
    "1 if the last Langfuse API scrape succeeded for this project, else 0",
    ["project"],
)
SCRAPE_TIMESTAMP = Gauge(
    "langfuse_exporter_last_scrape_timestamp_seconds",
    "Unix timestamp of the last successful scrape for this project",
    ["project"],
)
SCRAPE_ERRORS = Counter(
    "langfuse_exporter_scrape_errors_total",
    "Total failed Langfuse API scrapes",
    ["project"],
)

_ALL_GAUGES = (
    DAILY_TRACES,
    DAILY_OBSERVATIONS,
    DAILY_COST_USD,
    TOKENS_TOTAL,
    TOKENS_INPUT,
    TOKENS_OUTPUT,
    MODEL_COST_USD,
    MODEL_TRACES,
    MODEL_OBSERVATIONS,
)


def clear_gauges() -> None:
    for gauge in _ALL_GAUGES:
        gauge.clear()


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _zero_daily_row(date: str) -> dict:
    return {
        "date": date,
        "countTraces": 0,
        "countObservations": 0,
        "totalCost": 0,
        "usage": [],
    }


def _set_model_metrics(
    project: str, date: str, model: str, usage: Optional[dict] = None
) -> None:
    usage = usage or {}
    labels = {"project": project, "date": date, "model": model}
    TOKENS_TOTAL.labels(**labels).set(float(usage.get("totalUsage", 0)))
    TOKENS_INPUT.labels(**labels).set(float(usage.get("inputUsage", 0)))
    TOKENS_OUTPUT.labels(**labels).set(float(usage.get("outputUsage", 0)))
    MODEL_COST_USD.labels(**labels).set(float(usage.get("totalCost", 0)))
    MODEL_TRACES.labels(**labels).set(float(usage.get("countTraces", 0)))
    MODEL_OBSERVATIONS.labels(**labels).set(
        float(usage.get("countObservations", 0))
    )


def update_from_daily_rows(project: str, rows: list[dict]) -> None:
    if not rows:
        rows = [_zero_daily_row(_today_utc())]

    for row in rows:
        date = row.get("date", "unknown")
        DAILY_TRACES.labels(project=project, date=date).set(
            float(row.get("countTraces", 0))
        )
        DAILY_OBSERVATIONS.labels(project=project, date=date).set(
            float(row.get("countObservations", 0))
        )
        DAILY_COST_USD.labels(project=project, date=date).set(
            float(row.get("totalCost", 0))
        )

        usage_rows = row.get("usage") or []
        if not usage_rows:
            _set_model_metrics(project, date, "none")
            continue

        for usage in usage_rows:
            model = usage.get("model") or "unknown"
            _set_model_metrics(project, date, model, usage)
