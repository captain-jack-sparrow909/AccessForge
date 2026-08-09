"""Deterministic, repository-reviewed CAD building blocks.

This package intentionally contains no dynamic template loader.  The registry
maps a small, immutable allowlist of reviewed releases to fixed Python
generators.  It is not an AI or user-code execution boundary.
"""

from accessforge.cad.schemas import DesignSpec

__all__ = ["DesignSpec"]
