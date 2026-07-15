from __future__ import annotations

from pathlib import Path
from typing import TypeVar, Type

import yaml
from pydantic import BaseModel, ValidationError

from .contracts import DatasetManifest, ExperimentManifest


class ContractLoadError(ValueError):
    pass


T = TypeVar("T", bound=BaseModel)


def load_yaml_model(path: str | Path, model_type: Type[T]) -> T:
    source = Path(path)
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractLoadError(f"unable to read {source}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ContractLoadError(f"invalid YAML in {source}: {exc}") from exc

    try:
        return model_type.model_validate(raw)
    except ValidationError as exc:
        raise ContractLoadError(f"contract validation failed for {source}: {exc}") from exc


def load_experiment(path: str | Path) -> ExperimentManifest:
    return load_yaml_model(path, ExperimentManifest)


def load_dataset(path: str | Path) -> DatasetManifest:
    return load_yaml_model(path, DatasetManifest)


def resolve_dataset_path(
    manifest_path: str | Path,
    manifest: ExperimentManifest,
) -> Path:
    if not manifest.dataset.local_path:
        raise ContractLoadError(
            "the foundation runner requires dataset.local_path; "
            "production registry resolution is a pre-production backlog item"
        )
    base = Path(manifest_path).resolve().parent
    candidate = Path(manifest.dataset.local_path)
    return candidate if candidate.is_absolute() else (base / candidate).resolve()
