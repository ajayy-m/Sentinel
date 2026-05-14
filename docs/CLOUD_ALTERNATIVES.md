# Cloud & Hosted Alternatives (When Docker/Local Prometheus Not Available)

If local Prometheus and Grafana cannot be installed, consider these alternatives:

## 1. Grafana Cloud (Recommended for Quick Setup)

**Best for:** Teams wanting hosted observability without infrastructure.

- Sign up: https://grafana.com/auth/sign-up/create-account
- Free tier includes:
  - 3 GB logs retention
  - 10K metrics
  - Access to Grafana Cloud dashboards
  
**Integration with Sentinel:**
1. Create a Grafana Cloud API key
2. Set up Prometheus remote write to Grafana Cloud
3. Use Sentinel's collector `/metrics` endpoint as a scrape target on a remote Prometheus instance

**Typical setup:**
- Deploy Prometheus on a single remote server (Linux VM, cloud instance, or even WSL2)
- Configure Prometheus remote_write to send metrics to Grafana Cloud
- View dashboards in Grafana Cloud UI

**Cost:** Free tier up to limits; $49/month for larger deployments.

## 2. Datadog

**Best for:** Enterprises wanting turnkey observability + AI-assisted alerting.

- Site: https://www.datadoghq.com/
- Sentinel integration path:
  1. Export metrics from Sentinel collector to Datadog agent
  2. Or push metrics via Datadog HTTP API
  
**Pros:** Built-in anomaly detection, full-stack monitoring, extensive integrations.

**Cost:** $15–$40+ per host/month depending on features.

## 3. New Relic

**Best for:** Full APM + infrastructure monitoring in one platform.

- Site: https://newrelic.com/
- Sentinel integration:
  1. Use New Relic's Prometheus integration
  2. Remote write from Prometheus → New Relic
  
**Cost:** Free tier for small setups; $99+/month for production.

## 4. Prometheus + Grafana on a Remote Linux VM

**Best for:** Cost-conscious orgs wanting self-hosted control without Docker.

If local Windows Docker is blocked but you have access to a Linux VM (cloud or on-premises):

1. **Provision a Linux VM** (AWS EC2, Azure VM, DigitalOcean droplet, or Hyper-V)
   - Ubuntu 20.04 LTS or CentOS 8 recommended
   - Small instance size is fine (1 GB RAM, 20 GB disk)

2. **Install Prometheus & Grafana** (native Linux binaries):
   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install prometheus grafana-server
   
   # Or use Docker on the VM (if allowed)
   docker run -d -p 9090:9090 prom/prometheus
   docker run -d -p 3000:3000 grafana/grafana
   ```

3. **Configure Prometheus** on the VM to scrape Sentinel collector:
   ```yaml
   # /etc/prometheus/prometheus.yml
   scrape_configs:
     - job_name: 'sentinel-fleet'
       static_configs:
         - targets: ['<your-windows-collector-ip>:8000']
   ```

4. **Access dashboards** from the VM or via port forwarding:
   - Prometheus: `http://<vm-ip>:9090`
   - Grafana: `http://<vm-ip>:3000`

**Cost:** $5–20/month for a small VM on major clouds.

## 5. Cloud-Agnostic: Prometheus on WSL2

**Best for:** Developers who want minimal overhead without full Docker Desktop.

If WSL2 is permitted by your organization:

1. Install WSL2 with Ubuntu
2. Run Prometheus and Grafana as Linux services inside WSL2:
   ```bash
   # Inside WSL2 Ubuntu terminal
   sudo apt install prometheus grafana-server
   sudo systemctl start prometheus grafana-server
   ```
3. Configure Prometheus to scrape your Windows Sentinel collector:
   ```yaml
   scrape_configs:
     - job_name: 'sentinel'
       static_configs:
         - targets: ['host.docker.internal:8000']  # or Windows machine IP
   ```
4. Access from Windows:
   - Prometheus: `http://localhost:9090`
   - Grafana: `http://localhost:3000`

**Cost:** Free; only requires WSL2 and Ubuntu image.

## Recommendation Matrix

| Scenario | Solution | Effort | Cost | Notes |
|----------|----------|--------|------|-------|
| **Enterprise with cloud agreement** | Datadog / New Relic | Medium | $15–40/month | Full-stack monitoring included |
| **Quick hobby/lab setup** | Grafana Cloud + Prometheus on WSL2 | Low | Free–$10/month | Fastest to market |
| **Self-hosted, no Docker** | Prometheus + Grafana on remote Linux VM | Medium | $5–20/month | Maximum control |
| **Local Windows only** | Native Windows binaries (recommended first option) | Low | Free | See `NATIVE_PROMETHEUS_GRAFANA_SETUP.md` |
| **Developer/WSL environment** | Prometheus + Grafana in WSL2 | Low | Free | Simplest for Windows devs |

## Quick Decision Tree

```
Is Docker available on Windows?
  └─ YES → Use docker-compose (deploy/docker/docker-compose.yml)
  └─ NO  → Does your org permit WSL2?
           └─ YES → Use WSL2 + Linux Prometheus/Grafana
           └─ NO  → Does your org have a Linux VM/cloud account?
                    └─ YES → Install Prometheus/Grafana on remote VM
                    └─ NO  → Use native Windows binaries (docs/NATIVE_PROMETHEUS_GRAFANA_SETUP.md)
```

## Sentinel Metrics Exported

Regardless of which observability backend you choose, Sentinel exposes these key metrics:

- `sentinel_collector_received_payloads_total` — total payloads received
- `sentinel_cpu_usage_percent` — last known CPU %
- `sentinel_memory_usage_bytes` — last known memory bytes
- `sentinel_disk_usage_percent` — last known disk %
- `sentinel_anomalies_detected_total` — anomalies scored
- Standard Python process metrics (heap, GC, threads)

See `deploy/grafana/sentinel-observability-dashboard.json` for dashboard template.
