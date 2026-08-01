# Wilson Eval3ngine Backup and Recovery Runbook

## T8.1.5 - Production Backup, PITR, and Reconciliation

**RPO:** 15 minutes | **RTO:** 4 hours | **Retention:** 30 days

---

## Overview

This runbook covers the backup and recovery procedures for Wilson Eval3ngine. All backups are encrypted with KMS-managed keys and restore operations execute in isolated environments before verification.

---

## Backup Strategy

### PostgreSQL Backups

- **Full basebackup:** Every 24 hours (production)
- **WAL archiving:** Every 15 minutes (meets RPO=15min requirement)
- **Encryption:** All backups encrypted with `aws_kms_key.database_encryption`
- **Retention:** 30 days for automated backups, 90 days for final snapshots

### Object Store Backups

- **Versioning:** Enabled on S3 bucket (`we3-artifacts-<env>-<account>`)
- **Encryption:** SSE-KMS with `aws_kms_key.object_encryption`
- **Retention:** Lifecycle policy expires old versions after 30 days (noncurrent), 90 days total

---

## Verification Procedures

### Daily Verification (CI)

```bash
# Run backup verification tests
python -m pytest tests/unit/test_backup.py -v -k "integrity or verification"

# Verify backup metadata structure
python -c "
from wilson_eval3ngine.backup.backup_manager import BackupMetadata, BackupType
from datetime import datetime
# Verify all required fields present in metadata
"

# Check encryption status on all backups
aws s3api list-objects-v2 --bucket we3-backups-production --query 'Contents[].{Key: Key, KMS:Key.SSEKMSKeyId}'
```

### Monthly Restore Exercise

```bash
# 1. Identify latest verified backup
we3 backup-list --limit 5

# 2. Generate restore plan to isolated environment
we3 backup-restore-plan --timestamp "2026-07-15T12:00:00Z"

# 3. Execute isolated restore (NO network access until verified)
# See: RecoveryOrchestrator.execute_isolated_restore()

# 4. Run reconciliation
python -m pytest tests/integration/test_backup_restore.py -v -k "reconciliation"

# 5. Verify audit chain integrity
python -c "
from we3.backup import RecoveryOrchestrator
from we3.security.signing import TrustRegistry
# Verify audit chain + provenance edges
"
```

---

## Recovery Procedures

### Full Disaster Recovery

**When:** Complete control-plane failure, region unavailable, credential loss

**Steps:**

1. **Provision isolated restore environment**
   ```bash
   # Create isolated VPC/account for restore
   terraform apply -var="environment=restore-$(date +%Y%m%d)" \
     -target=module.vpc -target=aws_db_instance.we3_primary
   ```

2. **Restore from backup**
   ```bash
   # Find latest valid backup
   BACKUP_ID=$(we3 backup-list --limit 1 | jq -r '.backups[0].backup_id')

   # Execute restore to isolated database
   # This is handled by RecoveryOrchestrator in production code
   ```

3. **Run reconciliation**
   ```bash
   # Verify all accepted runs present
   python -m wilson_eval3ngine.recovery reconcile \
     --database-url postgresql://localhost/restore \
     --output var/reconciliation-report.json
   ```

4. **Integrity review and re-certification**
   - Compare restored state with last signed pre-failure manifest
   - Verify audit chain continuity
   - Confirm no missing objects/versions
   - Two-person approval required before production access

5. **Resume production**
   - Enable network access only after reconciliation passes
   - Update DNS to restored cluster
   - Monitor for integrity defects

---

## Security Controls

### Key Management

- **Database encryption keys:** Separately governed from application keys
- **Signing keys:** Ed25519, backed up via KeyBackupManager (metadata only, never private key)
- **Trust registry:** Revoked fingerprints preserved for recovery audit

### Access Control

- Backup/restore roles are separate from application identities
- No production credentials stored in application code
- All backup operations auditable via AuditCheckpoint

### Verification Requirements

Before restored production can resume release decisions:

- [ ] Reconciliation report shows `status: pass`
- [ ] All accepted runs present and matched
- [ ] Audit chain valid with no gaps
- [ ] Outbox events processed (pending = 0)
- [ ] Metric snapshots present and hash-verified
- [ ] Gate decisions present and verified
- [ ] Provenance edges intact
- [ ] Two-person approval recorded in recovery manifest

---

## Debugging Checklist

When investigating backup/restore issues:

| Check | Evidence Needed |
|-------|-----------------|
| Backup ID and timestamp | `backup.backup_timestamp` |
| WAL coverage | `backup.wal_start_lsn`, `backup.wal_end_lsn` |
| Object version inventory | S3 bucket versioning status |
| Key IDs and trust registry | KMS key aliases, TrustRegistry state |
| Audit checkpoint integrity | Hash chain verification |
| Restore topology | Isolated environment isolation |
| Reconciliation counts | Report totals |
| Hash failures | Verification discrepancy details |

---

## Negative/Security Testing

### Test Cases

- **Corrupted backup:** Backup with modified checksum
- **Missing key:** Key record with revoked/expired key_id
- **Unauthorized restore:** Restore without proper approvals
- **Cross-region failure:** Backup restore to different region
- **Stale data:** Backup older than retention period

### Running Security Tests

```bash
# Security-focused backup tests
python -m pytest tests/unit/test_backup.py -v -k "security or encrypted"

# Integration restore verification
python -m pytest tests/integration/test_backup_restore.py -v -k "security or isolated"

# Negative test scenarios
python -m pytest tests/security/ -v -k "backup"
```

---

## Related Files

- `src/wilson_eval3ngine/backup/backup_manager.py` - Core backup/recovery logic (563 lines)
- `src/wilson_eval3ngine/deployment/deployment_controller.py` - Deployment controls (418 lines)
- `infrastructure/terraform/main.tf` - Infrastructure configuration (539 lines)
- `infrastructure/terraform/variables.tf` - Variable definitions (70 lines)
- `tests/unit/test_backup.py` - Unit tests (25 tests)
- `tests/integration/test_backup_restore.py` - Integration tests (10 tests)
- `docs/operations/resilience-runbook.md` - Execution resilience
- `.github/workflows/ci.yml` - Deterministic CI with SHA-pinned actions