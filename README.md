# monitoring-compose

A comprehensive monitoring stack using Docker Compose with Prometheus, Grafana, cAdvisor and hkt custom exporter for system and application monitoring.

## 🚀 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Port availability: 23000 (Grafana), 23200 (Tempo query), 24317/24318 (otel-collector OTLP), 29090 (Prometheus), 28080 (cAdvisor), 23030 (Langfuse worker), 23001 (Langfuse web), 29100 (Langfuse exporter), 28123 & 29000 (Clickhouse), 29002 & 29001 (Minio), 26379 (Redis), 25432 (Postgres), 28872 (HktExporter)
- Minimum 2GB RAM recommended for optimal performance

## 🛠️ Getting Started



### 1. Environment Setup

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env.dev
# Edit .env.dev with your preferred Grafana admin credentials
# Edit .env.dev with your langfuse secret configure
```



### 2. Configure Prometheus scrape targets

Copy the example config and set targets for your machines (HKT exporter IPs/hostnames and device labels):

```bash
cp prometheus/prometheus.yml.example prometheus/prometheus.yml
```

Edit `prometheus/prometheus.yml` with your exporter addresses. Docker-internal jobs (`cadvisor`, `langfuse-exporter`) usually need no changes when using the default compose stack.

### 3. Configure Langfuse Prometheus Exporter

Create project credentials (one API key pair per Langfuse project):

```bash
cp langfuse-exportor/projects.json.example langfuse-exportor/projects.json
```

Edit `langfuse-exportor/projects.json` with keys from Langfuse UI → **Project → Settings → API Keys**.

The exporter is included in the main stack and scrapes Langfuse over the internal Docker network (`http://langfuse-web:3000`). Prometheus is preconfigured to scrape `langfuse-exporter:29100`.

### 4. Download & install HKT exporter binary

Installs the host metrics exporter on **macOS Apple Silicon** (LaunchDaemon). The GitHub release must be reachable ([releases](https://github.com/ipts-infrastructure/speedx/releases) — public visibility).

```bash
chmod +x ./scripts/install-hkt-exporter.sh
./scripts/install-hkt-exporter.sh          # download binary + enable auto-start
# ./scripts/install-hkt-exporter.sh uninstall
```

Metrics: [http://localhost:28872/metrics](http://localhost:28872/metrics)



### 5. Start the Stack

```bash
# Development
docker compose --env-file .env.dev up -d

# Production  
docker compose --env-file .env.prod up -d
```

If you only need traces (otel-collector + Tempo + Grafana + Prometheus), you can start a subset instead:

```bash
docker compose --env-file .env.dev up -d otel-collector tempo grafana prometheus
```



### 6. App traces (n8n, Dify, …) → otel-collector → Tempo

This stack includes an **OpenTelemetry Collector** as the shared OTLP gateway. Apps such as n8n and Dify run in their **own** Compose projects and send traces here; the collector forwards them to Tempo on the internal Docker network.

```text
n8n / Dify / other apps
        │
        ▼
otel-collector  (host :24318 HTTP / :24317 gRPC)
        │
        ▼
     Tempo  →  Grafana
```

Config lives at `otel/otel-collector-config.yaml`. Start/restart the stack so `otel-collector` is up (`docker compose up -d`).

**Which OTLP URL should apps use?**

| App reaches collector via | Example endpoint | When to use |
|---|---|---|
| Host publish (typical for separate Compose) | `http://host.docker.internal:24318` | n8n/Dify in another Compose on Docker Desktop (Mac/Windows) |
| Same Docker network as this stack | `http://otel-collector:4318` | App container joined to `monitoring-net` |
| Linux Docker Engine (no Desktop DNS) | same as above, plus `extra_hosts` below | When `host.docker.internal` is missing |

Point apps at the **collector**, not Tempo. Tempo OTLP ports are no longer published on the host.

**1. Enable OTEL in n8n** (external project — pick UI or env vars)

> **Version requirement:** OpenTelemetry tracing is only available in **n8n ≥ 2.19.0**.

#### Option A — n8n UI (recommended)

1. Open your n8n UI (e.g. `http://localhost:5678`).
2. Go to **Settings → OpenTelemetry**.
3. Turn **Enable** on.
4. Set the **OTLP endpoint** to `http://host.docker.internal:24318` (no `/v1/traces`).
5. Save. n8n applies the change without a restart (and reloads it across workers / webhook processors in queue mode).

While testing, also turn off “production only” (or equivalent) so manual / test executions emit traces.

#### Option B — Docker compose / `.env`

In n8n’s `docker-compose.yml` (or `.env`):

```yaml
services:
  n8n:
    image: n8nio/n8n:latest
    # ... your existing ports, volumes, etc.
    environment:
      # existing n8n env...
      N8N_OTEL_ENABLED: "true"
      # Host-published collector in this monitoring stack (n8n appends /v1/traces — do not include it)
      N8N_OTEL_EXPORTER_OTLP_ENDPOINT: "http://host.docker.internal:24318"
      N8N_OTEL_EXPORTER_SERVICE_NAME: "n8n"
      # optional while testing: include manual / test executions
      N8N_OTEL_TRACES_PRODUCTION_ONLY: "false"
    # Linux Docker Engine only (usually not needed on Docker Desktop):
    # extra_hosts:
    #   - "host.docker.internal:host-gateway"
```

Or in n8n’s `.env`:

```bash
N8N_OTEL_ENABLED=true
N8N_OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:24318
N8N_OTEL_EXPORTER_SERVICE_NAME=n8n
N8N_OTEL_TRACES_PRODUCTION_ONLY=false
```

Then recreate n8n:

```bash
# in your n8n project directory (not this repo)
docker compose up -d n8n
```

**Dify / other services:** use the same OTLP base URL (`http://host.docker.internal:24318` or `http://otel-collector:4318`) and set a distinct `service.name` (e.g. `dify`) so traces are easy to filter in Grafana.

Notes:

- Point the OTLP endpoint at the **base** URL only (no `/v1/traces`).
- Use the hostname that is reachable **from inside the app container**, not from your browser.
- To debug ingest, uncomment the `debug` exporter in `otel/otel-collector-config.yaml` and recreate `otel-collector`.

**2. View traces in Grafana**

- Dashboard: **MacOS → n8n Traces**
- Or **Explore → Tempo** with TraceQL:

```traceql
{ resource.service.name = "n8n" }
{ resource.service.name = "dify" }
{ resource.service.name = "n8n" && span.n8n.workflow.name =~ "AI Agent.*" }
{ resource.service.name = "n8n" && name = "node.execute" }
```

Click a trace to see spans like `workflow.execute`, `node.execute`, and attributes such as `n8n.workflow.name`, `n8n.node.name`, `n8n.execution.id`.

### 7. Access Services

- **Grafana Dashboard**: [http://localhost:23000](http://localhost:23000)
  - Username: `admin` (or as configured in .env)
  - Password: `admin` (or as configured in .env)
- **Prometheus**: [http://localhost:29090](http://localhost:29090)
- **cAdvisor**: [http://localhost:28080](http://localhost:28080)
- **HktExporter**: [http://localhost:28872/metrics](http://localhost:28872/metrics)
- **Langfuse Web UI**: [http://localhost:23001](http://localhost:23001)
- **Langfuse Worker**: [http://localhost:23030](http://localhost:23030) (internal worker UI / health)
- **Langfuse Clickhouse HTTP**: [http://localhost:28123](http://localhost:28123)
- **Langfuse Clickhouse TCP**: localhost:29000
- **Langfuse Minio S3 endpoint**: [http://localhost:29002](http://localhost:29002)
- **Langfuse Minio Console**: [http://localhost:29001](http://localhost:29001)
- **Langfuse Redis**: localhost:26379
- **Langfuse Postgres**: localhost:25432
- **Langfuse Exporter metrics**: [http://localhost:29100/metrics](http://localhost:29100/metrics)
- **Tempo**: [http://localhost:23200](http://localhost:23200) (query API)
- **otel-collector OTLP**: gRPC `localhost:24317`, HTTP `localhost:24318` (apps should use these, not Tempo)



### 8. Stop the Stack

```bash
docker compose down
```



## 🚨 Troubleshooting



### Common Issues

**Services not starting:**

- Check if required ports (23000, 29090, 28080, 23001, 23030, 28123, 29000, 29002, 29001, 26379, 25432) are available
- Verify Docker daemon is running: `docker info`

**Grafana login issues:**

- Verify credentials in your .env file
- Reset admin password: `docker exec -it grafana grafana-cli admin reset-admin-password newpassword`

**Prometheus targets down:**

- Copy `prometheus/prometheus.yml.example` to `prometheus/prometheus.yml` if the file is missing
- Check if `hkt-exporter` is running on port 28872
- Check if `langfuse-exporter` is running: `docker compose ps langfuse-exporter`
- Confirm `langfuse-exportor/projects.json` exists and contains valid API keys
- Verify network connectivity: `docker network ls`

**Langfuse not reachable (web/worker):**

- Ensure `langfuse-web` and `langfuse-worker` containers are healthy: `docker compose ps`
- Check that `NEXTAUTH_URL`, `DATABASE_URL`, and Clickhouse/Minio/Redis env vars are correctly set in `.env`
- Confirm required Langfuse ports are not in use by other processes

**Langfuse storage backend issues (Clickhouse/Minio/Redis/Postgres):**

- Check Clickhouse health: `curl http://localhost:28123/ping`
- Access Minio console at `http://localhost:29001` and verify the `langfuse` bucket exists
- Verify Redis is responding: `redis-cli -h localhost -p 26379 -a myredissecret`
- Confirm Postgres container is healthy: `docker compose ps postgres`

**Data persistence issues:**

- Ensure Docker volumes have proper permissions
- Check volume mounts: `docker volume ls`

**Memory issues:**

- Monitor resource usage: `docker stats`
- Adjust retention period in compose.yml if needed



## 🔖 References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [cAdvisor GitHub](https://github.com/google/cadvisor)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [HKT Custom Exporter](https://github.com/ipts-infrastructure/speedx)
- [Langfuse Documentation](https://langfuse.com/docs)



## 📄 License

