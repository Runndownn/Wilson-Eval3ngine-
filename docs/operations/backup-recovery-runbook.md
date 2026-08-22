# Wilson Eval3ngine Backup and Recovery Runbook

## Current assurance status

**This is a recovery design/runbook, not evidence that production backup, encryption, WAL archival, PITR, or restore execution is complete.**

The current source contains backup/recovery data models, PostgreSQL command scaffolding, reconciliation queries, recovery-manifest concepts, Terraform/deployment material, tests, and CLI entry points. A source audit found several execution paths that are still provisional and must not be represented as production protection:

- `BackupManager.create_full_backup()` invokes `pg_basebackup`, but the current implementation does **not** encrypt the resulting backup payload even though metadata is populated with `encrypted=True` and a key ID.
- the recorded backup checksum is currently derived from the backup-directory path string rather than the backup file contents, so it is not a content-integrity checksum;
- `create_wal_archive()` currently produces metadata rather than writing a real WAL archive;
- `generate_restore_plan()` currently synthesizes placeholder WAL segment names instead of proving a continuous WAL chain to the requested recovery point;
- `verify_backup_integrity()` contains an unimplemented signature-verification branch;
- `RecoveryOrchestrator.execute_isolated_restore()` currently logs the intended restore and returns success without executing `pg_restore`/PITR;
- backup metadata is kept in the manager's in-process `_backups` mapping, so separately invoked CLI processes do not yet provide a durable backup catalogue through this class;
- existing integration tests exercise orchestration/scaffolding with simulated backup records; they are not evidence that an actual PostgreSQL base backup has been encrypted, restored, replayed to a point in time, reconciled, and re-certified.

Until those gaps are closed and an authorized environment produces retained runtime evidence, the values below are **targets**, not achieved SLOs:

- target RPO: 15 minutes;
- target RTO: 4 hours;
- target retention: 30 days;
- target production control: KMS-backed encryption and separately governed signing/trust verification.

## What an operator may use today

The code is useful for reviewing the intended recovery contract, exercising metadata/reconciliation logic in controlled development, and building the deployment-specific implementation. Do **not** use the current `backup-create`, `backup-verify`, or restore-plan surface as the sole protection for production evaluation evidence.

If production protection is required now, use the database/object-store platform's independently managed backup, encryption, retention, WAL/PITR, and restore capabilities, and retain their native evidence. WE3 certification should reference those executed controls rather than inferring protection from this scaffold.

## Required completion gates

The backup/recovery capability should be promoted from provisional only when all of the following are implemented and demonstrated against the target deployment:

1. **Real payload encryption**
   - encrypt backup data with the approved external KMS/envelope-encryption mechanism;
   - record the actual key/version used without storing key material in the repository;
   - prove decryptability in an isolated restore exercise.

2. **Content integrity**
   - compute a deterministic manifest over the backup objects/bytes, not the local directory pathname;
   - sign the manifest with an approved recovery/signing identity;
   - fail verification when a backup object, manifest, or signature is modified.

3. **Durable backup catalogue**
   - persist backup metadata outside process memory;
   - make `backup-list`, verify, restore planning, retention/legal hold, and audit history operate over that durable catalogue;
   - bind records to storage object versions and database/WAL identity.

4. **Real WAL/PITR coverage**
   - capture actual WAL segment/range/timeline information;
   - prove continuity from the selected base backup to the requested target time;
   - reject a restore plan when coverage is incomplete rather than synthesizing segment names.

5. **Real isolated restore**
   - provision or select an isolated target;
   - execute the database restore and WAL replay to the requested recovery point;
   - keep the restored environment inaccessible to normal production clients until verification succeeds.

6. **Reconciliation and chain verification**
   - verify the audit chain cryptographically, not merely that event-hash fields are non-empty;
   - verify expected run/classification/metric/gate/provenance populations and object versions;
   - reconcile pending outbox/event state using the actual database dialect/schema;
   - emit a signed reconciliation artifact.

7. **Approval and re-certification**
   - require the configured independent approvals;
   - retain restore evidence, discrepancies, signatures, timing, and environment identity;
   - re-run the required release/certification checks before restored production resumes release authority.

## Intended production procedure

The following sequence documents the intended controlled procedure after the completion gates above exist.

### 1. Identify a verified base backup

Use the deployment's durable backup catalogue and native storage/database evidence to choose a base backup created before the recovery target. Do not rely on an in-memory manager instance or a screenshot of `backup-list`.

### 2. Prove WAL coverage

Establish the exact timeline and WAL range needed to reach the target timestamp. Missing or ambiguous coverage is a hard stop.

### 3. Provision an isolated target

The restore target must be separated from normal production traffic and identities. Record infrastructure identity, network policy, database version, storage location, and the source backup/object versions before execution.

### 4. Restore and replay

Execute the real database restore and WAL replay. Capture command/tool versions, timestamps, exit status, logs, object/version identifiers, and resulting database recovery point.

### 5. Reconcile

Verify at minimum:

- accepted run population;
- current classification population and supersession state;
- metric snapshots;
- gate decisions;
- audit-chain continuity;
- event/outbox state;
- provenance edges and referenced evidence objects;
- hashes/signatures and storage object versions.

A count-only match is insufficient if integrity/lineage checks fail.

### 6. Review discrepancies

Any missing run, broken chain, missing object, unresolved event, signature failure, or unexplained count difference keeps the environment isolated and triggers investigation/re-certification.

### 7. Approve return to service

Only designated independent approvers may authorize release authority after the restore/reconciliation evidence is complete. Network access and DNS changes should occur after this approval, not before.

## Verification evidence to retain

For each real exercise retain:

| Evidence | Why it matters |
|---|---|
| Source database/storage identity | Proves what was protected. |
| Base-backup ID, timestamp, object versions | Establishes recovery input. |
| Actual encrypted-object/KMS metadata | Proves encryption control rather than a Boolean field. |
| Content manifest and signature | Detects tampering/corruption. |
| WAL timeline/range/segments | Proves PITR coverage. |
| Isolated target identity/network policy | Proves containment. |
| Restore/replay logs and exit status | Proves execution occurred. |
| Recovery-point timestamp/LSN | Proves where the database landed. |
| Reconciliation report | Shows population/integrity findings. |
| Independent approvals | Establishes accountable return-to-service authority. |
| Duration measurements | Supports actual RPO/RTO claims. |

## Development tests versus runtime assurance

The current tests are useful regression checks for models, planning logic, security expectations, and reconciliation code. They do not turn a mocked backup record into an encrypted backup or a logging stub into a restore.

A CI job that runs backup unit/integration tests is therefore **source-level evidence**. A production recovery claim requires an executed backup/restore exercise against an authorized disposable/isolated database and storage environment, with the evidence above retained.

## Security rules

- Never place production database passwords, KMS material, object-store credentials, private endpoints, or restore topology in this public repository.
- Do not mark a backup encrypted solely because a key ID was supplied; verify the stored payload and KMS metadata.
- Do not treat a path-name hash as content integrity.
- Do not treat “restore plan generated” as “restore executed.”
- Do not reconnect a restored environment until integrity/reconciliation and approval gates pass.
- Keep backup/restore identities separate from ordinary application identities and apply least privilege.

## Related files

- `src/wilson_eval3ngine/backup/backup_manager.py` — current backup/recovery scaffold and reconciliation code.
- `src/wilson_eval3ngine/cli.py` — backup command entry points.
- `tests/unit/test_backup.py` — source-level backup/recovery tests.
- `tests/integration/test_backup_restore.py` — orchestration/scaffold integration tests using simulated state.
- `src/wilson_eval3ngine/persistence/migrations/006_backup_and_recovery.py` — persistence-related recovery schema work.
- `docs/operations/game-day-runbook.md` — broader failure-exercise procedure.
- `docs/STATUS.md` — authoritative current capability/assurance status.

## Promotion criterion

Change the status of backup/PITR/recovery to **implemented/runtime-assured** only after the real encryption, content integrity, durable catalogue, WAL continuity, isolated restore, reconciliation, and approval paths are implemented and an authorized target environment has produced retained passing evidence. Until then, preserve the word **provisional** wherever the feature is described publicly.
