"""Shared helpers for HTTP routers."""

from typing import Optional


def _parse_int_csv(raw: Optional[str]) -> Optional[list[int]]:
    """Parse a comma-separated list of positive integers from a query string.

    Returns ``None`` when the input is empty/None; otherwise returns a list
    (possibly empty) preserving order and skipping blank tokens. Invalid
    integers raise ``ValueError``.
    """
    if raw is None:
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    return [int(token) for token in trimmed.split(",") if token.strip()]


def parse_tag_ids(raw: Optional[str]) -> Optional[list[int]]:
    """Parse the ``tag_ids`` query parameter used by report endpoints."""
    return _parse_int_csv(raw)


def parse_type_ids(raw: Optional[str]) -> Optional[list[int]]:
    """Parse the ``type_ids`` query parameter used by report endpoints."""
    return _parse_int_csv(raw)
