import json
import os
from pathlib import Path


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _load_projects_from_file(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} must be a non-empty JSON array")
    projects = []
    for entry in data:
        name = entry.get("name", "").strip()
        public_key = entry.get("public_key", "").strip()
        secret_key = entry.get("secret_key", "").strip()
        if not name or not public_key or not secret_key:
            raise ValueError(
                f"Each project in {path} needs name, public_key, and secret_key"
            )
        projects.append(
            {"name": name, "public_key": public_key, "secret_key": secret_key}
        )
    return projects


def load_projects() -> list[dict]:
    projects_file = os.environ.get("LANGFUSE_PROJECTS_FILE", "").strip()
    if not projects_file:
        raise ValueError(
            "Missing LANGFUSE_PROJECTS_FILE — set it to your projects JSON path "
            "(e.g. /app/projects.json in Docker, ../projects.json locally)"
        )
    return _load_projects_from_file(projects_file)


def load_config() -> dict:
    host = _require("LANGFUSE_HOST").rstrip("/")
    return {
        "host": host,
        "projects": load_projects(),
        "scrape_interval": int(os.environ.get("SCRAPE_INTERVAL_SECONDS", "60")),
        "lookback_days": int(os.environ.get("LOOKBACK_DAYS", "7")),
        "metrics_port": int(os.environ.get("METRICS_PORT", "29100")),
    }
