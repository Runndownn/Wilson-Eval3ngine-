.PHONY: install test coverage validate demo critical verify schemas openapi api clean

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest -q

coverage:
	python -m coverage run -m pytest -q
	python -m coverage report

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
