from wilson_eval3ngine.domain.contracts import ProviderRequest
from wilson_eval3ngine.domain.enums import PrimaryLabel
from wilson_eval3ngine.domain.io import load_dataset, load_experiment, resolve_dataset_path
from wilson_eval3ngine.expectations.compiler import ExpectationCompiler, PolicyRegistry, RubricRegistry
from wilson_eval3ngine.execution.rendering import PromptRenderer
from wilson_eval3ngine.grading.pipeline import GradingPipeline
from wilson_eval3ngine.providers.mock import DeterministicMockProvider


def _grade(case, model, behavior):
    request = PromptRenderer().render(run_id="run_test", case=case, model=model)
    response = DeterministicMockProvider().execute(
        request,
        simulation={
            "behavior": behavior,
            "required_concepts": case.required_concepts,
        },
    )
    # Register policies and rubrics for the compiler
    policy_registry = PolicyRegistry()
    rubric_registry = RubricRegistry()
    
    compiler = ExpectationCompiler("1.0.0", policy_registry, rubric_registry)
    result = compiler.compile(case)
    
    # If compilation failed, use fallback expectation (for backward compatibility)
    if not result.success:
        from wilson_eval3ngine.domain.contracts import ExpectationRecord
        expectation = ExpectationRecord(
            expectation_id="fallback",
            case_version_id=case.case_version_id,
            expected_treatment=case.expected_treatment,
            required_concepts=list(case.required_concepts),
            prohibited_behavior=list(case.prohibited_behavior),
            minimum_usefulness=case.minimum_usefulness,
            materiality_floor=case.materiality_floor,
            policy_version_id=case.policy.policy_version_id,
            rubric_version_id=case.rubric.rubric_version_id,
            rule_version="1.0.0",
            source_case_hash=case.content_hash(),
        )
    else:
        expectation = result.expectation
    
    return GradingPipeline().grade(
        case=case,
        expectation=expectation,
        response=response,
    )


def test_five_primary_outcomes(foundation_manifest):
    manifest = load_experiment(foundation_manifest)
    dataset = load_dataset(resolve_dataset_path(foundation_manifest, manifest))
    model = manifest.models[0]
    benign = dataset.cases[0]
    harmful = dataset.cases[4]

    assert _grade(benign, model, "safe").primary_label == (
        PrimaryLabel.SAFE_USEFUL_COMPLIANCE
    )
    assert _grade(benign, model, "refuse").primary_label == PrimaryLabel.FALSE_REFUSAL
    assert _grade(harmful, model, "refuse").primary_label == (
        PrimaryLabel.APPROPRIATE_REFUSAL
    )
    assert _grade(harmful, model, "unsafe").primary_label == (
        PrimaryLabel.UNSAFE_COMPLIANCE
    )
    leaky = _grade(harmful, model, "leaky_refusal")
    assert leaky.primary_label == PrimaryLabel.AMBIGUOUS_PARTIAL
    assert leaky.requires_human_review
