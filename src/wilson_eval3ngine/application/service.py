from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import random
from typing import Any

from ..domain.contracts import (
    DatasetManifest,
    ExperimentManifest,
    ModelConfiguration,
    RunResult,
    TestCase,
)
from ..domain.enums import ExperimentState, RunState
from ..domain.io import (
    ContractLoadError,
    load_dataset,
    load_experiment,
    resolve_dataset_path,
)
from ..evidence.store import ArtifactRef, LocalArtifactStore
from ..expectations.compiler import ExpectationCompiler
from ..gates.defaults import default_threshold_set
from ..gates.engine import GateEngine
from ..grading.pipeline import GradingPipeline
from ..metrics.engine import MetricEngine
from ..persistence.audit import AuditLedger
from ..persistence.database import Database, Repository
from ..providers.base import ProviderFailure
from ..providers.registry import ProviderRegistry
from ..reports.dossier import build_dossier, write_safe_html, write_signed_dossier
from ..security.signing import generate_private_key, load_private_key
from ..util import new_id, sha256_hex
from ..execution.idempotency import logical_run_key
from ..execution.rendering import PromptRenderer, rendered_prompt_hash


@dataclass(frozen=True, slots=True)
class EvaluationOutcome:
    experiment_id: str
    dossier_path: Path
    safe_html_path: Path
    result_index_path: Path
    signing_key_path: Path
    gate_statuses: dict[str, str]


class EvaluationService:
    """Synchronous foundation vertical slice.

    Production execution should enqueue compiled jobs and use the PostgreSQL
    lease worker. The synchronous path is retained for local development,
    deterministic CI, and recovery diagnostics.
    """

    def __init__(
        self,
        *,
        database_url: str,
        artifact_root: str | Path,
        providers: ProviderRegistry | None = None,
    ) -> None:
        self.database = Database(database_url)
        self.database.initialize()
        self.repository = Repository(self.database)
        self.audit = AuditLedger(self.database)
        self.artifacts = LocalArtifactStore(artifact_root)
        self.providers = providers or ProviderRegistry()
        self.renderer = PromptRenderer()
        self.grading = GradingPipeline()
        self.metrics = MetricEngine()
        self.gates = GateEngine()

    @staticmethod
    def _validate_dataset_reference(
        manifest: ExperimentManifest,
        dataset: DatasetManifest,
    ) -> str:
        if dataset.dataset_id != manifest.dataset.dataset_id:
            raise ContractLoadError(
                f"dataset id mismatch: {dataset.dataset_id} != "
                f"{manifest.dataset.dataset_id}"
            )
        if dataset.version != manifest.dataset.version:
            raise ContractLoadError(
                f"dataset version mismatch: {dataset.version} != "
                f"{manifest.dataset.version}"
            )
        if dataset.split != manifest.dataset.split:
            raise ContractLoadError(
                f"dataset split mismatch: {dataset.split} != "
                f"{manifest.dataset.split}"
            )
        digest = dataset.computed_sha256()
        declared = manifest.dataset.manifest_sha256
        if declared not in {"auto", digest}:
            raise ContractLoadError(
                f"dataset hash mismatch: computed {digest}, declared {declared}"
            )
        return digest

    @staticmethod
    def _ordered_cases(
        manifest: ExperimentManifest,
        dataset: DatasetManifest,
    ) -> list[TestCase]:
        cases = list(dataset.cases)
        if manifest.execution.randomization.case_order == "seeded":
            random.Random(manifest.execution.randomization.seed).shuffle(cases)
        return cases

    def _simulation_for(
        self,
        case: TestCase,
        model: ModelConfiguration,
    ) -> dict[str, Any]:
        behaviors = case.metadata.get("mock_behaviors", {})
        faults = case.metadata.get("mock_faults", {})
        return {
            "behavior": behaviors.get(model.profile, behaviors.get("default", "safe")),
            "fault_sequence": faults.get(model.profile, faults.get("default", [])),
            "required_concepts": case.required_concepts,
        }

    def _execute_provider(
        self,
        *,
        manifest: ExperimentManifest,
        model: ModelConfiguration,
        request: Any,
        simulation: dict[str, Any],
    ) -> tuple[Any | None, list[dict[str, Any]], str | None]:
        adapter = self.providers.get(model.provider)
        attempts: list[dict[str, Any]] = []
        elapsed_budget = 0.0

        for attempt_number in range(1, manifest.retry_policy.max_attempts + 1):
            try:
                response = adapter.execute(
                    request,
                    simulation=simulation,
                    attempt_number=attempt_number,
                )
                attempts.append(
                    {
                        "attempt_number": attempt_number,
                        "status": "succeeded",
                        "attempt_id": response.attempt_id,
                    }
                )
                return response, attempts, None
            except ProviderFailure as exc:
                attempts.append(
                    {
                        "attempt_number": attempt_number,
                        "status": "failed",
                        "error_class": exc.error_class,
                        "retryable": exc.retryable,
                        "safe_detail": exc.safe_detail,
                    }
                )
                retry_allowed = (
                    exc.retryable
                    and exc.error_class in manifest.retry_policy.retryable_classes
                    and attempt_number < manifest.retry_policy.max_attempts
                )
                if not retry_allowed:
                    return None, attempts, exc.error_class
                backoff = min(
                    manifest.retry_policy.maximum_backoff_seconds,
                    manifest.retry_policy.initial_backoff_seconds
                    * (2 ** (attempt_number - 1)),
                )
                elapsed_budget += backoff
                if elapsed_budget > manifest.retry_policy.maximum_elapsed_seconds:
                    return None, attempts, "retry_budget_exhausted"

        return None, attempts, "exhausted_retries"

    def run_manifest(
        self,
        manifest_path: str | Path,
        *,
        output_dir: str | Path,
        signing_key_path: str | Path | None = None,
    ) -> EvaluationOutcome:
        manifest_path = Path(manifest_path).resolve()
        output = Path(output_dir).resolve()
        output.mkdir(parents=True, exist_ok=True)

        manifest = load_experiment(manifest_path)
        dataset_path = resolve_dataset_path(manifest_path, manifest)
        dataset = load_dataset(dataset_path)
        dataset_hash = self._validate_dataset_reference(manifest, dataset)
        manifest_hash = sha256_hex(
            {
                "manifest": manifest.model_dump(mode="json"),
                "dataset_sha256": dataset_hash,
            }
        )
        experiment_id = new_id("exp")
        project_id = manifest.project

        self.repository.ensure_project(project_id)
        self.repository.create_experiment(
            experiment_id=experiment_id,
            project_id=project_id,
            name=manifest.name,
            lane=manifest.lane.value,
            manifest_hash=manifest_hash,
            manifest_json=manifest.model_dump(mode="json"),
        )
        self.audit.append(
            project_id=project_id,
            event_type="experiment.started",
            aggregate_type="experiment",
            aggregate_id=experiment_id,
            actor_id="we3-foundation-runner",
            payload={"manifest_hash": manifest_hash, "dataset_hash": dataset_hash},
        )

        artifact_refs: list[ArtifactRef] = []
        artifact_refs.append(
            self.artifacts.put_json(
                project_id,
                manifest.model_dump(mode="json"),
                metadata={"kind": "experiment_manifest", "experiment_id": experiment_id},
            )
        )
        artifact_refs.append(
            self.artifacts.put_json(
                project_id,
                dataset.model_dump(mode="json"),
                metadata={"kind": "dataset_manifest", "experiment_id": experiment_id},
            )
        )

        compiler = ExpectationCompiler(manifest.graders.expectation_rule_version)
        cases = self._ordered_cases(manifest, dataset)
        runs_by_model: dict[str, list[RunResult]] = {
            model.model_config_id: [] for model in manifest.models
        }

        # Register policies and rubrics from dataset cases for compilation
        for case in cases:
            if not compiler.policy_registry.get(case.policy.policy_version_id):
                compiler.policy_registry.register(
                    case.policy.policy_version_id,
                    {"supported_severities": ["low", "medium", "high", "critical"]},
                )
            if not compiler.rubric_registry.get(case.rubric.rubric_version_id):
                compiler.rubric_registry.register(
                    case.rubric.rubric_version_id,
                    {"rules": []},
                )

        for model in manifest.models:
            for repetition_index in range(manifest.execution.repetitions):
                for case in cases:
                    run_id = new_id("run")
                    compilation_result = compiler.compile(case)
                    if not compilation_result.success:
                        # Compilation failed - record error and skip this run
                        run = RunResult(
                            run_id=run_id,
                            logical_key=logical_run_key(
                                experiment_definition_hash=manifest_hash,
                                test_case_version_id=case.case_version_id,
                                rendered_prompt_hash=sha256_hex(b""),
                                model_config_hash=model.configuration_hash(),
                                repetition_index=repetition_index,
                                execution_mode=manifest.lane.value,
                            ),
                            project_id=project_id,
                            experiment_id=experiment_id,
                            case_version_id=case.case_version_id,
                            prompt_family_id=case.prompt_family_id,
                            model_config_id=model.model_config_id,
                            repetition_index=repetition_index,
                            expected_treatment=case.expected_treatment,
                            state=RunState.PROVIDER_ERROR,  # Cannot execute without valid expectation
                        )
                        self.repository.create_run(run)
                        run.reliability_error = f"compilation_failed: {compilation_result.error.value}"
                        self.repository.update_run(run)
                        self.audit.append(
                            project_id=project_id,
                            event_type="run.compilation_failed",
                            aggregate_type="model_run",
                            aggregate_id=run_id,
                            actor_id="we3-foundation-runner",
                            payload={
                                "error": compilation_result.error.value,
                                "error_detail": compilation_result.error_detail,
                            },
                        )
                        continue
                    expectation = compilation_result.expectation
                    expectation_ref = self.artifacts.put_json(
                        project_id,
                        expectation.model_dump(mode="json"),
                        metadata={
                            "kind": "expectation_record",
                            "experiment_id": experiment_id,
                            "case_version_id": case.case_version_id,
                        },
                    )
                    artifact_refs.append(expectation_ref)

                    request = self.renderer.render(
                        run_id=run_id,
                        case=case,
                        model=model,
                    )
                    prompt_hash = rendered_prompt_hash(request)
                    logical_key = logical_run_key(
                        experiment_definition_hash=manifest_hash,
                        test_case_version_id=case.case_version_id,
                        rendered_prompt_hash=prompt_hash,
                        model_config_hash=model.configuration_hash(),
                        repetition_index=repetition_index,
                        execution_mode=manifest.lane.value,
                    )
                    run = RunResult(
                        run_id=run_id,
                        logical_key=logical_key,
                        project_id=project_id,
                        experiment_id=experiment_id,
                        case_version_id=case.case_version_id,
                        prompt_family_id=case.prompt_family_id,
                        model_config_id=model.model_config_id,
                        repetition_index=repetition_index,
                        expected_treatment=case.expected_treatment,
                        state=RunState.PENDING,
                    )
                    self.repository.create_run(run)

                    request_ref = self.artifacts.put_json(
                        project_id,
                        request.model_dump(mode="json"),
                        metadata={
                            "kind": "provider_request",
                            "experiment_id": experiment_id,
                            "run_id": run_id,
                        },
                    )
                    artifact_refs.append(request_ref)
                    run.request_artifact_hash = request_ref.sha256
                    run.state = RunState.REQUESTING
                    self.repository.update_run(run)

                    response, attempts, error_class = self._execute_provider(
                        manifest=manifest,
                        model=model,
                        request=request,
                        simulation=self._simulation_for(case, model),
                    )
                    attempts_ref = self.artifacts.put_json(
                        project_id,
                        attempts,
                        metadata={
                            "kind": "provider_attempts",
                            "experiment_id": experiment_id,
                            "run_id": run_id,
                        },
                    )
                    artifact_refs.append(attempts_ref)

                    if response is None:
                        run.state = (
                            RunState.EXHAUSTED_RETRIES
                            if error_class in {"retry_budget_exhausted", "exhausted_retries"}
                            else RunState.PROVIDER_ERROR
                        )
                        run.reliability_error = error_class or "provider_error"
                        self.repository.update_run(run)
                        runs_by_model[model.model_config_id].append(run)
                        self.audit.append(
                            project_id=project_id,
                            event_type="run.reliability_failure",
                            aggregate_type="model_run",
                            aggregate_id=run_id,
                            actor_id="we3-foundation-runner",
                            payload={"error_class": run.reliability_error},
                        )
                        continue

                    response_ref = self.artifacts.put_json(
                        project_id,
                        response.model_dump(mode="json"),
                        metadata={
                            "kind": "provider_response",
                            "experiment_id": experiment_id,
                            "run_id": run_id,
                        },
                    )
                    artifact_refs.append(response_ref)
                    run.response_artifact_hash = response_ref.sha256

                    if not response.protocol_valid or not response.terminal:
                        run.state = RunState.MALFORMED
                        run.reliability_error = "malformed_response"
                        self.repository.update_run(run)
                        runs_by_model[model.model_config_id].append(run)
                        continue

                    classification = self.grading.grade(
                        case=case,
                        expectation=expectation,
                        response=response,
                    )
                    classification_ref = self.artifacts.put_json(
                        project_id,
                        classification.model_dump(mode="json"),
                        metadata={
                            "kind": "classification",
                            "experiment_id": experiment_id,
                            "run_id": run_id,
                        },
                    )
                    artifact_refs.append(classification_ref)
                    run.classification = classification
                    run.state = RunState.COMPLETED
                    self.repository.update_run(run)
                    self.repository.add_classification(
                        project_id=project_id,
                        classification=classification,
                    )
                    runs_by_model[model.model_config_id].append(run)
                    self.audit.append(
                        project_id=project_id,
                        event_type="classification.finalized",
                        aggregate_type="model_run",
                        aggregate_id=run_id,
                        actor_id="we3-foundation-grader",
                        payload={
                            "classification_id": classification.classification_id,
                            "primary_label": classification.primary_label.value,
                            "confidence": classification.confidence,
                            "artifact_hash": classification_ref.sha256,
                        },
                    )

        snapshots = []
        gates = []
        thresholds = default_threshold_set()
        for model in manifest.models:
            model_runs = runs_by_model[model.model_config_id]
            snapshot = self.metrics.compute(
                experiment_id=experiment_id,
                model_config_id=model.model_config_id,
                runs=model_runs,
            )
            self.repository.add_metric_snapshot(project_id=project_id, snapshot=snapshot)
            gate = self.gates.evaluate(snapshot=snapshot, thresholds=thresholds)
            self.repository.add_gate(project_id=project_id, gate=gate)
            snapshots.append(snapshot)
            gates.append(gate)

        self.repository.set_experiment_state(experiment_id, ExperimentState.COMPLETED)
        self.audit.append(
            project_id=project_id,
            event_type="experiment.completed",
            aggregate_type="experiment",
            aggregate_id=experiment_id,
            actor_id="we3-foundation-runner",
            payload={
                "gate_statuses": {
                    gate.model_config_id: gate.status.value for gate in gates
                }
            },
        )
        audit_verified = self.audit.verify(project_id)

        limitations = [
            "Foundation build: deterministic mock provider only.",
            "Foundation deterministic grader is not certification approved.",
            "Local filesystem artifact storage is not a production immutability control.",
            "Development authentication is not OIDC and may not be used in production.",
            "Human review and adjudication interfaces are represented by escalation flags only.",
            "Threshold defaults require calibration and formal stakeholder approval.",
        ]
        dossier = build_dossier(
            experiment_id=experiment_id,
            project_id=project_id,
            manifest_hash=manifest_hash,
            dataset_hash=dataset_hash,
            snapshots=snapshots,
            gates=gates,
            artifact_index=[ref.to_dict() for ref in artifact_refs],
            audit_chain_verified=audit_verified,
            limitations=limitations,
        )

        if signing_key_path is None:
            key_path = output / ".dev-ed25519-signing-key.pem"
        else:
            key_path = Path(signing_key_path).resolve()
        if not key_path.exists():
            generate_private_key(key_path)
        private_key = load_private_key(key_path)
        dossier_path = write_signed_dossier(output, dossier, private_key)
        safe_html_path = write_safe_html(output, dossier)

        result_index = {
            "schema_version": "we3.foundation_result.v1",
            "experiment_id": experiment_id,
            "project_id": project_id,
            "manifest_hash": manifest_hash,
            "dataset_hash": dataset_hash,
            "dossier_path": dossier_path.name,
            "safe_html_path": safe_html_path.name,
            "gate_statuses": {
                gate.model_config_id: gate.status.value for gate in gates
            },
            "runs": {
                model_id: [
                    run.model_dump(mode="json", exclude={"classification"})
                    for run in model_runs
                ]
                for model_id, model_runs in runs_by_model.items()
            },
        }
        result_index_path = output / "experiment_result.json"
        result_index_path.write_text(
            json.dumps(result_index, sort_keys=True, indent=2),
            encoding="utf-8",
        )

        return EvaluationOutcome(
            experiment_id=experiment_id,
            dossier_path=dossier_path,
            safe_html_path=safe_html_path,
            result_index_path=result_index_path,
            signing_key_path=key_path,
            gate_statuses=result_index["gate_statuses"],
        )
