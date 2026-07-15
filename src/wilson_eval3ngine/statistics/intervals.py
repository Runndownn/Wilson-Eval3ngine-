from __future__ import annotations

from math import sqrt
from statistics import NormalDist

from ..domain.contracts import Interval


def wilson_interval(
    successes: int,
    total: int,
    *,
    confidence: float = 0.95,
) -> Interval | None:
    if total <= 0:
        return None
    if successes < 0 or successes > total:
        raise ValueError("successes must be between zero and total")
    alpha = 1.0 - confidence
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    p = successes / total
    denominator = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denominator
    margin = (
        z
        * sqrt((p * (1.0 - p) / total) + (z * z) / (4.0 * total * total))
        / denominator
    )
    return Interval(
        lower=max(0.0, center - margin),
        upper=min(1.0, center + margin),
        confidence=confidence,
    )
