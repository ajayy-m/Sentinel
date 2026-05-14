# Sentinel Implementation Checklist

Use this checklist as a release gate before and during development.
Status legend: [ ] Not done, [x] Done, [N/A] Not applicable.

## Project Metadata

- Project name: Sentinel 
- Owner:
- Date started:
- Target release:

## Phase 0 Gate: Hardening and Portability

### 1. Versioned Contracts

- [x] Define schema versioning strategy for metric payloads.
- [x] Define schema versioning strategy for change events.
- [x] Define schema versioning strategy for alerts/incidents.
- [ ] Define schema versioning strategy for ActionRequest and ActionResult.
- [x] Document compatibility behavior when agent version is newer than collector version.
- [ ] Add contract validation tests for valid and invalid payloads.

Evidence:
- Spec file path: sentinel/core/schema.py
- Test file path:
- Reviewer:

### 2. Security Baseline

- [x] Define node identity model (node_id ownership and trust model).
- [ ] Define message integrity/authentication for multi-node mode.
- [x] Define replay protection mechanism.
- [ ] Define key rotation procedure.
- [ ] Define compromised-node revocation procedure.
- [ ] Verify least-privilege runtime for Linux agent.
- [ ] Verify least-privilege runtime for Windows agent.

Evidence:
- Security doc path: docs/SECURITY_BASELINE.md
- Threat assumptions:
- Reviewer:

### 3. Action Safety Runbooks

- [x] Restart service runbook completed.
- [x] Kill process runbook completed.
- [x] Disk cleanup runbook completed.
- [x] Ulimit/resource adjustment runbook completed.
- [x] Approved script execution runbook completed.
- [x] Every runbook includes preconditions.
- [x] Every runbook includes exact command templates.
- [x] Every runbook includes success and failure criteria.
- [x] Every runbook includes cooldown/rate limit.
- [x] Every runbook includes rollback or compensating action.
- [ ] Idempotency behavior documented and tested where possible.

Evidence:
- Runbook path: docs/ACTION_RUNBOOKS.md
- Test log path:
- Reviewer:

### 4. Audit Trail Guarantees

- [x] Persist approval identity for every action.
- [x] Persist proposed command and executed command.
- [x] Persist target node/service/process details.
- [x] Persist timestamps, exit code, stdout, stderr.
- [x] Confirm audit records are append-only or immutable by policy.
- [x] Verify retrieval query for incident reconstruction.

Evidence:
- Storage schema path: sentinel/core/storage.py
- Example audit record ID:
- Test file path: tests/test_storage_audit_immutability.py
- Reviewer:

### 5. AI Evaluation Criteria

- [x] False-positive budget defined.
- [x] Detection latency target defined.
- [x] Precision/recall target defined.
- [x] Time-to-explanation target in UI defined.
- [ ] Rule-only baseline detector implemented for comparison.
- [ ] Evaluation dataset (real or synthetic) prepared.

Evidence:
- KPI doc path: docs/AI_EVALUATION_KPI.md
- Benchmark script path:
- Reviewer:

### 6. Simulation Mode (Mandatory)

- [x] Replay mode implemented with recorded or synthetic telemetry.
- [x] Full pipeline validated in simulation mode.
- [x] Confirmation gate remains active in simulation.
- [ ] Action queue and approvals tested without live impact.
- [ ] AI explanations verified against replayed incidents.

Evidence:
- Simulation config path:
- Test scenario IDs:
- Reviewer:

### 7. Data Lifecycle Policy

- [ ] Retention policy defined for DuckDB metric store.
- [x] Retention policy defined for SQLite config/incident store.
- [x] Archive policy defined for Parquet exports.
- [x] Compression policy defined.
- [x] Sensitive field redaction policy defined.
- [x] Data purge procedure documented and tested.

Evidence:
- Policy doc path: docs/DATA_LIFECYCLE_POLICY.md
- Purge test path: tests/test_storage_purge.py
- Purge command path: sentinel/core/purge.py, sentinel.py role=purge
- Reviewer:

### 8. Packaging and Deployment

- [x] Linux systemd unit and install steps documented.
- [x] Windows service wrapper and install steps documented.
- [x] Dependency manifest completed for both OS targets.
- [x] Config schema is identical across OS targets.
- [x] Upgrade plan documented.
- [x] Rollback plan documented.

Evidence:
- Packaging doc path: docs/PACKAGING_DEPLOYMENT.md
- Installer script path: deploy/windows/install-services.ps1
- Linux unit path: deploy/linux/sentinel-collector.service, deploy/linux/sentinel-agent.service
- Reviewer:

### 9. Portability: No Hardcoded Deployment Values

- [x] No hardcoded hostnames or IP addresses in source.
- [x] No hardcoded ports in source (except overridable defaults).
- [x] No hardcoded absolute filesystem paths in source.
- [x] No hardcoded usernames or machine-specific identifiers.
- [x] No hardcoded node IDs.
- [x] No hardcoded service names outside config.
- [x] No hardcoded OS command variants outside adapters.
- [x] All deployment values sourced from config, env vars, or CLI.
- [x] Startup fails fast with clear error when required config is missing.

Verification method:
- [x] Run static search for common literals (hosts, paths, ports).
- [x] Run startup with intentionally missing config to verify fail-fast.
- [x] Run startup with alternate config values to verify dynamic behavior.

Evidence:
- Search command/results path: scripts/verify_portability.ps1
- Validation test path: scripts/verify_portability.ps1 -RunFailFastCheck
- Reviewer:

### 10. Startup Preflight Readiness

- [x] Validate writable data directory.
- [x] Validate writable log directory.
- [x] Validate required runtime dependencies.
- [x] Probe optional capabilities (GPU, OS-specific providers).
- [ ] Validate transport/auth configuration for selected mode.
- [x] Print concise readiness report before steady state.

Evidence:
- Preflight module path: sentinel/core/preflight.py
- Example readiness report: validated in collector run on 2026-05-04
- Reviewer:

### 11. Portability Acceptance Test

Pass condition: fresh Linux and fresh Windows setup succeeds with no source code edits.

- [ ] Linux fresh install completed using config/env only.
- [ ] Windows fresh install completed using config/env only.
- [ ] First telemetry received within startup window.
- [ ] Central UI shows node health without manual code changes.
- [ ] Action approval workflow functions on both OS targets.

Evidence:
- Linux test environment details:
- Windows test environment details:
- Test run date:
- Reviewer:

## Phase 1 Entry Decision

- [ ] All mandatory Phase 0 items completed.
- [ ] Risks accepted for any deferred non-mandatory item.
- [ ] Team sign-off complete.

Sign-off:
- Engineering:
- Security:
- Operations:
- Date:

## Production Readiness Decision

- [ ] Simulation suite passed.
- [ ] Audit trail verified.
- [ ] Portability acceptance test passed.
- [ ] Rollback tested.

Sign-off:
- Engineering:
- Security:
- Operations:
- Date:
