import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

logger = logging.getLogger("langfuse-exporter")


class LangfuseClient:
    def __init__(self, host: str, public_key: str, secret_key: str):
        self._session = requests.Session()
        self._session.auth = (public_key, secret_key)
        self._session.headers["Accept"] = "application/json"
        self._base = host.rstrip("/")

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

    def fetch_observations(
        self,
        lookback_hours: int,
        *,
        page_limit: int = 100,
        max_pages: int = 10,
    ) -> list[dict]:
        """
        Fetch GENERATION observations with Langfuse-calculated metrics.

        Tries Observations API v2 first (`fields` includes metrics/usage), then
        falls back to v1 page-based `/api/public/observations`.
        """
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=lookback_hours)
        from_ts = start.isoformat().replace("+00:00", "Z")
        to_ts = end.isoformat().replace("+00:00", "Z")

        try:
            return self._fetch_observations_v2(
                from_ts, to_ts, page_limit=page_limit, max_pages=max_pages
            )
        except Exception as exc:
            logger.info(
                "Observations v2 unavailable (%s); falling back to v1", exc
            )
            return self._fetch_observations_v1(
                from_ts, to_ts, page_limit=page_limit, max_pages=max_pages
            )

    def _fetch_observations_v2(
        self,
        from_ts: str,
        to_ts: str,
        *,
        page_limit: int,
        max_pages: int,
    ) -> list[dict]:
        observations: list[dict] = []
        cursor: Optional[str] = None
        for _ in range(max_pages):
            params: dict[str, Any] = {
                "fromStartTime": from_ts,
                "toStartTime": to_ts,
                "type": "GENERATION",
                "limit": page_limit,
                "fields": "core,basic,metrics,usage,model,time,metadata",
            }
            if cursor:
                params["cursor"] = cursor
            response = self._session.get(
                f"{self._base}/api/public/v2/observations",
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("data") or []
            observations.extend(batch)
            meta = payload.get("meta") or {}
            cursor = meta.get("cursor")
            if not batch or not cursor:
                break
        return observations

    def _fetch_observations_v1(
        self,
        from_ts: str,
        to_ts: str,
        *,
        page_limit: int,
        max_pages: int,
    ) -> list[dict]:
        observations: list[dict] = []
        page = 1
        while page <= max_pages:
            params = {
                "fromStartTime": from_ts,
                "toStartTime": to_ts,
                "type": "GENERATION",
                "limit": page_limit,
                "page": page,
            }
            response = self._session.get(
                f"{self._base}/api/public/observations",
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
            batch = payload.get("data") or []
            observations.extend(batch)
            meta = payload.get("meta") or {}
            total_pages = int(meta.get("totalPages") or 1)
            if page >= total_pages or not batch:
                break
            page += 1
        return observations


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


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


def _usage_tokens(observation: dict) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Read Langfuse usage fields (not n8n metadata)."""
    usage = _as_dict(observation.get("usage"))
    details = _as_dict(observation.get("usageDetails"))

    input_tokens = _to_float(
        observation.get("inputUsage")
        or usage.get("input")
        or usage.get("promptTokens")
        or details.get("input")
        or details.get("promptTokens")
    )
    output_tokens = _to_float(
        observation.get("outputUsage")
        or usage.get("output")
        or usage.get("completionTokens")
        or details.get("output")
        or details.get("completionTokens")
    )
    total_tokens = _to_float(
        observation.get("totalUsage")
        or usage.get("total")
        or usage.get("totalTokens")
        or details.get("total")
        or details.get("totalTokens")
    )
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return input_tokens, output_tokens, total_tokens


def _ttft_ms_from_observation(observation: dict) -> Optional[float]:
    """
    Langfuse-calculated TTFT only.

    Observations API returns timeToFirstToken in seconds (v1/v2 metrics group).
    """
    ttft_sec = _to_float(observation.get("timeToFirstToken"))
    if ttft_sec is None:
        return None
    # Guard: some builds may already return milliseconds (> few minutes unlikely as seconds)
    if ttft_sec > 600:
        return ttft_sec
    return ttft_sec * 1000.0


def _latency_ms_from_observation(observation: dict) -> Optional[float]:
    """
    Langfuse generation latency in milliseconds.

    Observations API returns `latency` in seconds (v2); some builds use ms.
    """
    latency = _to_float(observation.get("latency"))
    if latency is None or latency < 0:
        return None
    # Same heuristic as TPS: values > 600 are treated as already-ms
    if latency > 600:
        return latency
    return latency * 1000.0


def _tps_from_observation(
    observation: dict,
    *,
    output_tokens: Optional[float],
) -> Optional[float]:
    """Langfuse tokensPerSecond, or derive from Langfuse latency + output tokens."""
    tps = _to_float(observation.get("tokensPerSecond"))
    if tps is not None:
        return tps
    # outputTokensPerSecond alias if present
    tps = _to_float(observation.get("outputTokensPerSecond"))
    if tps is not None:
        return tps

    latency_sec = _to_float(observation.get("latency"))
    if latency_sec is None or latency_sec <= 0 or output_tokens is None:
        return None
    # latency is seconds on v2 metrics; some v1 builds use ms
    if latency_sec > 600:
        latency_sec = latency_sec / 1000.0
    if latency_sec <= 0:
        return None
    return float(output_tokens) / latency_sec


def _label_from_metadata(metadata: dict, *keys: str, default: str = "unknown") -> str:
    for key in keys:
        value = metadata.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, dict):
            value = value.get("name") or value.get("id")
        if value is not None and value != "":
            return str(value)
    return default


def extract_observation_metrics(observation: dict) -> Optional[dict]:
    """
    Pull TTFT / TPS / tokens from Langfuse observation fields only.

    TTFT and TPS come from Langfuse-calculated observation metrics
    (`timeToFirstToken`, `tokensPerSecond` / latency+tokens). Token counts come
    from Langfuse usage on the generation — not from n8n AI_* metadata.
    """
    if str(observation.get("type") or "").upper() not in ("", "GENERATION"):
        # Allow missing type (some payloads); reject explicit non-generations
        if observation.get("type") is not None:
            return None

    ttft_ms = _ttft_ms_from_observation(observation)
    latency_ms = _latency_ms_from_observation(observation)
    input_tokens, output_tokens, total_tokens = _usage_tokens(observation)
    tps = _tps_from_observation(observation, output_tokens=output_tokens)

    # Require Langfuse TTFT, latency, TPS, or usage so empty generations are skipped
    if (
        ttft_ms is None
        and latency_ms is None
        and tps is None
        and input_tokens is None
        and output_tokens is None
    ):
        return None

    metadata = _as_dict(observation.get("metadata"))
    model = (
        observation.get("providedModelName")
        or observation.get("model")
        or metadata.get("model")
        or "unknown"
    )
    node_name = _label_from_metadata(
        metadata,
        "n8n_node_name",
        "n8n.node.name",
        "node",
        default=str(observation.get("name") or "unknown"),
    )
    workflow = _label_from_metadata(
        metadata,
        "n8n_workflow_name",
        "n8n.workflow.name",
        "parentWorkflow",
        "workflow",
        default=str(observation.get("traceName") or "unknown"),
    )
    workflow_id = _label_from_metadata(
        metadata,
        "n8n_workflow_id",
        "n8n.workflow.id",
        "workflowId",
        "workflow_id",
        default="unknown",
    )
    execution_id = _label_from_metadata(
        metadata,
        "executionId",
        "n8n_execution_id",
        "n8n.execution.id",
        default="",
    )
    if execution_id == "unknown":
        execution_id = ""

    return {
        "observation_id": str(observation.get("id") or ""),
        "trace_id": str(observation.get("traceId") or observation.get("trace_id") or ""),
        "ttft_ms": ttft_ms,
        "latency_ms": latency_ms,
        "tps": tps,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "model": str(model),
        "node_name": str(node_name),
        "workflow": str(workflow),
        "workflow_id": str(workflow_id) if workflow_id not in (None, "") else "unknown",
        "execution_id": str(execution_id) if execution_id is not None else "",
    }


# Back-compat for older imports/tests — metadata path removed.
def extract_trace_metrics(trace: dict) -> Optional[dict]:
    logger.warning(
        "extract_trace_metrics is deprecated; use extract_observation_metrics"
    )
    return None
