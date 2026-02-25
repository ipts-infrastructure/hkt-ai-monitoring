# monitoring-compose

A comprehensive monitoring stack using Docker Compose with Prometheus, Grafana, cAdvisor and hkt custom exporter for system and application monitoring.

## 🚀 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Port availability: 23000 (Grafana), 29090 (Prometheus), 28080 (cAdvisor), 23030 (Langfuse worker), 23001 (Langfuse web), 28123 & 29000 (Clickhouse), 29002 & 29001 (Minio), 26379 (Redis), 25432 (Postgres)
- Minimum 2GB RAM recommended for optimal performance

## 🛠️ Getting Started

### 1. Environment Setup
Copy the example environment file and configure your credentials:
```bash
cp .env.example .env.dev
# Edit .env.dev with your preferred Grafana admin credentials
# Edit .env.dev with your langfuse secret configure
```

### 2. Download & install HKT exporter binary
Download the appropriate binary from [releases](https://github.com/ipts-infrastructure/speedx/releases):

**macOS:**
```bash
# Download and install (Please ensure the visibility of the Github was PUBLIC)
curl -L -o hkt-prom-exporter-darwin-arm64 https://github.com/ipts-infrastructure/speedx/releases/latest/download/hkt-prom-exporter-darwin-arm64 # Downloads the binary file from release
chmod +x hkt-prom-exporter-darwin-arm64                                         # Add exeuction permission 
sudo mv hkt-prom-exporter-darwin-arm64 /usr/local/bin/                          # Moves the binary to a standard location

# Setup auto-start (optional)
cp ./speedx/com.hkt.hkt-prom-exporter.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.hkt.hkt-prom-exporter.plist    # Change ownership 
sudo chmod 644 /Library/LaunchDaemons/com.hkt.hkt-prom-exporter.plist           # Change approriate permission 
plutil -lint /Library/LaunchDaemons/com.hkt.hkt-prom-exporter.plist             # Validate plist format
sudo launchctl load -w /Library/LaunchDaemons/com.hkt.hkt-prom-exporter.plist   # Loads the plist and enables it

# Unload if needed
sudo launchctl unload -w /Library/LaunchDaemons/com.hkt.hkt-prom-exporter.plist # Stops the service and removes auto-start
```

### 3. Start the Stack
```bash
# Development
docker compose --env-file .env.dev up -d

# Production  
docker compose --env-file .env.prod up -d
```

### 4. Access Services
- **Grafana Dashboard**: http://localhost:23000
  - Username: `admin` (or as configured in .env)
  - Password: `admin` (or as configured in .env)
- **Prometheus**: http://localhost:29090
- **cAdvisor**: http://localhost:28080
- **HktExporter**: http://localhost:8872/metrics
- **Langfuse Web UI**: http://localhost:23001
- **Langfuse Worker**: http://localhost:23030 (internal worker UI / health)
- **Langfuse Clickhouse HTTP**: http://localhost:28123
- **Langfuse Clickhouse TCP**: localhost:29000
- **Langfuse Minio S3 endpoint**: http://localhost:29002
- **Langfuse Minio Console**: http://localhost:29001
- **Langfuse Redis**: localhost:26379
- **Langfuse Postgres**: localhost:25432

### 5. Stop the Stack
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
- Check if `hkt-exporter` is running on port 8872
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