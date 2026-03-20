from __future__ import annotations


def value_or_zero(value: float | None) -> float:
    return float(value) if value is not None else 0.0



def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))



def regress_to_target(value: float, *, target: float, factor: float, lower: float | None = None, upper: float | None = None) -> float:
    regressed = target + factor * (value - target)
    if lower is not None or upper is not None:
        regressed = clamp(regressed, lower if lower is not None else regressed, upper if upper is not None else regressed)
    return regressed
