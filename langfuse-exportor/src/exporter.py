import logging
import time
from datetime import datetime, timezone

from prometheus_client import start_http_server

from config import load_config
from langfuse_client import LangfuseClient, extract_trace_metrics
from metrics import (
    AI_METRICS_EXTRACTED,
    SCRAPE_ERRORS,
    SCRAPE_SUCCESS,
    SCRAPE_TIMESTAMP,
    TRACES_FETCHED,
    clear_daily_gauges,
    update_from_daily_rows,
    update_from_traces,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("langfuse-exporter")


def scrape_project(host: str, project: dict, cfg: dict) -> None:
    name = project["name"]
    client = LangfuseClient(host, project["public_key"], project["secret_key"])

    rows = client.fetch_daily_metrics(cfg["lookback_days"])
    update_from_daily_rows(name, rows)

    traces = client.fetch_traces(
        cfg["trace_lookback_hours"],
        page_limit=cfg["trace_page_limit"],
        max_pages=cfg["trace_max_pages"],
    )
    trace_metrics = []
    for trace in traces:
        extracted = extract_trace_metrics(trace)
        if extracted:
            trace_metrics.append(extracted)

    new_traces, window_traces = update_from_traces(name, trace_metrics)

    TRACES_FETCHED.labels(project=name).set(len(traces))
    AI_METRICS_EXTRACTED.labels(project=name).set(len(trace_metrics))
    SCRAPE_SUCCESS.labels(project=name).set(1)
    SCRAPE_TIMESTAMP.labels(project=name).set(
        datetime.now(timezone.utc).timestamp()
    )
    logger.info(
        "Scraped project %s: daily_rows=%d traces=%d ai_metrics=%d new=%d",
        name,
        len(rows),
        len(traces),
        len(trace_metrics),
        new_traces,
    )
    if traces and not trace_metrics:
        logger.warning(
            "Project %s: fetched %d traces but none had AI_TTFT_Ms/tokens "
            "(check Langfuse metadata on those traces)",
            name,
            len(traces),
        )


def run() -> None:
    cfg = load_config()
    project_names = [p["name"] for p in cfg["projects"]]

    start_http_server(cfg["metrics_port"])
    logger.info(
        "Langfuse exporter listening on :%d/metrics "
        "(interval=%ds, lookback=%dd, trace_lookback=%dh, projects=%s)",
        cfg["metrics_port"],
        cfg["scrape_interval"],
        cfg["lookback_days"],
        cfg["trace_lookback_hours"],
        ", ".join(project_names),
    )

    while True:
        # Rebuild daily/window gauges; keep counters + histogram for rate()
        clear_daily_gauges()
        for project in cfg["projects"]:
            try:
                scrape_project(cfg["host"], project, cfg)
            except Exception:
                SCRAPE_SUCCESS.labels(project=project["name"]).set(0)
                SCRAPE_ERRORS.labels(project=project["name"]).inc()
                logger.exception(
                    "Failed to scrape Langfuse metrics for project %s",
                    project["name"],
                )
        time.sleep(cfg["scrape_interval"])


if __name__ == "__main__":
    run()
