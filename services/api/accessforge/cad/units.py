"""Canonical length conversion used at the API boundary.

The persisted ``DesignSpec`` uses metres, the SI base unit.  CadQuery follows
the common mechanical-CAD convention of millimetres, so the compiler performs
the only metres-to-millimetres conversion internally and records it in its
provenance.  Values are rounded to a nanometre to make JSON hashing stable.
"""

from __future__ import annotations

import math

from fastapi import HTTPException, status

UNIT_TO_METRES: dict[str, float] = {
    "m": 1.0,
    "mm": 0.001,
    "cm": 0.01,
    "in": 0.0254,
}


class UnitConversionError(ValueError):
    """A user-facing length entry cannot safely become a canonical value."""


def normalize_unit(unit: str) -> str:
    value = unit.strip().lower()
    if value not in UNIT_TO_METRES:
        allowed = ", ".join(UNIT_TO_METRES)
        raise UnitConversionError(f"Length units must be one of: {allowed}.")
    return value


def to_metres(value: float, unit: str) -> float:
    if not math.isfinite(value) or value <= 0:
        raise UnitConversionError("A length must be a finite value greater than zero.")
    canonical = round(value * UNIT_TO_METRES[normalize_unit(unit)], 9)
    if canonical <= 0:
        raise UnitConversionError("The converted length must be greater than zero.")
    return canonical


def metres_to_mm(value_metres: float) -> float:
    if not math.isfinite(value_metres) or value_metres <= 0:
        raise UnitConversionError("A canonical length must be a finite value greater than zero.")
    return round(value_metres * 1000.0, 6)


def unit_problem(error: UnitConversionError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))
