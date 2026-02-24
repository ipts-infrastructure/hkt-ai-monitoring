# monitoring-compose

A comprehensive monitoring stack using Docker Compose with Prometheus, Grafana, cAdvisor and hkt custom exporter for system and application monitoring.

## 🚀 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Port availability: 3200 (Grafana), 9290 (Prometheus), 8280 (cAdvisor)
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
- **Grafana Dashboard**: http://localhost:3200
  - Username: `admin` (or as configured in .env)
  - Password: `admin` (or as configured in .env)
- **Prometheus**: http://localhost:9290
- **cAdvisor**: http://localhost:8280
- **HktExporter**: http://localhost:8872/metrics

### 5. Stop the Stack
```bash
docker compose down
```

## 🚨 Troubleshooting

### Common Issues

**Services not starting:**
- Check if required ports (3200, 9290, 8280) are available
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