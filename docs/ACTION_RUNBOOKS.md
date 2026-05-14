# Sentinel Action Safety Runbooks

## 1. Restart Service (systemctl / sc.exe)

### Preconditions

- Service name is in the approved list in config
- Service is currently running (health check first)
- No critical dependencies are active (check dependent services)

### Command Template

**Linux:**
```bash
systemctl restart <service_name>
```

**Windows:**
```powershell
Restart-Service -Name <service_name> -Force
```

### Success Criteria

- Exit code is 0
- Service transitions to "running" state within 30 seconds
- No error in system logs (journalctl / Event Log)

### Failure Criteria

- Exit code != 0
- Service remains stopped after 30 seconds
- Related services also fail to start

### Cooldown

- 5-minute cooldown per service; reject restart requests within window
- Prevents restart loops if service immediately crashes

### Rollback

- Manual (no automatic rollback)
- On failure, operator checks logs and decides on next action

---

## 2. Kill Process (os.kill)

### Preconditions

- PID is re-verified immediately before sending signal
- PID does not match Sentinel's own process
- Process name matches expected name (prevent collateral damage)

### Command Template

**Unix:**
```bash
kill -TERM <PID>  # SIGTERM = graceful shutdown
# Wait 5 seconds, then SIGKILL if not dead:
kill -KILL <PID>  # SIGKILL = force terminate
```

**Windows:**
```powershell
Stop-Process -Id <PID> -Force
```

### Success Criteria

- Exit code 0
- Process no longer appears in process list
- Parent process is notified (SIGCHLD or equivalent)

### Failure Criteria

- Process still exists after SIGKILL / Stop-Process
- Zombie process appears

### Cooldown

- 2-minute cooldown per PID
- If PID is recycled (new process with same ID), require explicit re-validation

### Rollback

- Manual restart of service or re-spawn if applicable

---

## 3. Disk Cleanup (safe temp/log removal)

### Preconditions

- Target directory is in whitelist: `/tmp/`, `/var/log/`, `C:\Temp\`, `C:\Windows\Temp\`
- Disk usage is above threshold (e.g., 90%)
- Directory contains only logs/temp files (age > 7 days)

### Command Template

**Linux:**
```bash
find /var/log -type f -mtime +7 -name "*.log" -delete
find /tmp -type f -atime +14 -delete
```

**Windows:**
```powershell
Get-ChildItem -Path C:\Windows\Temp -Recurse -File | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)} | Remove-Item -Force
```

### Success Criteria

- At least 10% disk space recovered
- Exit code 0
- No system services interrupted

### Failure Criteria

- Disk still above threshold
- Access denied to files
- System logs show permission errors

### Cooldown

- 1-hour cooldown per target directory
- Prevent repeated cleanup attempts

### Rollback

- Deleted files are not recoverable (this is destructive)
- Only run after manual operator verification

---

## 4. Ulimit/Resource Adjustment (resource.setrlimit)

### Preconditions

- Target service is known (e.g., nginx, database)
- New limits are within safe bounds (e.g., file descriptors: 1024 - 1M)
- Current limit is not already at max

### Command Template

**Linux (via service config):**
```ini
[Service]
LimitNOFILE=65536
LimitNPROC=32768
ExecStartPost=systemctl restart <service>
```

**Programmatic (Python):**
```python
import resource
resource.setrlimit(resource.RLIMIT_NOFILE, (65536, 65536))
```

### Success Criteria

- New limit takes effect (verify with `ulimit -n`)
- Service maintains stability after change
- No additional errors in logs

### Failure Criteria

- New limit rejected by kernel (exceeds hard limit)
- Service becomes unstable with new limit

### Cooldown

- 10-minute cooldown per service
- Allow service to stabilize before next adjustment

### Rollback

- Revert to previous limits in service config and restart

---

## 5. Approved Script Execution

### Preconditions

- Script is in `config/approved_scripts/` directory
- Script name is in approval whitelist (config value)
- Script has executable permission (Unix) or is .ps1 (Windows)
- Script does not contain shell metacharacters outside approvedlist

### Command Template

**Linux:**
```bash
/config/approved_scripts/<script_name>.sh <arg1> <arg2>
```

**Windows:**
```powershell
& "C:\Sentinel\approved_scripts\<script_name>.ps1" -Arg1 $arg1 -Arg2 $arg2
```

### Success Criteria

- Exit code 0
- Script output contains expected success marker
- No unexpected side effects (audit logs, file changes)

### Failure Criteria

- Exit code != 0
- Script output contains error marker
- Unexpected modifications detected

### Cooldown

- 5-minute cooldown per script name
- Prevent script execution loops

### Rollback

- Manual; script author must define rollback procedure in script itself

---

## Enforcement in Code

All runbooks are enforced in `sentinel/actions/gate.py`:

```python
APPROVED_ACTIONS = {
    "restart_service": {
        "command_template": "systemctl restart {service_name}",
        "preconditions": ["service_running", "no_critical_deps"],
        "cooldown_seconds": 300,
        "allowed_on": ["Linux"],
    },
    "kill_process": {
        "command_template": "kill -TERM {pid}; kill -KILL {pid}",
        "preconditions": ["pid_valid", "not_sentinel_pid", "process_name_matches"],
        "cooldown_seconds": 120,
        "allowed_on": ["Linux", "Windows"],
    },
    # ... etc
}
```

Every action request is validated against its runbook before approval/execution.
