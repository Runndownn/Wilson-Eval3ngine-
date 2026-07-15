from sqlalchemy import update

from wilson_eval3ngine.persistence.audit import AuditLedger
from wilson_eval3ngine.persistence.database import AuditEventRow, Database, Repository


def test_audit_chain_detects_tampering(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'audit.db'}")
    db.initialize()
    Repository(db).ensure_project("p")
    ledger = AuditLedger(db)
    ledger.append(
        project_id="p",
        event_type="a",
        aggregate_type="experiment",
        aggregate_id="e",
        actor_id="tester",
        payload={"x": 1},
    )
    ledger.append(
        project_id="p",
        event_type="b",
        aggregate_type="experiment",
        aggregate_id="e",
        actor_id="tester",
        payload={"x": 2},
    )
    assert ledger.verify("p")

    with db.session() as session, session.begin():
        row = session.query(AuditEventRow).order_by(AuditEventRow.created_at).first()
        row.payload_json = {"x": 999}

    assert not ledger.verify("p")
