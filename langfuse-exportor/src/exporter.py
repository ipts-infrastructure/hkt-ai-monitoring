import logging
import time
from datetime import datetime, timezone

from prometheus_client import start_http_server

from config import load_config
from langfuse_client import LangfuseClient
from metrics import (
    SCRAPE_ERRORS,
    SCRAPE_SUCCESS,
    SCRAPE_TIMESTAMP,
    clear_gauges,
    update_from_daily_rows,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("langfuse-exporter")


def scrape_project(
    host: str, project: dict, lookback_days: int
) -> None:
    name = project["name"]
    client = LangfuseClient(host, project["public_key"], project["secret_key"])
    rows = client.fetch_daily_metrics(lookback_days)
    update_from_daily_rows(name, rows)
    SCRAPE_SUCCESS.labels(project=name).set(1)
    SCRAPE_TIMESTAMP.labels(project=name).set(datetime.now(timezone.utc).timestamp())
    logger.info("Scraped %d daily metric rows for project %s", len(rows), name)


def run() -> None:
    cfg = load_config()
    project_names = [p["name"] for p in cfg["projects"]]

    start_http_server(cfg["metrics_port"])
    logger.info(
        "Langfuse exporter listening on :%d/metrics (interval=%ds, lookback=%dd, projects=%s)",
        cfg["metrics_port"],
        cfg["scrape_interval"],
        cfg["lookback_days"],
        ", ".join(project_names),
    )

    while True:
        clear_gauges()
        for project in cfg["projects"]:
            try:
                scrape_project(cfg["host"], project, cfg["lookback_days"])
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
