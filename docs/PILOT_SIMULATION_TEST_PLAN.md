# Pilot Simulation & Test Plan

**Duration:** 1 week (2026-05-05 to 2026-05-12)  
**Target Hosts:** 2-3 representative lab nodes  
**Objective:** Validate anomaly detection, false-positive rates, and operator workflows

---

## Phase 1: Pilot Setup (Day 1)

### Prerequisites
- ✅ All release gates verified (see [RELEASE_GATE_VERIFICATION.md](RELEASE_GATE_VERIFICATION.md))
- ✅ Sentinel collector/agent/UI running on pilot nodes
- ✅ Metrics exporter enabled for metrics collection (optional)
- ✅ 2-3 target nodes identified (varied OS/workloads preferred)

### Deployment Steps

```powershell
# On each pilot host

# 1. Clone/pull latest Sentinel code
git clone https://github.com/YOUR_ORG/sentinel.git
# or: git pull origin main

# 2. Set up virtualenv
cd sentinel
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Enable simulation mode in config
# Edit config/config.yaml:
# - Set enable_simulation: true
# - Set simulation_spike_interval_seconds: 60 (spike every 1 minute)
# - Set simulation_anomaly_types: [cpu, memory, disk]
# - Set enable_llm: true (to test root-cause hints)

# 4. Start collector (on central hub or each node)
python sentinel.py collector --config config/config.yaml

# 5. Start agent (on each pilot node)
python sentinel.py agent --config config/config.yaml

# 6. Start UI (on operator workstation)
python sentinel.py ui --config config/config.yaml
```

### Sample Pilot config/config.yaml
```yaml
system:
  node_id: "pilot-node-1"  # Unique per node

transport:
  endpoint: "tcp://127.0.0.1:5556"
  discovery:
    enabled: true

collector:
  storage_enabled: true
  sqlite_path: "./data/sentinel.db"
  # prometheus exporter configuration (optional)
  # prometheus:
  #   enabled: true
  #   port: 8000

pipeline:
  cpu_warn_percent: 75       # Lower thresholds for simulation sensitivity
  cpu_critical_percent: 90
  memory_warn_percent: 75
  memory_critical_percent: 90
  disk_warn_percent: 80
  disk_critical_percent: 90

anomaly:
  window_size: 20
  min_samples: 8
  zscore_warn: 1.5           # Lower z-score to catch more anomalies (testing)
  zscore_critical: 2.5

root_cause:
  enable_llm: true           # Enable LLM for root-cause hints
  window_seconds: 60

recommendations:
  cooldown_seconds: 30

approval_gate:
  auto_promote_recommendations: false  # Require manual review

# Simulation settings (test mode)
simulation:
  enabled: true
  spike_interval_seconds: 60
  spike_duration_seconds: 10
  anomaly_types: [cpu, memory, disk]
  spike_percent_increase: 50  # +50% from baseline

ui:
  window_title: "Sentinel Pilot Control Center"
  refresh_interval_ms: 1000   # Faster refresh for demo
  max_rows: 20
```

---

## Phase 2: Baseline & Warmup (Days 1-2)

### Objectives
- Establish normal baseline metrics
- Verify data pipeline is working
- Identify any false-positives from normal operations

### Testing Steps

```powershell
# 1. Monitor baseline metrics for 2 hours with NO simulation
# - Check that no anomalies trigger
# - Record typical CPU, memory, disk ranges
# - Verify payloads are flowing

Get-Content .\logs\collector.log -Wait -Tail 20

# 2. Check UI fleet dashboard
# - Should show all nodes as "healthy"
# - Score should be high (90+)
# - No alerts or anomalies visible

# 3. Verify metrics exporter (if enabled)
# If enabled, verify the `/metrics` endpoint or alternatively confirm ingestion via the database:
& "i:/Projects/Coding Projects/College Projects/Helios/venv/Scripts/python.exe" -c "import sqlite3; conn=sqlite3.connect('./data/sentinel.db'); print(conn.execute('SELECT COUNT(*) FROM metrics').fetchone()); conn.close()"

# 4. Record baseline numbers
# - Active nodes count
# - Latest health score
# - Latest alerts count (should be 0)
```

### Success Criteria
- No spurious alerts on idle/normal system
- All payloads persisting to database
- UI refreshing every 1-2 seconds without lag

---

## Phase 3: Simulation Testing (Days 2-5)

### Test Case 1: CPU Spike Detection

**Trigger:** Simulation spikes CPU to 50% above baseline  
**Expected Behavior:**
- Anomaly detected within 30 seconds
- Alert generated with "CPU" category
- Root-cause hint generated (if LLM enabled)
- Recommendation created

**Verification:**
```powershell
# 1. Monitor logs during spike
Get-Content .\logs\collector.log -Wait | Select-String "anomaly|alert|recommendation"

# 2. Check UI
# - Verify alert appears in "Alerts" tab
# - Verify anomaly appears in "Root Cause" tab
# - Verify recommendation appears in "Recommendations" tab

# 3. Record metrics
# - Detection latency (from spike start to alert creation)
# - Confidence score of root-cause hint
# - Recommendation priority (high/medium/low)
```

**Acceptance Criteria:**
- ✅ Detection latency < 30 seconds
- ✅ Root-cause confidence > 60% (if LLM enabled)
- ✅ Recommendation generated (non-empty title + reason)

---

### Test Case 2: Memory Spike Detection

**Trigger:** Simulation spikes memory to 50% above baseline  
**Expected Behavior:**
- Similar to CPU spike (see above)
- Alert category should be "Memory"

**Verification:** Same as Test Case 1

---

### Test Case 3: Disk Spike Detection

**Trigger:** Simulation spikes disk to 50% above baseline  
**Expected Behavior:**
- Similar to CPU spike (see above)
- Alert category should be "Disk"

**Verification:** Same as Test Case 1

---

### Test Case 4: Multi-Metric Anomaly (CPU + Memory)

**Trigger:** Simulate CPU and memory spike simultaneously  
**Expected Behavior:**
- Both anomalies detected
- Root-cause correlator links them (e.g., "process memory leak causing CPU thrashing")
- Single correlated recommendation (not two separate ones)

**Verification:**
```powershell
# 1. Check that only one recommendation is generated (not duplicates)
# 2. Check root-cause message references both metrics
# 3. Verify confidence score is high (correlation detected)
```

---

### Test Case 5: False-Positive Rate

**Duration:** 8 hours continuous simulation  
**Objective:** Measure noise (false alarms) vs real anomalies

**Methodology:**
1. Run simulation spikes for 8 hours (1 spike per hour, 10 seconds duration)
2. Count total alerts generated
3. Manually audit: which are valid anomalies, which are false alarms
4. Calculate false-positive rate = (false alerts / total alerts) * 100

**Expected Results:**
- False-positive rate < 5%
- If exceeds 5%, adjust z-score thresholds in config

**Recording Template:**
```
Timestamp | Spike Type | Alert Generated | Alert Category | Latency | Valid? | Notes
2026-05-05 14:00 | CPU | YES | CPU | 15s | YES | Correct detection
2026-05-05 14:01 | CPU | YES | CPU | 18s | YES | Correct detection
2026-05-05 14:02 | Disk | NO | N/A | N/A | N/A | FALSE NEGATIVE - spike not detected
2026-05-05 14:05 | NONE | YES | Memory | 5s | NO | FALSE POSITIVE - no spike triggered
...
```

---

## Phase 4: Operator Workflow Testing (Days 5-6)

### Test Case 6: Recommendation Review & Action

**Trigger:** Generate 10 recommendations via simulation  
**Expected Behavior:**
- Operator reviews each recommendation
- Operator approves/rejects based on merit
- Decision is recorded in database

**Procedure:**
```powershell
# 1. Watch UI Recommendations tab
# 2. Right-click on a recommendation → "Promote to Action Request"
# 3. Review request in Action Queue tab
# 4. Right-click on request → "Approve" or "Reject"
# 5. Verify decision logged in Decision Log tab
```

**Metrics to Record:**
- Recommendation count
- Approved count
- Rejected count
- Approval rate = (Approved / Total) * 100
- Average time to approve (from creation to approval)

**Success Criteria:**
- ✅ Approval rate > 60% (operators trust recommendations)
- ✅ Average approval time < 2 minutes
- ✅ All decisions persisted to database (audit trail)

---

### Test Case 7: Restart Resilience

**Trigger:** Kill collector, restart it, verify agent reconnects  
**Expected Behavior:**
- Collector restarts without data loss
- Agent reconnects within 30 seconds
- Payloads resume flowing
- No recommendations lost

**Procedure:**
```powershell
# 1. Kill collector
Get-Process python | Where-Object { $_.CommandLine -like "*collector*" } | Stop-Process -Force

# 2. Monitor agent logs for reconnection attempts
Get-Content .\logs\agent.log -Wait | Select-String "connect|retry|failed"

# 3. Restart collector
& "i:/Projects/Coding Projects/College Projects/Helios/venv/Scripts/python.exe" sentinel.py collector --config config/config.yaml

# 4. Verify agent reconnects
# Should see "Connected to collector" or similar in agent.log within 30s

# 5. Verify UI shows all historical data still intact
# - Recommendations tab should still show previous recommendations
# - Decision log should be unchanged
```

**Success Criteria:**
- ✅ Agent reconnects within 30 seconds
- ✅ No data loss (all recommendations/decisions still in DB)
- ✅ New payloads flow normally after restart

---

## Phase 5: KPI Measurement & Analysis (Day 7)

### Key Performance Indicators (KPIs)

| KPI | Target | Measurement Method | Acceptance |
|-----|--------|-------------------|------------|
| **Detection Latency** | < 30 sec | Timestamp(spike_start) → timestamp(alert_created) | PASS if median < 30s |
| **False-Positive Rate** | < 5% | (false_alerts / total_alerts) * 100 | PASS if < 5% |
| **Operator Approval Rate** | > 60% | (approved / total_recommendations) * 100 | PASS if > 60% |
| **System Uptime** | > 99% | (runtime - downtime) / runtime * 100 | PASS if > 99% |
| **Data Persistence** | 100% | Verify all records in DB after restart | PASS if no data loss |

### Analysis Template

```
=================================================================
SENTINEL PILOT - KPI ANALYSIS REPORT
Duration: 2026-05-05 to 2026-05-12
Hosts Tested: pilot-node-1, pilot-node-2, pilot-node-3
=================================================================

DETECTION LATENCY
- Median latency: _____ seconds
- 95th percentile: _____ seconds
- Min: _____ seconds
- Max: _____ seconds
- Status: [PASS / FAIL]

FALSE-POSITIVE RATE
- Total alerts: _____
- False alarms: _____
- False-positive rate: _____ %
- Status: [PASS / FAIL]

OPERATOR APPROVAL RATE
- Total recommendations: _____
- Approved: _____
- Rejected: _____
- Approval rate: _____ %
- Avg time to approve: _____ minutes
- Status: [PASS / FAIL]

SYSTEM UPTIME
- Total runtime: _____ hours
- Downtime incidents: _____ (list each)
- Total downtime: _____ minutes
- Uptime percentage: _____ %
- Status: [PASS / FAIL]

DATA PERSISTENCE
- Anomalies persisted: _____
- Recommendations persisted: _____
- Decisions persisted: _____
- Data loss incidents: [NONE / describe]
- Status: [PASS / FAIL]

=================================================================
OVERALL RESULT: [PILOT PASS / PILOT FAIL]
Recommended Actions:
- _________________________________________________________________
- _________________________________________________________________

Lessons Learned:
- _________________________________________________________________
- _________________________________________________________________
```

---

## Rollback During Pilot

If critical issues occur:

```powershell
# 1. Stop all Sentinel processes
Get-Process python | Where-Object { $_.CommandLine -like "*sentinel*" } | Stop-Process -Force

# 2. Restore previous database backup (if available)
Copy-Item -Path "./data/sentinel.db.backup" -Destination "./data/sentinel.db" -Force

# 3. Revert code to previous commit (if needed)
git checkout <previous_commit_hash>

# 4. Restart
.\scripts\start_local_stack.ps1
```

---

## Monitoring During Pilot

### Log Files to Watch
- `logs/collector.log` — payload ingestion, anomaly detection
- `logs/agent.log` — payload generation, connectivity
- `logs/ui.log` — UI events and errors

### Commands for Real-Time Monitoring

```powershell
# Watch collector anomaly detections
Get-Content .\logs\collector.log -Wait | Select-String "anomaly|alert|recommendation"

# Watch agent payload generation
Get-Content .\logs\agent.log -Wait | Select-String "payload|send|response"

# Check active connections
Get-NetTCPConnection | Where-Object { $_.LocalPort -eq 5556 -or $_.LocalPort -eq 8000 }
```

### Prometheus Queries

```
# Payload ingestion rate
rate(sentinel_collector_received_payloads_total[1m])

# Active nodes
sentinel_collector_active_nodes

# Detection latency (custom metric if enabled)
rate(sentinel_anomaly_detection_latency_seconds[1m])
```

---

## Success Criteria for Pilot Pass

**All of the following must be true:**
1. ✅ Detection latency < 30 seconds (median)
2. ✅ False-positive rate < 5%
3. ✅ Operator approval rate > 60%
4. ✅ System uptime > 99%
5. ✅ Zero data loss on restart

**If all passed:** Proceed to limited production rollout on additional nodes.

**If any failed:** Return to tuning phase and re-run pilot.

---

See [Plan.txt](../Plan.txt) for overall project roadmap.
