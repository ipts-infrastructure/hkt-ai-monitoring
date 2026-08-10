from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests


class LangfuseClient:
    def __init__(self, host: str, public_key: str, secret_key: str):
        self._session = requests.Session()
        self._session.auth = (public_key, secret_key)
        self._session.headers["Accept"] = "application/json"
        self._base = host

    def fetch_daily_metrics(self, lookback_days: int) -> list[dict]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days)
        params = {
            "fromTimestamp": start.isoformat().replace("+00:00", "Z"),
            "toTimestamp": end.isoformat().replace("+00:00", "Z"),
            "limit": lookback_days + 1,
        }
        response = self._session.get(
            f"{self._base}/api/public/metrics/daily",
            params=params,
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", [])

    def fetch_traces(
        self,
        lookback_hours: int,
        *,
        page_limit: int = 100,
        max_pages: int = 10,
    ) -> list[dict]:
        """Fetch recent traces (newest first) within the lookback window."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=lookback_hours)
        traces: list[dict] = []
        page = 1
        while page <= max_pages:
            params = {
                "fromTimestamp": start.isoformat().replace("+00:00", "Z"),
                "toTimestamp": end.isoformat().replace("+00:00", "Z"),
                "limit": page_limit,
                "page": page,
                "orderBy": "timestamp.desc",
            }
            response = self._session.get(
                f"{self._base}/api/public/traces",
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("data") or []
            traces.extend(batch)
            meta = payload.get("meta") or {}
            total_pages = int(meta.get("totalPages") or 1)
            if page >= total_pages or not batch:
                break
            page += 1
        return traces


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def extract_trace_metrics(trace: dict) -> Optional[dict]:
    """
    Pull TTFT / tokens / labels from a Langfuse trace.

    Supports post-run metadata from n8n demos:
      AI_TTFT_Ms, inputTokens, outputTokens, totalTokens,
      model, n8n_node_name / n8n.node.name, n8n_workflow_name, executionId
    """
    metadata = trace.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    ttft_ms = _to_float(metadata.get("AI_TTFT_Ms"))
    if ttft_ms is None:
        ttft_ms = _to_float(metadata.get("AI_TTFT_Sec"))
        if ttft_ms is not None:
            ttft_ms *= 1000.0

    input_tokens = _to_float(metadata.get("inputTokens"))
    output_tokens = _to_float(metadata.get("outputTokens"))
    total_tokens = _to_float(metadata.get("totalTokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    # Skip traces with nothing useful for Prometheus numeric export
    if ttft_ms is None and input_tokens is None and output_tokens is None:
        return None

    trace_input = trace.get("input")
    input_model = None
    if isinstance(trace_input, dict):
        input_model = trace_input.get("model")
    model = metadata.get("model") or input_model or "unknown"
    node_name = (
        metadata.get("n8n_node_name")
        or metadata.get("n8n.node.name")
        or metadata.get("node")
        or "unknown"
    )
    workflow = (
        metadata.get("n8n_workflow_name")
        or metadata.get("n8n.workflow.name")
        or metadata.get("parentWorkflow")
        or metadata.get("workflow")
        or "unknown"
    )
    if isinstance(workflow, dict):
        workflow = workflow.get("name") or "unknown"

    execution_id = metadata.get("executionId")
    if execution_id is None:
        execution_id = metadata.get("n8n_execution_id") or metadata.get(
            "n8n.execution.id"
        )

    return {
        "trace_id": str(trace.get("id") or ""),
        "ttft_ms": ttft_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "model": str(model),
        "node_name": str(node_name),
        "workflow": str(workflow),
        "execution_id": str(execution_id) if execution_id is not None else "",
    }
