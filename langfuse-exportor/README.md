# Langfuse Prometheus Exporter

Polls Langfuse for **multiple projects** and exposes Prometheus metrics with a `project` label:

1. **Daily Metrics API** — traces, observations, cost, tokens by model/day
2. **Traces API** — per-trace **TTFT**, **tokens**, and **rates** (from n8n post-run metadata)

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
# Daily (calendar day label)
sum by (project, model) (langfuse_tokens_total)
sum by (project) (langfuse_daily_cost_usd)

# TTFT / tokens / rates from traces (n8n post-run metadata)
langfuse_ttft_ms_last
langfuse_ttft_ms_avg_window
histogram_quantile(0.95, sum by (le, project, model) (rate(langfuse_ttft_ms_bucket[15m])))
rate(langfuse_traces_total[5m])
rate(langfuse_trace_tokens_sum_total[5m])
rate(langfuse_trace_tokens_input_total[5m])
rate(langfuse_trace_tokens_output_total[5m])

langfuse_exporter_last_scrape_success
```

## Trace metadata expected (TTFT / tokens)

The exporter reads numeric fields from each Langfuse trace `metadata` (as written by the n8n Langfuse post-run child):

| Metadata key | Metric use |
|--------------|------------|
| `AI_TTFT_Ms` (or `AI_TTFT_Sec`) | TTFT histogram + last/avg/p95 |
| `inputTokens` / `outputTokens` / `totalTokens` | Token counters |
| `model` | label |
| `n8n_node_name` or `n8n.node.name` | `node_name` label |
| `n8n_workflow_name` or `n8n.workflow.name` | `workflow` label |

Prompt/output text is **not** exported to Prometheus (cardinality / privacy).

## Logs

```bash
docker compose logs -f langfuse-exporter
```

Expected output per scrape cycle:

```text
INFO Scraped project dify-prod: daily_rows=7 traces=42 ai_metrics=12 new=3
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
| `TRACE_LOOKBACK_HOURS` | no | `24` | Hours of traces to fetch for TTFT/tokens |
| `TRACE_PAGE_LIMIT` | no | `100` | Traces per API page |
| `TRACE_MAX_PAGES` | no | `10` | Max pages per scrape |
| `METRICS_PORT` | no | `29100` | Exporter listen port |

## Exported metrics

### Daily metrics API

All include a `project` label. Day series also have a `date` label (`YYYY-MM-DD`).

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

When Langfuse returns no daily rows, or a day has no model usage, the exporter still emits zero-valued metrics (`model="none"` for token series).

### Trace-based TTFT / tokens / rates

Labels: `project`, `model`, `node_name`, `workflow`.

Counters and the histogram are incremented **once per trace id** (deduped across scrapes) so you can use `rate()` / `increase()`.

| Metric | Type | Notes |
|--------|------|-------|
| `langfuse_traces_total` | Counter | Use `rate(...[5m])` for request rate |
| `langfuse_trace_tokens_input_total` | Counter | Use `rate()` for tokens/sec |
| `langfuse_trace_tokens_output_total` | Counter | Use `rate()` for tokens/sec |
| `langfuse_trace_tokens_sum_total` | Counter | Use `rate()` for tokens/sec |
| `langfuse_ttft_ms` | Histogram | Quantiles via `histogram_quantile` |
| `langfuse_ttft_ms_last` | Gauge | Most recent TTFT |
| `langfuse_ttft_ms_avg_window` | Gauge | Avg over lookback window |
| `langfuse_ttft_ms_p95_window` | Gauge | Approx p95 over lookback window |
| `langfuse_window_traces` | Gauge | Traces with TTFT in lookback |
| `langfuse_trace_ttft_ms` | Gauge | Per-trace TTFT (table; labels include `execution_id`) |
| `langfuse_trace_input_tokens` | Gauge | Per-trace input tokens |
| `langfuse_trace_output_tokens` | Gauge | Per-trace output tokens |
| `langfuse_trace_total_tokens` | Gauge | Per-trace total tokens |

### Exporter health

| Metric | Labels |
|--------|--------|
| `langfuse_exporter_last_scrape_success` | `project` |
| `langfuse_exporter_last_scrape_timestamp_seconds` | `project` |
| `langfuse_exporter_scrape_errors_total` | `project` |

`projects.json` is gitignored — do not commit API keys.
