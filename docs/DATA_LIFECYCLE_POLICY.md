# Sentinel Data Lifecycle Policy

## 1. Retention Policy

### SQLite Main Database (`./data/sentinel.db`)

| Table | Retention | Rationale |
|-------|-----------|-----------|
| `metric_payloads` | 30 days | Recent metrics for trend analysis; 30d = ~180 payloads at 15min interval |
| `health_summaries` | 30 days | Health snapshots; keep aligned with payloads |
| `alerts` | 60 days | Operator investigation + trend analysis |
| `anomaly_scores` | 30 days | Baseline for new anomalies |
| `root_cause_hints` | 60 days | Incident root-cause history |
| `action_recommendations` | 90 days | Track what AI recommended (for KPI evaluation) |
| `action_requests` | 90 days | Approval audit trail |
| `approval_decisions` | 180 days | Compliance + audit |
| `node_discoveries` | 365 days | Node enrollment history |
| `change_events` | 60 days | State changes for incident reconstruction |

### Example Cleanup Query

```sql
-- Delete payloads older than 30 days
DELETE FROM metric_payloads
WHERE datetime(created_at_utc) < datetime('now', '-30 days');

-- Delete alerts older than 60 days (except critical)
DELETE FROM alerts
WHERE datetime(created_at_utc) < datetime('now', '-60 days')
  AND severity != 'critical';
```

---

## 2. Archive Policy

### Quarterly Archive (every 90 days)

**Action:**
1. Export all data older than 30 days to Parquet files (compressed)
2. Organize as `archive/sentinel-2026-Q2-metrics.parquet`, etc.
3. Delete from main SQLite after export + verification
4. Store archive in cold storage (S3 Glacier, tape, etc.)

**Format:**
- Parquet with Snappy compression
- Partitioned by table + date range
- Includes schema version and export timestamp

**Example:**
```
archive/
├── sentinel-2026-Q1-metrics.parquet.gz      (185 MB)
├── sentinel-2026-Q1-alerts.parquet.gz       (42 MB)
├── sentinel-2026-Q1-decisions.parquet.gz    (8 MB)
└── MANIFEST.json (schema info, timestamps)
```

---

## 3. Redaction Policy

### Sensitive Fields

The following fields must be redacted in archived data:

- Command-line arguments (may contain passwords/tokens)
- Environment variables
- File paths (internal IP addresses in UNC paths)
- Process names containing username

### Redaction Strategy

```python
def redact_sensitive_fields(record: dict) -> dict:
    """Redact sensitive data before archiving."""
    redacted = dict(record)
    
    # Redact command
    if 'command' in redacted:
        redacted['command'] = '<REDACTED_COMMAND>'
    
    # Redact process name if contains @
    if 'process_name' in redacted and '@' in redacted['process_name']:
        redacted['process_name'] = '<REDACTED_PROCESS>'
    
    # Mask IP in file path
    if 'path' in redacted:
        import re
        redacted['path'] = re.sub(r'\d+\.\d+\.\d+\.\d+', '<IP>', redacted['path'])
    
    return redacted
```

### Audit Log Redaction Exception

**Approval decisions and action requests are NOT redacted** — full command history must be preserved for audit trail and compliance.

---

## 4. Data Purge Procedure

### Manual Purge (operator-initiated)

```bash
# Delete all data older than specified date
python sentinel.py purge --before 2026-01-01 --confirm

# Dry-run to see what would be deleted
python sentinel.py purge --before 2026-01-01 --dry-run
```

### Automated Purge (scheduled)

Add to system cron (Linux) or Task Scheduler (Windows):

```bash
# Every Sunday at 3 AM
0 3 * * 0 python /opt/sentinel/sentinel.py purge --before $(date -d '30 days ago' +%Y-%m-%d) --confirm
```

### Purge Verification

After purge, verify:
```sql
SELECT COUNT(*) FROM metric_payloads;
-- Expect: significant reduction

SELECT MAX(created_at_utc) FROM metric_payloads;
-- Expect: recently retention date
```

---

## 5. Backup Strategy

### Daily Backup

**Schedule:** Every 24 hours (e.g., 02:00 UTC)

```bash
# Export to dated snapshot
cp ./data/sentinel.db ./backups/sentinel-$(date +%Y%m%d).db.bak
gzip ./backups/sentinel-$(date +%Y%m%d).db.bak

# Copy to remote storage
aws s3 cp ./backups/sentinel-*.db.bak.gz s3://sentinel-backups/daily/ --sse
```

### Weekly Full Archive

**Schedule:** Every Sunday at 04:00 UTC

```bash
# Export all tables to Parquet
python sentinel.py export --format parquet --output ./exports/sentinel-week-$(date +%Y-W%V).tar.gz

# Upload to cold storage
aws s3 cp ./exports/sentinel-*.tar.gz s3://sentinel-archives/weekly/ --storage-class GLACIER
```

### Retention

- Daily backups: keep 30 days
- Weekly archives: keep 2 years
- Audit log backups (immutable): keep permanently

---

## 6. Compliance and Legal Hold

### Incident Investigation Hold

When an incident requires forensic investigation:

1. Flag the incident ID in `holds.txt`
2. Do NOT purge any data related to that incident
3. Preserve full audit trail indefinitely

**Example:**
```
# holds.txt
incident-2026-05-03-service-outage

# Prevents purge of any data from:
# - Start time: 2026-05-03T14:30:00Z
# - End time: 2026-05-03T16:45:00Z
```

### GDPR / Data Privacy Retention Limits

If required by local regulations:
- Delete PII-containing fields (usernames, IPs) after 90 days
- Preserve anonymized metrics indefinitely
- Document deletion with timestamp

---

## 7. Disk Usage Monitoring

### Alert Thresholds

- **SQLite file > 500 MB:** Trigger archive job
- **Disk < 10% free:** Trigger emergency cleanup (delete oldest payloads)
- **Disk < 5% free:** Collector enters read-only mode; reject new payloads

### Monitor Script

```python
def check_disk_usage():
    db_size_mb = os.path.getsize('./data/sentinel.db') / 1024 / 1024
    disk_free_pct = psutil.disk_usage('/').percent
    
    if db_size_mb > 500:
        logger.warning(f"SQLite database at {db_size_mb}MB; archive recommended")
    
    if disk_free_pct > 90:
        logger.critical(f"Disk {disk_free_pct}% full; stopping new payload acceptance")
```

---

## Summary

- **Keep:** Recent 30-60 day payloads in SQLite (hot)
- **Archive:** Quarterly to Parquet/Glacier (cold)
- **Redact:** Sensitive fields before archiving
- **Preserve:** Audit trails (approvals/decisions) indefinitely
- **Monitor:** Disk usage; alert and purge when full
- **Hold:** Incident data on-demand for compliance
