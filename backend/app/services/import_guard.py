"""Data-origin interlock for demo imports and API visibility."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Any


class DataOrigin(StrEnum):
    SYNTHETIC = "synthetic"
    REAL_IMPORT = "real_import"
    LIVE_CONNECTOR = "live_connector"


class ImportOriginRejected(PermissionError):
    """Raised when an archive origin is unsafe for the current mode."""


_TRUTHY = frozenset({"1", "true", "yes", "on"})
_FALSEY = frozenset({"0", "false", "no", "off", ""})


def demo_mode_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Read DEMO_MODE strictly so misspellings do not silently change behavior."""

    source = os.environ if environ is None else environ
    raw_value = source.get("DEMO_MODE", "false").strip().casefold()
    if raw_value in _TRUTHY:
        return True
    if raw_value in _FALSEY:
        return False
    raise ValueError("DEMO_MODE must be a boolean value")


def coerce_data_origin(value: DataOrigin | str) -> DataOrigin:
    try:
        return DataOrigin(value)
    except ValueError as error:
        allowed = ", ".join(origin.value for origin in DataOrigin)
        raise ValueError(f"data origin must be one of: {allowed}") from error


def assert_archive_import_allowed(
    data_origin: DataOrigin | str,
    *,
    demo_mode: bool | None = None,
) -> DataOrigin:
    """Reject non-synthetic archives while demo mode is active."""

    origin = coerce_data_origin(data_origin)
    enabled = demo_mode_enabled() if demo_mode is None else demo_mode
    if enabled and origin is not DataOrigin.SYNTHETIC:
        raise ImportOriginRejected("demo mode only accepts archives marked synthetic")
    return origin


assert_import_allowed = assert_archive_import_allowed


def origin_is_visible(
    data_origin: DataOrigin | str,
    *,
    demo_mode: bool | None = None,
) -> bool:
    """Real imports are never API-visible in demo mode."""

    origin = coerce_data_origin(data_origin)
    enabled = demo_mode_enabled() if demo_mode is None else demo_mode
    return not (enabled and origin is DataOrigin.REAL_IMPORT)


def filter_visible_by_origin[T](
    records: Iterable[T],
    *,
    demo_mode: bool | None = None,
) -> tuple[T, ...]:
    """Return visible records without mutating stored objects or the input iterable."""

    enabled = demo_mode_enabled() if demo_mode is None else demo_mode
    visible: list[T] = []
    for record in records:
        if origin_is_visible(_record_origin(record), demo_mode=enabled):
            visible.append(record)
    return tuple(visible)


def _record_origin(record: Any) -> DataOrigin | str:
    if isinstance(record, Mapping):
        if "data_origin" not in record:
            raise ValueError("record has no data_origin")
        return record["data_origin"]
    if not hasattr(record, "data_origin"):
        raise ValueError("record has no data_origin")
    return record.data_origin
