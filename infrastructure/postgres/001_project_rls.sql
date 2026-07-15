-- Production hardening reference. Apply only after the application sets
-- SET LOCAL we3.project_id = '<verified-project-id>' in every transaction.

ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE classifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE metric_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE gate_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY experiments_project_isolation ON experiments
USING (project_id = current_setting('we3.project_id', true))
WITH CHECK (project_id = current_setting('we3.project_id', true));

CREATE POLICY runs_project_isolation ON runs
USING (project_id = current_setting('we3.project_id', true))
WITH CHECK (project_id = current_setting('we3.project_id', true));

CREATE POLICY classifications_project_isolation ON classifications
USING (project_id = current_setting('we3.project_id', true))
WITH CHECK (project_id = current_setting('we3.project_id', true));

CREATE POLICY metric_snapshots_project_isolation ON metric_snapshots
USING (project_id = current_setting('we3.project_id', true))
WITH CHECK (project_id = current_setting('we3.project_id', true));

CREATE POLICY gate_decisions_project_isolation ON gate_decisions
USING (project_id = current_setting('we3.project_id', true))
WITH CHECK (project_id = current_setting('we3.project_id', true));

CREATE POLICY audit_events_project_isolation ON audit_events
USING (project_id = current_setting('we3.project_id', true))
WITH CHECK (project_id = current_setting('we3.project_id', true));

CREATE POLICY jobs_project_isolation ON jobs
USING (project_id = current_setting('we3.project_id', true))
WITH CHECK (project_id = current_setting('we3.project_id', true));
