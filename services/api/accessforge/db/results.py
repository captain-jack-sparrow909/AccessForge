"""Typed helpers for SQLAlchemy mutation results at the async boundary."""

from __future__ import annotations


def affected_row_count(result: object) -> int:
    """Return a DB-API mutation count without leaking an untyped result object."""

    value = getattr(result, "rowcount", None)
    return value if isinstance(value, int) else 0
