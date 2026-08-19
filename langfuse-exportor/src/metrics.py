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
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
# Named langfuse_trace_* so counters don't collide with daily gauges
# (prometheus_client treats Counter "foo_total" as timeseries family "foo").
TOKENS_INPUT_TOTAL = Counter(
    "langfuse_trace_tokens_input_total",
    "Cumulative input tokens from Langfuse traces (use rate())",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
TOKENS_OUTPUT_TOTAL = Counter(
    "langfuse_trace_tokens_output_total",
    "Cumulative output tokens from Langfuse traces (use rate())",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
TOKENS_SUM_TOTAL = Counter(
    "langfuse_trace_tokens_sum_total",
    "Cumulative total tokens from Langfuse traces (use rate())",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
TTFT_MS = Histogram(
    "langfuse_ttft_ms",
    "Time-to-first-token in milliseconds from Langfuse observation metrics",
    ["project", "model", "node_name", "workflow", "workflow_id"],
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
LATENCY_MS = Histogram(
    "langfuse_latency_ms",
    "Langfuse generation latency in milliseconds (endTime - startTime)",
    ["project", "model", "node_name", "workflow", "workflow_id"],
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
        120000,
        float("inf"),
    ),
)
TTFT_MS_LAST = Gauge(
    "langfuse_ttft_ms_last",
    "Most recent Langfuse-calculated TTFT in milliseconds",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
TTFT_MS_AVG_WINDOW = Gauge(
    "langfuse_ttft_ms_avg_window",
    "Average Langfuse TTFT (ms) over generations in the lookback window",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
TTFT_MS_P95_WINDOW = Gauge(
    "langfuse_ttft_ms_p95_window",
    "Approx p95 Langfuse TTFT (ms) over generations in the lookback window",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
TPS_LAST = Gauge(
    "langfuse_tps_last",
    "Most recent Langfuse tokens-per-second (output)",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
TPS_AVG_WINDOW = Gauge(
    "langfuse_tps_avg_window",
    "Average Langfuse tokens-per-second over generations in the lookback window",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)
WINDOW_TRACES = Gauge(
    "langfuse_window_traces",
    "Number of generations with AI metrics in the lookback window",
    ["project", "model", "node_name", "workflow", "workflow_id"],
)

# Per-observation gauges (rebuilt each scrape) — Grafana tables / Execution ID filter
TRACE_TTFT_MS = Gauge(
    "langfuse_trace_ttft_ms",
    "Langfuse-calculated TTFT (ms) per generation in the lookback window",
    [
        "project",
        "execution_id",
        "model",
        "node_name",
        "workflow",
        "workflow_id",
        "trace_id",
        "observation_id",
    ],
)
TRACE_TPS = Gauge(
    "langfuse_trace_tps",
    "Langfuse-calculated tokens-per-second per generation in the lookback window",
    [
        "project",
        "execution_id",
        "model",
        "node_name",
        "workflow",
        "workflow_id",
        "trace_id",
        "observation_id",
    ],
)
TRACE_LATENCY_MS = Gauge(
    "langfuse_trace_latency_ms",
    "Langfuse generation latency (ms) per generation in the lookback window",
    [
        "project",
        "execution_id",
        "model",
        "node_name",
        "workflow",
        "workflow_id",
        "trace_id",
        "observation_id",
    ],
)
TRACE_INPUT_TOKENS = Gauge(
    "langfuse_trace_input_tokens",
    "Langfuse input tokens per generation in the lookback window",
    [
        "project",
        "execution_id",
        "model",
        "node_name",
        "workflow",
        "workflow_id",
        "trace_id",
        "observation_id",
    ],
)
TRACE_OUTPUT_TOKENS = Gauge(
    "langfuse_trace_output_tokens",
    "Langfuse output tokens per generation in the lookback window",
    [
        "project",
        "execution_id",
        "model",
        "node_name",
        "workflow",
        "workflow_id",
        "trace_id",
        "observation_id",
    ],
)
TRACE_TOTAL_TOKENS = Gauge(
    "langfuse_trace_total_tokens",
    "Langfuse total tokens per generation in the lookback window",
    [
        "project",
        "execution_id",
        "model",
        "node_name",
        "workflow",
        "workflow_id",
        "trace_id",
        "observation_id",
    ],
)
# Wide row for Grafana Table (one query; numbers in labels — no joins)
TRACE_ROW = Gauge(
    "langfuse_trace_row",
    "Langfuse generation row for Grafana tables (value always 1; numbers in labels)",
    [
        "project",
        "execution_id",
        "model",
        "node_name",
        "workflow",
        "workflow_id",
        "trace_id",
        "observation_id",
        "ttft_ms",
        "latency_ms",
        "tps",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    ],
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
TRACES_FETCHED = Gauge(
    "langfuse_exporter_traces_fetched",
    "Observations (GENERATION) returned by Langfuse on the last scrape",
    ["project"],
)
AI_METRICS_EXTRACTED = Gauge(
    "langfuse_exporter_ai_metrics_extracted",
    "Generations with Langfuse TTFT/TPS/token fields extracted on the last scrape",
    ["project"],
)
EXPORTER_FEATURE = Gauge(
    "langfuse_exporter_feature_trace_ttft",
    "1 when this exporter build supports Langfuse observation TTFT/TPS metrics",
    [],
)
EXPORTER_FEATURE.set(1)

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
    TPS_AVG_WINDOW,
    WINDOW_TRACES,
    TRACE_TTFT_MS,
    TRACE_TPS,
    TRACE_LATENCY_MS,
    TRACE_INPUT_TOKENS,
    TRACE_OUTPUT_TOKENS,
    TRACE_TOTAL_TOKENS,
    TRACE_ROW,
)

# Per-project ring of seen observation IDs to avoid double-counting counters/histogram
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


def _remember_id(project: str, item_id: str) -> bool:
    """Return True if this observation/trace id was not seen before (and record it)."""
    if not item_id:
        return False
    seen_set = _SEEN_SET[project]
    if item_id in seen_set:
        return False
    seen_q = _SEEN[project]
    seen_q.append(item_id)
    seen_set.add(item_id)
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


def _label_num(value: object) -> str:
    if value is None:
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return str(number)


def update_from_observations(
    project: str, observation_metrics: list[dict]
) -> Tuple[int, int]:
    """
    Update window gauges for all generations, and increment counters/histogram
    only for newly seen observation IDs.

    Returns (new_observations, window_generations_with_metrics).
    """
    ttft_by_label: Dict[Tuple[str, str, str, str], list[float]] = defaultdict(list)
    tps_by_label: Dict[Tuple[str, str, str, str], list[float]] = defaultdict(list)
    count_by_label: Dict[Tuple[str, str, str, str], int] = defaultdict(int)
    new_count = 0

    for item in observation_metrics:
        model = item.get("model") or "unknown"
        node_name = item.get("node_name") or "unknown"
        workflow = item.get("workflow") or "unknown"
        workflow_id = item.get("workflow_id") or "unknown"
        key = (model, node_name, workflow, workflow_id)
        labels = {
            "project": project,
            "model": model,
            "node_name": node_name,
            "workflow": workflow,
            "workflow_id": workflow_id,
        }
        count_by_label[key] += 1
        ttft_ms = item.get("ttft_ms")
        latency_ms = item.get("latency_ms")
        tps = item.get("tps")
        if ttft_ms is not None:
            ttft_by_label[key].append(float(ttft_ms))
        if tps is not None:
            tps_by_label[key].append(float(tps))

        exec_id = item.get("execution_id") or "unknown"
        trace_id = item.get("trace_id") or "unknown"
        observation_id = item.get("observation_id") or "unknown"
        row_labels = {
            "project": project,
            "execution_id": exec_id,
            "model": model,
            "node_name": node_name,
            "workflow": workflow,
            "workflow_id": workflow_id,
            "trace_id": trace_id,
            "observation_id": observation_id,
        }
        # Always emit gauges so Grafana table joins don't collapse when
        # Langfuse omits TTFT (non-streaming) or TPS.
        TRACE_TTFT_MS.labels(**row_labels).set(
            float(ttft_ms) if ttft_ms is not None else 0.0
        )
        TRACE_LATENCY_MS.labels(**row_labels).set(
            float(latency_ms) if latency_ms is not None else 0.0
        )
        TRACE_TPS.labels(**row_labels).set(
            float(tps) if tps is not None else 0.0
        )
        TRACE_INPUT_TOKENS.labels(**row_labels).set(
            float(item["input_tokens"])
            if item.get("input_tokens") is not None
            else 0.0
        )
        TRACE_OUTPUT_TOKENS.labels(**row_labels).set(
            float(item["output_tokens"])
            if item.get("output_tokens") is not None
            else 0.0
        )
        TRACE_TOTAL_TOKENS.labels(**row_labels).set(
            float(item["total_tokens"])
            if item.get("total_tokens") is not None
            else 0.0
        )

        TRACE_ROW.labels(
            project=project,
            execution_id=exec_id,
            model=model,
            node_name=node_name,
            workflow=workflow,
            workflow_id=workflow_id,
            trace_id=trace_id,
            observation_id=observation_id,
            ttft_ms=_label_num(ttft_ms),
            latency_ms=_label_num(latency_ms),
            tps=_label_num(tps),
            input_tokens=_label_num(item.get("input_tokens")),
            output_tokens=_label_num(item.get("output_tokens")),
            total_tokens=_label_num(item.get("total_tokens")),
        ).set(1)

        dedupe_id = observation_id if observation_id != "unknown" else trace_id
        if not _remember_id(project, dedupe_id):
            continue

        new_count += 1
        TRACES_TOTAL.labels(**labels).inc()
        if ttft_ms is not None:
            TTFT_MS.labels(**labels).observe(float(ttft_ms))
            TTFT_MS_LAST.labels(**labels).set(float(ttft_ms))
        if latency_ms is not None:
            LATENCY_MS.labels(**labels).observe(float(latency_ms))
        if tps is not None:
            TPS_LAST.labels(**labels).set(float(tps))
        if item.get("input_tokens") is not None:
            TOKENS_INPUT_TOTAL.labels(**labels).inc(float(item["input_tokens"]))
        if item.get("output_tokens") is not None:
            TOKENS_OUTPUT_TOTAL.labels(**labels).inc(float(item["output_tokens"]))
        if item.get("total_tokens") is not None:
            TOKENS_SUM_TOTAL.labels(**labels).inc(float(item["total_tokens"]))

    for key, window_count in count_by_label.items():
        model, node_name, workflow, workflow_id = key
        labels = {
            "project": project,
            "model": model,
            "node_name": node_name,
            "workflow": workflow,
            "workflow_id": workflow_id,
        }
        WINDOW_TRACES.labels(**labels).set(window_count)
        ttft_sorted = sorted(ttft_by_label.get(key, []))
        if ttft_sorted:
            TTFT_MS_AVG_WINDOW.labels(**labels).set(
                sum(ttft_sorted) / len(ttft_sorted)
            )
            TTFT_MS_P95_WINDOW.labels(**labels).set(
                _percentile(ttft_sorted, 0.95)
            )
        tps_sorted = sorted(tps_by_label.get(key, []))
        if tps_sorted:
            TPS_AVG_WINDOW.labels(**labels).set(
                sum(tps_sorted) / len(tps_sorted)
            )

    return new_count, sum(count_by_label.values())


# Back-compat alias
def update_from_traces(project: str, trace_metrics: list[dict]) -> Tuple[int, int]:
    return update_from_observations(project, trace_metrics)