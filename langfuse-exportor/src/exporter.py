import logging
import time
from datetime import datetime, timezone

from prometheus_client import start_http_server

from config import load_config
from langfuse_client import LangfuseClient, extract_observation_metrics
from metrics import (
    AI_METRICS_EXTRACTED,
    SCRAPE_ERRORS,
    SCRAPE_SUCCESS,
    SCRAPE_TIMESTAMP,
    TRACES_FETCHED,
    clear_daily_gauges,
    update_from_daily_rows,
    update_from_observations,
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

    observations = client.fetch_observations(
        cfg["trace_lookback_hours"],
        page_limit=cfg["trace_page_limit"],
        max_pages=cfg["trace_max_pages"],
    )
    observation_metrics = []
    for observation in observations:
        extracted = extract_observation_metrics(observation)
        if extracted:
            observation_metrics.append(extracted)

    new_obs, window_obs = update_from_observations(name, observation_metrics)

    TRACES_FETCHED.labels(project=name).set(len(observations))
    AI_METRICS_EXTRACTED.labels(project=name).set(len(observation_metrics))
    SCRAPE_SUCCESS.labels(project=name).set(1)
    SCRAPE_TIMESTAMP.labels(project=name).set(
        datetime.now(timezone.utc).timestamp()
    )
    logger.info(
        "Scraped project %s: daily_rows=%d observations=%d ai_metrics=%d new=%d",
        name,
        len(rows),
        len(observations),
        len(observation_metrics),
        new_obs,
    )
    if observations and not observation_metrics:
        logger.warning(
            "Project %s: fetched %d GENERATION observations but none had "
            "Langfuse timeToFirstToken / tokensPerSecond / usage "
            "(needs streaming completionStartTime for TTFT)",
            name,
            len(observations),
        )
    elif observation_metrics:
        with_ttft = sum(1 for m in observation_metrics if m.get("ttft_ms") is not None)
        with_tps = sum(1 for m in observation_metrics if m.get("tps") is not None)
        logger.info(
            "Project %s: Langfuse metrics coverage ttft=%d/%d tps=%d/%d",
            name,
            with_ttft,
            len(observation_metrics),
            with_tps,
            len(observation_metrics),
        )


def run() -> None:
    cfg = load_config()
    project_names = [p["name"] for p in cfg["projects"]]

    start_http_server(cfg["metrics_port"])
    logger.info(
        "Langfuse exporter listening on :%d/metrics "
        "(interval=%ds, lookback=%dd, observation_lookback=%dh, projects=%s)",
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
