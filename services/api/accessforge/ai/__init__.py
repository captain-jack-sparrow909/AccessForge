"""Domain-owned AI boundaries.

This package intentionally contains no database, route, or job coupling.  AI
providers are replaceable infrastructure; domain workflows consume the typed
contracts exposed by :mod:`accessforge.ai.providers`.
"""
