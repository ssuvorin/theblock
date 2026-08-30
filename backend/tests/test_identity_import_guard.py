from __future__ import annotations

from dataclasses import dataclass

import pytest
from app.services.import_guard import (
    ImportOriginRejected,
    assert_archive_import_allowed,
    demo_mode_enabled,
    filter_visible_by_origin,
)


@dataclass(frozen=True)
class OriginRecord:
    identifier: str
    data_origin: str


def test_demo_mode_archive_guard() -> None:
    assert assert_archive_import_allowed("synthetic", demo_mode=True).value == "synthetic"
    with pytest.raises(ImportOriginRejected):
        assert_archive_import_allowed("real_import", demo_mode=True)
    with pytest.raises(ImportOriginRejected):
        assert_archive_import_allowed("live_connector", demo_mode=True)
    assert assert_archive_import_allowed("real_import", demo_mode=False).value == "real_import"


def test_demo_mode_visibility_filters_real_import_without_mutation() -> None:
    records = [
        OriginRecord("synthetic", "synthetic"),
        OriginRecord("real", "real_import"),
        OriginRecord("live", "live_connector"),
    ]
    snapshot = list(records)
    visible = filter_visible_by_origin(records, demo_mode=True)
    assert tuple(record.identifier for record in visible) == ("synthetic", "live")
    assert records == snapshot
    assert records[1].data_origin == "real_import"
    assert filter_visible_by_origin(records, demo_mode=False) == tuple(records)


def test_demo_mode_environment_parsing_is_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    assert demo_mode_enabled()
    monkeypatch.setenv("DEMO_MODE", "off")
    assert not demo_mode_enabled()
    monkeypatch.setenv("DEMO_MODE", "sometimes")
    with pytest.raises(ValueError):
        demo_mode_enabled()
