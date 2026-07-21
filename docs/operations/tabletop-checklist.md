# Quarterly Tabletop Exercise Checklist

## SEV Tabletop Validation (TODO 53)

This checklist ensures operational runbooks remain valid and effective.

## Quarterly Requirements

- [ ] All SEV-1 scenarios covered in runbook tested
- [ ] All SEV-2 scenarios covered in runbook tested  
- [ ] Evidence preservation verified for each scenario
- [ ] Alert links to correct runbook version verified
- [ ] Runbook commands tested against current deployment
- [ ] Role assignments validated with current team structure
- [ ] Communication templates reviewed and updated

## Scenario Testing

### Provider Outage
- [ ] Can identify outage from alerts
- [ ] Evidence preserved during outage
- [ ] Mock provider fallback documented
- [ ] Recovery time measured and within SLA

### Evidence Loss/Curruption
- [ ] Evidence freeze procedure verified
- [ ] Backup restoration tested
- [ ] Audit chain verification works
- [ ] Recovery without data loss validated

### Queue Collapse
- [ ] Queue depth alerts trigger correctly
- [ ] Worker scaling procedure verified
- [ ] Stuck job detection works
- [ ] Queue drains clean after recovery

### Model Identity Drift
- [ ] Drift detection alerts verified
- [ ] Affected runs tagged correctly
- [ ] Grader version rollback tested
- [ ] Evidence integrity maintained

## Runbook Validation

### Commands Current
- [ ] All CLI commands tested against current version
- [ ] Database queries verified against current schema
- [ ] Environment variables documented
- [ ] Version-specific instructions validated

### Alert Links
- [ ] All alert runbook URLs return 200
- [ ] Alert fingerprints deduplicate correctly
- [ ] Recovery conditions documented and tested

## Evidence Preservation

- [ ] SHA-256 hashes captured before any destructive action
- [ ] Audit events logged for all state changes
- [ ] Backup verification procedure tested
- [ ] Chain of custody documentation complete

## Team Readiness

- [ ] Incident commander identified and trained
- [ ] Evidence lead trained on preservation procedures
- [ ] Operations lead familiar with recovery commands
- [ ] Communications lead has access to status channels

## Documentation Updates

After each tabletop exercise:
1. Document any deviations from runbook
2. Update runbook with corrections
3. Record evidence verification results
4. Note any alerts that didn't fire correctly
5. Verify runbook version in alert rules matches

## Next Review Date

Set for: [3 months from implementation date]