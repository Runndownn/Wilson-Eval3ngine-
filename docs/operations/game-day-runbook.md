# Wilson Eval3ngine Game-Day Runbook

## Purpose and current maturity

The game-day module is a **controlled scenario and incident-lifecycle simulator**. It provides a common failure taxonomy, authorization/safety-observer checks, an incident timeline, synthetic timing/decision metrics, findings, abort criteria, and a repeatable report shape that can be used to rehearse how WE3 should detect, contain, preserve evidence, restore, reconcile, and re-certify after failures.

It is important to understand that the current `GameDayOrchestrator` does **not** itself stop a real PostgreSQL server, corrupt a real object store, partition a network, disable an IdP, or exercise the newly implemented physical backup/PITR path. Its current phase transitions and timing values are simulated in Python. Therefore a successful game-day report demonstrates orchestration/reporting behavior for the scenario model; it is not runtime evidence that the named infrastructure fault was actually injected or recovered from.

For a real PostgreSQL encrypted-backup/PITR exercise, use the dedicated recovery workflow described in [Backup and Recovery Runbook](backup-recovery-runbook.md). A future target-environment game day can compose those real exercises with the scenario/reporting model here.

## What the source currently defines

`src/wilson_eval3ngine/testing/game_day.py` defines **25 scenarios across 14 fault categories**:

| Category | Scenario IDs | What the scenario model represents |
|---|---|---|
| Common flow | `gd_common_001` | A no-fault baseline. |
| Rare critical | `gd_critical_001`–`002` | Database restart and object-store unavailability. |
| Hostile input | `gd_hostile_001`–`002` | Prompt injection and report XSS attempts. |
| Partial failure | `gd_partial_001`–`002` | Outbox-consumer outage/duplicate delivery and partial evidence upload. |
| Concurrency | `gd_concurrent_001`–`002` | Stale leases and duplicate lease claims. |
| Replay | `gd_replay_001` | Idempotency replay. |
| Timeout/retry | `gd_timeout_001`–`002` | Provider/network timeout and retry-bound behavior. |
| Network partition | `gd_network_001` | PostgreSQL/object-storage partition scenario. |
| Malformed data | `gd_malformed_001`–`002` | Malformed run state and invalid audit hash. |
| Large payload | `gd_large_001` | Memory/backpressure scenario. |
| Version skew | `gd_skew_001`–`002` | Worker/event-schema and grader-version skew. |
| Dependency outage | `gd_deps_001`–`002` | IdP and provider outage. |
| Operator error | `gd_operator_001`–`002` | Plausible wrong action and unauthorized override. |
| Security compromise | `gd_security_001`–`003` | Signing-key compromise, audit tampering, and egress-control violation. |

This table describes **scenario definitions**, not proof that all 25 underlying failure modes have been reproduced against production-like infrastructure.

## Incident lifecycle represented by each scenario

A scenario proceeds through the same conceptual phases:

1. **Preparation** — identify the scenario and ensure authorization/safety conditions exist.
2. **Detection** — record that the fault was observed.
3. **Triage** — assign incident-response authority.
4. **Containment** — record containment/degradation actions.
5. **Evidence preservation** — retain evidence references and integrity context.
6. **Restore/repair** — represent service repair/recovery.
7. **Reconciliation** — represent state/integrity verification.
8. **Re-certification** — determine whether evidence gaps require a new certification decision.
9. **Closure** — finish the exercise and preserve findings/timeline.

This common lifecycle is valuable even when the fault itself is simulated. It gives incident and platform teams one vocabulary for asking whether a real exercise detected the event, who became responsible, what evidence was preserved, how recovery was demonstrated, and what release authority should exist afterward.

## Authorization and safety controls

The orchestrator requires an authorization token whose current source-level validation is the prefix `gd_auth_`, and scenario execution requires the safety-observer flag to be set. These checks are **simulation controls**, not production authorization. A real game day must still use written change authorization, named incident authority, a defined blast radius, rollback/abort procedures, and an independent observer according to the organization's operating process.

A useful authorized test token for a disposable exercise is:

```text
gd_auth_staging_20260822_operator
```

Do not interpret acceptance of that string by the simulator as proof that the requester was authenticated or authorized by a real identity system.

## Current CLI

The current CLI exposes one `game-day` command with a required `--context`, a required `--authorization`, and an output directory.

To print the failure matrix without executing the scenario loop:

```bash
we3 game-day \
  --context matrix \
  --authorization gd_auth_documentation_matrix
```

The CLI checks `context == "matrix"` before validating the token, but Typer still requires the option syntactically. The value above is illustrative only.

To execute the current full simulated failure matrix:

```bash
we3 game-day \
  --context run \
  --authorization gd_auth_staging_20260822_operator \
  --output var/game_day
```

The report is written to:

```text
var/game_day/game_day_result.json
```

The current CLI does **not** expose the previously documented `we3 game-day run`, `run-scenario`, `--with-load`, or `--concurrent-users` interfaces. Those examples have been removed because documentation should describe executable commands rather than intended future interfaces.

## Understanding the generated report

A `GameDayReport` contains:

- `exercise_id` and execution timestamp;
- the scenario IDs executed;
- the ordered timeline events produced by the phase model;
- aggregate `GameDayMetrics`;
- findings created by the simulator;
- whether the exercise was aborted and the abort reason.

The metric model includes mean-time-to-detect style timing, acknowledgement, containment, recovery, reconciliation, RPO/RTO fields, SLO impact, integrity verification, decision correctness, and communication timing. In the current simulator many of these values are generated deterministically from scenario seed/state rather than observed from external systems. They are useful for testing report logic and rehearsal workflows, but they must not be cited as measured service-level results.

That distinction is especially important for RPO and RTO. The recovery subsystem now records an actual elapsed restore duration during its disposable PostgreSQL exercise. A synthetic `GameDayMetrics.rto_hours` value and a real `RestoreExecutionResult.duration_seconds` are different classes of evidence and should never be merged without preserving their provenance.

## Basic report inspection

You can validate the report structure without pretending its simulated metrics are production measurements:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path("var/game_day/game_day_result.json")
report = json.loads(path.read_text(encoding="utf-8"))

assert report["exercise_id"]
assert isinstance(report["scenarios_executed"], list)
assert len(report["scenarios_executed"]) == 25
assert isinstance(report["timeline"], list)
assert isinstance(report["metrics"], dict)
assert isinstance(report["findings"], list)
assert isinstance(report["aborted"], bool)

print(f"exercise: {report['exercise_id']}")
print(f"scenarios: {len(report['scenarios_executed'])}")
print(f"timeline events: {len(report['timeline'])}")
print(f"aborted: {report['aborted']}")
PY
```

This check answers “did the simulator produce the expected report contract?” It does not answer “did the actual organization recover from all 25 faults?”

## Abort criteria

Individual scenario definitions include abort criteria such as evidence loss, integrity violations, unsafe/unhandled schema conditions, unauthorized actions, or security-control failure. `check_abort_criteria()` evaluates those criteria against the observed-state dictionary supplied to the simulator.

In a real game day, abort criteria should map to concrete monitoring signals and an accountable person who can stop the exercise. A string such as `data_loss_detected` in source is a useful contract only after the staging/runtime harness defines how that fact is measured.

## Evidence model

A useful real game day should preserve three layers of evidence separately:

### 1. Scenario/orchestration evidence

The report from `GameDayOrchestrator` shows which scenario model was exercised, the simulated lifecycle transitions, findings, and the common report contract.

### 2. Component runtime evidence

Real component exercises should retain native results. For example, the PostgreSQL recovery exercise should retain encrypted-backup manifest identities, WAL sequence, restore log hash, measured duration, signed recovery baseline, and reconciliation result. Provider, IdP, scheduler, object-store, and network exercises should likewise keep the evidence produced by those systems.

### 3. Human/operational evidence

A governed exercise also needs written authorization, participant roles, timeline communications, decisions, abort/rollback actions, approvals, and follow-up owners. Source code cannot manufacture those organizational facts.

Keeping the three layers separate prevents a simulated timeline event from being mistaken for proof that an infrastructure control executed.

## Composing the real PostgreSQL recovery exercise

For database-recovery game days, treat the `we3-backup` workflow as the component exercise and the game-day report as orchestration context. A practical staging sequence is:

1. authorize the exercise and name the safety observer;
2. capture/verify the pre-exercise recovery baseline;
3. verify that encrypted full-backup and real WAL coverage exist;
4. run the chosen database failure scenario in the authorized staging environment;
5. execute `we3-backup restore` to an isolated loopback recovery instance;
6. retain `restore_execution.json`, PostgreSQL restore log, plan, backup/WAL identities, and reconciliation output;
7. record those evidence references in the game-day/incident record;
8. perform the required re-certification and human approval before restoring release authority.

The exact commands and trust/KMS configuration are in [Backup and Recovery Runbook](backup-recovery-runbook.md). Do not copy production KMS credentials, database passwords, private storage paths, or raw sensitive logs into a public game-day report.

## RPO/RTO interpretation

The scenario model contains RPO/RTO fields and several scenarios describe target recovery windows. Treat those as **objectives/rehearsal values** until a target-like exercise measures them.

For a real database exercise, calculate RPO from the actual protected recovery point/WAL coverage relative to the failure point and calculate RTO from observed incident/recovery timestamps. Retain the source backup ID, ending LSN, required WAL sequence, target timestamp/LSN, restore start/completion times, and reconciliation result so another reviewer can reconstruct the measurement.

A configured target such as “15 minutes” is a policy requirement. A measured value such as “this restore completed in 83 seconds and reached LSN X” is evidence. The first should never be presented as though it were the second.

## Security scenario interpretation

### Signing-key compromise

The scenario model can represent a compromised-key incident. The real recovery implementation provides a concrete negative test: a forged/untrusted backup-manifest signature fails verification. A target-environment exercise should additionally prove revocation/rotation through the actual key authority and trust distribution process.

### Audit tampering

Recovery reconciliation recomputes the canonical project audit chain and compares terminal roots with a signed baseline. The unit suite deliberately modifies an audit hash and requires reconciliation to fail. A real game day can build on that behavior using a disposable database rather than corrupting production evidence.

### Egress violations

The game-day model names egress-control failure, but it does not enforce network policy itself. Real validation belongs to the deployment firewall/container/network layer and should produce bounded evidence showing approved destinations were reachable and prohibited destinations were not.

## What should block a real exercise from being called successful

A real staging or production-readiness game day should not be called successful merely because `game_day_result.json` exists. At minimum, fail the exercise when a required real component check was not executed, expected evidence is missing, integrity/reconciliation failed, an abort criterion fired without the prescribed response, or an accountable approver cannot establish what was restored and why release authority should resume.

Findings should have an owner and retest requirement proportional to their certification impact. A critical recovery or integrity finding should remain visible until the failing component has been corrected and the relevant scenario has been executed again with retained evidence.

## Current implementation boundaries

The current simulator does not yet:

- invoke the real `we3-backup` restore automatically;
- manipulate a real IdP, provider, object store, network partition, or scheduler process;
- authenticate game-day authorization tokens against an identity/approval service;
- expose a supported single-scenario CLI command;
- expose the previously documented load/concurrency flags;
- convert component evidence automatically into game-day evidence references.

Those are integration opportunities, not facts that should be hidden by runbook language. Keeping them visible makes it easier to decide whether a future change belongs in scenario orchestration, a component-specific runtime harness, or the organization's operating procedure.

## Related implementation and runbooks

- `src/wilson_eval3ngine/testing/game_day.py` — scenario taxonomy, lifecycle simulator, metrics/findings/report model.
- `src/wilson_eval3ngine/cli.py` — current `we3 game-day --context ...` interface.
- `src/wilson_eval3ngine/backup/` — real encrypted PostgreSQL backup/PITR component path.
- [Backup/Recovery](backup-recovery-runbook.md) — real PostgreSQL recovery mechanics and evidence.
- [SEV Incidents](sev-incidents.md) — incident response procedures.
- [Performance Qualification](performance-qualification.md) — load/performance qualification.
- [Certification Runbook](certification-runbook.md) — certification/re-certification process.
