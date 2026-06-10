from datetime import datetime, timezone

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


def _date_to_timestamp(date: str) -> float | None:
    try:
        day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end = day.replace(hour=23, minute=59, second=59)
        now = datetime.now(timezone.utc)
        if end > now:
            end = now
        return end.timestamp()
    except ValueError:
        return None


def _set_daily_gauge(gauge: Gauge, labels: dict, value: float, date: str) -> None:
    ts = _date_to_timestamp(date)
    if ts is not None:
        gauge.labels(**labels).set(value, timestamp=ts)
    else:
        gauge.labels(**labels).set(value)


def update_from_daily_rows(project: str, rows: list[dict]) -> None:
    for row in rows:
        date = row.get("date", "unknown")
        _set_daily_gauge(
            DAILY_TRACES,
            {"project": project, "date": date},
            float(row.get("countTraces", 0)),
            date,
        )
        _set_daily_gauge(
            DAILY_OBSERVATIONS,
            {"project": project, "date": date},
            float(row.get("countObservations", 0)),
            date,
        )
        _set_daily_gauge(
            DAILY_COST_USD,
            {"project": project, "date": date},
            float(row.get("totalCost", 0)),
            date,
        )

        for usage in row.get("usage", []):
            model = usage.get("model") or "unknown"
            labels = {"project": project, "date": date, "model": model}
            _set_daily_gauge(
                TOKENS_TOTAL, labels, float(usage.get("totalUsage", 0)), date
            )
            _set_daily_gauge(
                TOKENS_INPUT, labels, float(usage.get("inputUsage", 0)), date
            )
            _set_daily_gauge(
                TOKENS_OUTPUT, labels, float(usage.get("outputUsage", 0)), date
            )
            _set_daily_gauge(
                MODEL_COST_USD, labels, float(usage.get("totalCost", 0)), date
            )
            _set_daily_gauge(
                MODEL_TRACES, labels, float(usage.get("countTraces", 0)), date
            )
            _set_daily_gauge(
                MODEL_OBSERVATIONS,
                labels,
                float(usage.get("countObservations", 0)),
                date,
            )
