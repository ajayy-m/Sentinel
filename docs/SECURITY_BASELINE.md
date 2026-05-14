# Sentinel Security Baseline

## 1. Node Identity Model

**Goal:** Each monitored node has a stable, unforgeable identity.

### Node ID Generation

- Each node auto-derives a `node_id` = `hostname + sha1(hostname|os|machine|uuid)[:12]`
- Example: `DESKTOP-ABC-a7f8b2c3d4e1`
- This is stable across reboots and derivable from the machine itself
- Optional override via `SENTINEL_NODE_ID` env var for special deployments (cloud instances with ephemeral hostnames)

### Node Trust Model

- **Single-LAN assumption:** All agents and collector are on the same trusted network segment
- **No end-to-end encryption (v1):** Messages use UDP broadcast discovery on same subnet
- **Implicit trust:** Node IDs are not cryptographically signed; we rely on network boundary
- **Future (v2.0):** Add HMAC signing of payloads with shared symmetric key per node

## 2. Message Integrity and Authentication

### Current (v1.0)

- Discovery broadcasts are unsigned JSON over UDP
- Collector and agents respond to any discovery request without auth
- **Implication:** Only deploy on trusted internal networks

### Replay Protection

- Each payload includes `timestamp_utc` (ISO8601)
- Collector stores latest timestamp per node; drops payloads older than newest
- **Cooldown:** Collector rejects duplicate payloads within 1-second window
- **Rationale:** Prevents simple packet replay attacks on same LAN

### Recommended Deployment Constraint

- Collector and agents on internal network only (firewall rule: reject external traffic on discovery/ZMQ ports)
- No public internet exposure without additional layers (VPN, TLS termination, auth proxy)

## 3. Key Rotation and Compromised Node Revocation

### Current (v1.0)

- No cryptographic keys; discovery/ZMQ in cleartext
- Node identity is non-repudiable but not secret

### Future (v2.0)

- Each node gets a random shared secret (key) during onboarding
- Payloads include HMAC(payload, key) signature
- Key rotation: central config push with new key, short grace period for old key
- Revocation: central config blacklist of node IDs (collector rejects from blacklisted IDs)

### Operational Procedure (v1.0)

Even before full HMAC rollout, operators should follow this procedure when rotating or revoking access:

1. **Rotate shared config values**
   - Update `SENTINEL_SHARED_KEY` in the secure config store
   - Roll collector first, then agents, to avoid mixed-mode failures
   - Keep the previous value active for one maintenance window only

2. **Revoke a compromised node**
   - Add the node ID to the collector-side denylist configuration
   - Restart the collector so the denylist is applied consistently
   - Verify that the node no longer appears in discovery or payload logs

3. **Verify least privilege runtime**
   - Linux: run the agent under the dedicated `sentinel` service account with read-only access to telemetry sources and write access only to logs/data
   - Windows: run the agent and collector as dedicated low-privilege service accounts; avoid interactive admin sessions for steady-state operation
   - Confirm the service account cannot modify system configuration, install software, or spawn arbitrary shells

## 4. Least Privilege Runtime

### Linux Agent

```bash
# Create dedicated user (non-login shell)
sudo useradd -r -s /usr/sbin/nologin -M -d /var/sentinel sentinel

# Agent runs as sentinel user with permission to:
# - Read /proc, /sys for metrics
# - Execute psutil probes
# - Write to /var/log/sentinel/
# - Connect to collector (TCP outbound)

# NOT permitted to:
# - Write to system config
# - Execute arbitrary commands
# - Access other user home dirs
```

### Windows Agent

```powershell
# Run as dedicated low-privilege service account
New-LocalUser -Name SentinelAgent -NoPassword -AccountNeverExpires -PasswordNeverExpires

# Service runs as SentinelAgent with permissions to:
# - Read WMI performance counters
# - Read Event Log
# - Connect to collector (TCP outbound)

# NOT permitted to:
# - Write to Program Files
# - Modify registry
# - Execute scripts without whitelist
```

## 5. Audit Trail Security

- All approval decisions, action requests, and executed commands are stored in immutable append-only SQLite tables
- Schema enforces:
  - `created_at_utc` is auto-set at insert time, never editable
  - No DELETE or UPDATE on approval_decisions or action_requests tables (policy enforced in code)
  - All changes logged to `audit_log` table with actor identity
- Backup strategy: daily SQLite snapshots to immutable storage (S3, cold archive, etc.)

## 6. Recommendations for Multi-Node Production

1. **Network Isolation**
   - Deploy collector + agents on private VLAN with firewall rules
   - Reject all traffic on discovery/ZMQ ports from outside VLAN

2. **Authentication Layer (future)**
   - Wrap discovery in HMAC-SHA256 signatures
   - Rotate keys monthly
   - Blacklist compromised nodes immediately

3. **Encryption (future)**
   - Use ZMQ CurveZMQ for agent-collector traffic (built-in ZMQ TLS replacement)
   - TLS for UI-to-collector REST API (if added)

4. **Monitoring & Audit**
   - Log all approval decisions and agent registration
   - Alert on unusual node registrations or repeated auth failures
   - Backup audit trail daily to cold storage

5. **Incident Response**
   - Revocation procedure: add node ID to blacklist in config, restart collector
   - Re-credential procedure: generate new shared key, push to agent via secure channel
   - Forensics: SQLite backup + audit logs allow timeline reconstruction
