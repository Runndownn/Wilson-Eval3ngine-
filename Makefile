.PHONY: install install-security lint docs-check test coverage security-check security-unit validate demo critical verify schemas openapi api clean backup backup-create backup-list backup-verify backup-baseline backup-restore-plan backup-restore

install:
	python -m pip install -e ".[dev]"

install-security:
	python -m pip install -e ".[dev,security]"

lint:
	python -m compileall -q src tests scripts
	python scripts/validate_documentation_assets.py
	node --check gui/static/enhanced.js
	node --check gui/static/ux4.js
	node --check gui/static/ux5.js
	node --check gui/static/ux6.js

docs-check:
	python scripts/validate_documentation_assets.py

test:
	python -m pytest -q

coverage:
	python -m coverage run -m pytest -q
	python -m coverage report

security-unit:
	python -m pytest -q tests/unit/test_oidc_auth.py tests/unit/test_security_enhancements.py tests/unit/test_production_middleware.py tests/unit/test_security_hardening_20260822.py tests/unit/test_api_authorization_contract.py tests/unit/test_api_security_composition.py

security-check:
	python -m compileall -q src tests scripts
	python -m bandit -q -r src/wilson_eval3ngine
	python -m pip_audit --local
	we3 scan-ci --source . --output var/security/supply_chain_report.json
	$(MAKE) security-unit

validate:
	we3 validate examples/experiments/foundation.yaml

demo:
	we3 run examples/experiments/foundation.yaml --output var/foundation --database-url sqlite:///./var/we3.db --artifact-root var/artifacts

critical:
	we3 run examples/experiments/critical_failure.yaml --output var/critical-failure --database-url sqlite:///./var/we3-critical.db --artifact-root var/artifacts-critical

verify:
	we3 verify-dossier var/foundation/release_dossier.json

schemas:
	we3 export-schemas --output contracts/schemas

openapi:
	WE3_DATABASE_URL=sqlite:///./var/openapi.db WE3_ARTIFACT_ROOT=./var/openapi-artifacts python scripts/export_openapi.py --output contracts/openapi.v1.json

api:
	WE3_DATABASE_URL=sqlite:///./var/api.db WE3_ARTIFACT_ROOT=./var/api-artifacts we3 serve --host 127.0.0.1 --port 8000

clean:
	rm -rf .pytest_cache .coverage htmlcov var build dist *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# Recovery operations intentionally use the dedicated PostgreSQL/KMS-aware CLI.
# Install optional dependencies first with: python -m pip install -e ".[dev,backup]"
backup:
	we3-backup --help

backup-create:
	we3-backup create --key-id "$(KEY_ID)" --signing-key "$(SIGNING_KEY)"

backup-list:
	we3-backup list --limit 20

backup-verify:
	we3-backup verify "$(BACKUP_ID)"

backup-baseline:
	we3-backup capture-baseline --output "$(BASELINE)" --signing-key "$(SIGNING_KEY)"

backup-restore-plan:
	we3-backup plan --timestamp "$(TIMESTAMP)" --baseline "$(BASELINE)" $(if $(TARGET_LSN),--target-lsn "$(TARGET_LSN)",)

backup-restore:
	we3-backup restore --timestamp "$(TIMESTAMP)" --baseline "$(BASELINE)" --isolated-database-url "$(ISOLATED_DATABASE_URL)" --data-directory "$(RESTORE_DATA_DIR)" $(if $(TARGET_LSN),--target-lsn "$(TARGET_LSN)",)
