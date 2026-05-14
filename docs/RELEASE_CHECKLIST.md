# Release Checklist

This checklist is the minimal set of items required to cut a controlled pilot release.

## Preconditions
- [ ] All critical tests pass locally (`tests/`)
- [ ] Preflight checks pass on target hosts (`python sentinel.py preflight`)
- [ ] Config templates updated and validated (`config/*.yaml`)

## Verification
- [ ] Collector/agent/ui/api start from `scripts/start_pilot_stack.ps1` or individual commands
- [ ] Metrics exporter available (if enabled) or data ingest verified
- [ ] Read-only API responding (`/health`, `/summary`, `/recommendations`)
- [ ] Sample run of simulator (optional) to validate detection paths

## Security
- [ ] Verify `transport.auth` configuration and shared-key rotation plan
- [ ] Ensure audit append-only tables are present and triggers enabled

## Packaging
- [ ] Build artifacts created (wheel, sdist) and `requirements.txt` pinned
- [ ] Scripts and service templates included (systemd, NSSM)

## Documentation & Runbooks
- [ ] `docs/RELEASE_GATE_VERIFICATION.md` reviewed and updated
- [ ] Pilot runbook and KPI capture template available (`docs/PILOT_SIMULATION_TEST_PLAN.md`, `docs/PILOT_KPI_TEMPLATE.csv`)

## Post-release
- [ ] Tag release, push artifacts, create release notes
- [ ] Schedule quiet soak and KPI capture (24-72 hours)

Tips: keep the pilot noise low during soak; disable the simulator for quieter baselines.
