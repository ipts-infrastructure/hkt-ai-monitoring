from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, Optional, Set, Tuple

from prometheus_client import Counter, Gauge, Histogram

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

# --- Incremental / rate-friendly series (do not clear each scrape) ---
TRACES_TOTAL = Counter(
    "langfuse_traces_total",
    "Langfuse traces processed by the exporter (use rate() for request rate)",
    ["project", "model", "node_name", "workflow"],
)
# Named langfuse_trace_* so counters don't collide with daily gauges
# (prometheus_client treats Counter "foo_total" as timeseries family "foo").
TOKENS_INPUT_TOTAL = Counter(
    "langfuse_trace_tokens_input_total",
    "Cumulative input tokens from Langfuse traces (use rate())",
    ["project", "model", "node_name", "workflow"],
)
TOKENS_OUTPUT_TOTAL = Counter(
    "langfuse_trace_tokens_output_total",
    "Cumulative output tokens from Langfuse traces (use rate())",
    ["project", "model", "node_name", "workflow"],
)
TOKENS_SUM_TOTAL = Counter(
    "langfuse_trace_tokens_sum_total",
    "Cumulative total tokens from Langfuse traces (use rate())",
    ["project", "model", "node_name", "workflow"],
)
TTFT_MS = Histogram(
    "langfuse_ttft_ms",
    "Time-to-first-token in milliseconds from Langfuse trace metadata",
    ["project", "model", "node_name", "workflow"],
    buckets=(
        100,
        250,
        500,
        1000,
        2000,
        4000,
        8000,
        12000,
        16000,
        24000,
        32000,
        60000,
        float("inf"),
    ),
)
TTFT_MS_LAST = Gauge(
    "langfuse_ttft_ms_last",
    "Most recent TTFT in milliseconds observed by the exporter",
    ["project", "model", "node_name", "workflow"],
)
TTFT_MS_AVG_WINDOW = Gauge(
    "langfuse_ttft_ms_avg_window",
    "Average TTFT (ms) over traces in the current lookback window",
    ["project", "model", "node_name", "workflow"],
)
TTFT_MS_P95_WINDOW = Gauge(
    "langfuse_ttft_ms_p95_window",
    "Approx p95 TTFT (ms) over traces in the current lookback window",
    ["project", "model", "node_name", "workflow"],
)
WINDOW_TRACES = Gauge(
    "langfuse_window_traces",
    "Number of traces with AI metrics in the lookback window",
    ["project", "model", "node_name", "workflow"],
)

# Per-trace gauges (rebuilt each scrape) — for Grafana table + Execution ID filter
TRACE_TTFT_MS = Gauge(
    "langfuse_trace_ttft_ms",
    "TTFT (ms) per Langfuse trace in the exporter lookback window",
    ["project", "execution_id", "model", "node_name", "workflow", "trace_id"],
)
TRACE_INPUT_TOKENS = Gauge(
    "langfuse_trace_input_tokens",
    "Input tokens per Langfuse trace in the lookback window",
    ["project", "execution_id", "model", "node_name", "workflow", "trace_id"],
)
TRACE_OUTPUT_TOKENS = Gauge(
    "langfuse_trace_output_tokens",
    "Output tokens per Langfuse trace in the lookback window",
    ["project", "execution_id", "model", "node_name", "workflow", "trace_id"],
)
TRACE_TOTAL_TOKENS = Gauge(
    "langfuse_trace_total_tokens",
    "Total tokens per Langfuse trace in the lookback window",
    ["project", "execution_id", "model", "node_name", "workflow", "trace_id"],
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

_ALL_DAILY_GAUGES = (
    DAILY_TRACES,
    DAILY_OBSERVATIONS,
    DAILY_COST_USD,
    TOKENS_TOTAL,
    TOKENS_INPUT,
    TOKENS_OUTPUT,
    MODEL_COST_USD,
    MODEL_TRACES,
    MODEL_OBSERVATIONS,
    TTFT_MS_AVG_WINDOW,
    TTFT_MS_P95_WINDOW,
    WINDOW_TRACES,
    TRACE_TTFT_MS,
    TRACE_INPUT_TOKENS,
    TRACE_OUTPUT_TOKENS,
    TRACE_TOTAL_TOKENS,
)

# Per-project ring of seen trace IDs to avoid double-counting counters/histogram
_SEEN: Dict[str, Deque[str]] = defaultdict(deque)
_SEEN_SET: Dict[str, Set[str]] = defaultdict(set)
_MAX_SEEN = 20000


def clear_daily_gauges() -> None:
    """Clear rebuildable gauges. Counters/histograms are kept for rate()."""
    for gauge in _ALL_DAILY_GAUGES:
        gauge.clear()


# Back-compat alias used by older tests/callers
def clear_gauges() -> None:
    clear_daily_gauges()


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


def _remember_trace(project: str, trace_id: str) -> bool:
    """Return True if this trace_id was not seen before (and record it)."""
    if not trace_id:
        return False
    seen_set = _SEEN_SET[project]
    if trace_id in seen_set:
        return False
    seen_q = _SEEN[project]
    seen_q.append(trace_id)
    seen_set.add(trace_id)
    while len(seen_q) > _MAX_SEEN:
        old = seen_q.popleft()
        seen_set.discard(old)
    return True


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def update_from_traces(project: str, trace_metrics: list[dict]) -> Tuple[int, int]:
    """
    Update window gauges for all traces, and increment counters/histogram
    only for newly seen trace IDs.

    Returns (new_traces, window_traces_with_metrics).
    """
    ttft_by_label: Dict[Tuple[str, str, str], list[float]] = defaultdict(list)
    count_by_label: Dict[Tuple[str, str, str], int] = defaultdict(int)
    new_count = 0

    for item in trace_metrics:
        model = item.get("model") or "unknown"
        node_name = item.get("node_name") or "unknown"
        workflow = item.get("workflow") or "unknown"
        key = (model, node_name, workflow)
        labels = {
            "project": project,
            "model": model,
            "node_name": node_name,
            "workflow": workflow,
        }
        count_by_label[key] += 1
        ttft_ms = item.get("ttft_ms")
        if ttft_ms is not None:
            ttft_by_label[key].append(float(ttft_ms))

        # Per-trace gauges (all traces in window — for Prometheus table)
        exec_id = item.get("execution_id") or "unknown"
        trace_id = item.get("trace_id") or "unknown"
        row_labels = {
            "project": project,
            "execution_id": exec_id,
            "model": model,
            "node_name": node_name,
            "workflow": workflow,
            "trace_id": trace_id,
        }
        if ttft_ms is not None:
            TRACE_TTFT_MS.labels(**row_labels).set(float(ttft_ms))
        if item.get("input_tokens") is not None:
            TRACE_INPUT_TOKENS.labels(**row_labels).set(float(item["input_tokens"]))
        if item.get("output_tokens") is not None:
            TRACE_OUTPUT_TOKENS.labels(**row_labels).set(
                float(item["output_tokens"])
            )
        if item.get("total_tokens") is not None:
            TRACE_TOTAL_TOKENS.labels(**row_labels).set(float(item["total_tokens"]))

        if not _remember_trace(project, item.get("trace_id", "")):
            continue

        new_count += 1
        TRACES_TOTAL.labels(**labels).inc()
        if ttft_ms is not None:
            TTFT_MS.labels(**labels).observe(float(ttft_ms))
            TTFT_MS_LAST.labels(**labels).set(float(ttft_ms))
        if item.get("input_tokens") is not None:
            TOKENS_INPUT_TOTAL.labels(**labels).inc(float(item["input_tokens"]))
        if item.get("output_tokens") is not None:
            TOKENS_OUTPUT_TOTAL.labels(**labels).inc(float(item["output_tokens"]))
        if item.get("total_tokens") is not None:
            TOKENS_SUM_TOTAL.labels(**labels).inc(float(item["total_tokens"]))

    # Rebuild window aggregates each scrape
    for key, window_count in count_by_label.items():
        model, node_name, workflow = key
        labels = {
            "project": project,
            "model": model,
            "node_name": node_name,
            "workflow": workflow,
        }
        WINDOW_TRACES.labels(**labels).set(window_count)
        values_sorted = sorted(ttft_by_label.get(key, []))
        if values_sorted:
            TTFT_MS_AVG_WINDOW.labels(**labels).set(
                sum(values_sorted) / len(values_sorted)
            )
            TTFT_MS_P95_WINDOW.labels(**labels).set(
                _percentile(values_sorted, 0.95)
            )

    return new_count, sum(count_by_label.values())
