from wilson_eval3ngine.execution.idempotency import logical_run_key


def test_logical_key_is_deterministic_and_sensitive():
    args = dict(
        experiment_definition_hash="a" * 64,
        test_case_version_id="casev_1",
        rendered_prompt_hash="b" * 64,
        model_config_hash="c" * 64,
        repetition_index=0,
        execution_mode="certification",
    )
    first = logical_run_key(**args)
    second = logical_run_key(**args)
    assert first == second
    assert len(first) == 64

    changed = dict(args)
    changed["repetition_index"] = 1
    assert logical_run_key(**changed) != first
