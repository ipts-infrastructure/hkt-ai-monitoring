# Langfuse Prometheus Exporter

Polls the Langfuse [Daily Metrics API](https://langfuse.com/docs/metrics/features/metrics-api#daily-metrics) for **multiple projects** and exposes Prometheus metrics with a `project` label.

Works with **Prometheus and Grafana already running on your Mac** — this repo only runs the exporter.

## Quick start

1. Create project credentials (one API key pair per Langfuse project):

```bash
cp projects.json.example projects.json
```

Edit `projects.json` — add every project you want to export:

```json
[
  {
    "name": "dify-prod",
    "public_key": "pk-lf-...",
    "secret_key": "sk-lf-..."
  },
  {
    "name": "dify-dev",
    "public_key": "pk-lf-...",
    "secret_key": "sk-lf-..."
  }
]
```

Get keys from Langfuse UI → **Project → Settings → API Keys**.

2. Configure `.env`:

```bash
cp .env.example .env
```

```env
LANGFUSE_HOST=http://host.docker.internal:23001
LANGFUSE_PROJECTS_FILE=/app/projects.json
```

3. Start the exporter:

```bash
docker compose up -d --build
```

4. Add a scrape job to your existing Prometheus (`prometheus-scrape.example.yml`):

```yaml
scrape_configs:
  - job_name: langfuse-exporter
    scrape_interval: 60s
    static_configs:
      - targets: ["localhost:29100"]
```

Reload Prometheus and confirm the target is **UP** (e.g. http://localhost:29090/targets).

5. Verify metrics: http://localhost:29100/metrics

6. Grafana PromQL examples:

```promql
sum by (project, model) (langfuse_tokens_total)
sum by (project) (langfuse_daily_cost_usd)
langfuse_exporter_last_scrape_success
```

## Logs

```bash
docker compose logs -f langfuse-exporter
```

Expected output per scrape cycle:

```text
INFO Scraped 7 daily metric rows for project dify-prod
INFO Scraped 7 daily metric rows for project dify-dev
```

## Scrape target by setup

| Prometheus runs on… | Scrape target |
|---------------------|---------------|
| Host (same Mac as exporter) | `localhost:29100` |
| Docker | `host.docker.internal:29100` |
| Another machine | `<mac-ip>:29100` |

## Run without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export LANGFUSE_HOST=http://localhost:23001
export LANGFUSE_PROJECTS_FILE=../projects.json

cd src && python exporter.py
```

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LANGFUSE_HOST` | yes | — | Langfuse base URL |
| `LANGFUSE_PROJECTS_FILE` | yes | — | Path to projects JSON (use `/app/projects.json` in Docker) |
| `SCRAPE_INTERVAL_SECONDS` | no | `60` | Poll interval |
| `LOOKBACK_DAYS` | no | `7` | Days of daily metrics to fetch |
| `METRICS_PORT` | no | `29100` | Exporter listen port |

## Exported metrics

All metrics include a `project` label.

| Metric | Labels |
|--------|--------|
| `langfuse_daily_traces` | `project`, `date` |
| `langfuse_daily_observations` | `project`, `date` |
| `langfuse_daily_cost_usd` | `project`, `date` |
| `langfuse_tokens_total` | `project`, `date`, `model` |
| `langfuse_tokens_input` | `project`, `date`, `model` |
| `langfuse_tokens_output` | `project`, `date`, `model` |
| `langfuse_model_cost_usd` | `project`, `date`, `model` |
| `langfuse_model_traces` | `project`, `date`, `model` |
| `langfuse_model_observations` | `project`, `date`, `model` |
| `langfuse_exporter_last_scrape_success` | `project` |
| `langfuse_exporter_scrape_errors_total` | `project` |

Daily metrics are stored with a sample timestamp at **23:59:59 UTC** on each `date` label so Grafana's time range picker can filter by calendar day.

`projects.json` is gitignored — do not commit API keys.
