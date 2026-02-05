# monitoring-compose

A comprehensive monitoring stack using Docker Compose with Prometheus, Grafana, cAdvisor and hkt custom exporter for system and application monitoring.

## 🚀 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Port availability: 3000 (Grafana), 9090 (Prometheus), 8080 (cAdvisor)
- Minimum 2GB RAM recommended for optimal performance

## 🛠️ Getting Started

### 1. Environment Setup
Copy the example environment file and configure your credentials:
```bash
cp .env.example .env.dev
# Edit .env.dev with your preferred Grafana admin credentials
```

### 2. Download & install HKT exporter binary
Download the appropriate binary from [releases](https://github.com/ipts-infrastructure/speedx/releases):

**macOS:**
```bash
# Download and install (Please ensure the visibility of the Github was PUBLIC)
curl -L -o hkt-prom-exporter-darwin-arm64 https://github.com/ipts-infrastructure/speedx/releases/latest/download/hkt-prom-exporter-darwin-arm64
chmod +x hkt-prom-exporter-darwin-arm64
sudo mv hkt-prom-exporter-darwin-arm64 /usr/local/bin/

# Setup log file permissions
sudo touch /var/log/hkt_exporter.log
sudo chown $(whoami) /var/log/hkt_exporter.log

# Setup auto-start (optional)
cp ./speedx/com.hkt.hkt-prom-exporter.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hkt.hkt-prom-exporter.plist

# Validate plist format
plutil -lint ~/Library/LaunchAgents/com.hkt.hkt-prom-exporter.plist

# Unload if needed
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.hkt.hkt-prom-exporter.plist
```

### 3. Start the Stack
```bash
# Development
docker compose --env-file .env.dev up -d

# Production  
docker compose --env-file .env.prod up -d
```

### 4. Access Services
- **Grafana Dashboard**: http://localhost:3000
  - Username: `admin` (or as configured in .env)
  - Password: `admin` (or as configured in .env)
- **Prometheus**: http://localhost:9090
- **cAdvisor**: http://localhost:8080
- **HktExporter**: http://localhost:8872/metrics

### 5. Stop the Stack
```bash
docker compose down
```

## 🚨 Troubleshooting

### Common Issues

**Services not starting:**
- Check if required ports (3000, 9090, 8080) are available
- Verify Docker daemon is running: `docker info`

**Grafana login issues:**
- Verify credentials in your .env file
- Reset admin password: `docker exec -it grafana grafana-cli admin reset-admin-password newpassword`

**Prometheus targets down:**
- Check if `hkt-exporter` is running on port 8872
- Verify network connectivity: `docker network ls`

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

## 📄 License