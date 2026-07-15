from __future__ import annotations

from ..util import sha256_hex


def logical_run_key(
    *,
    experiment_definition_hash: str,
    test_case_version_id: str,
    rendered_prompt_hash: str,
    model_config_hash: str,
    repetition_index: int,
    execution_mode: str,
) -> str:
    return sha256_hex(
        {
            "experiment_definition_hash": experiment_definition_hash,
            "test_case_version_id": test_case_version_id,
            "rendered_prompt_hash": rendered_prompt_hash,
            "model_config_hash": model_config_hash,
            "repetition_index": repetition_index,
            "execution_mode": execution_mode,
        }
    )
