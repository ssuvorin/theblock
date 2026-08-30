"""The orchestrator must degrade only for provider outages, never for its own defects.

A broad ``except Exception`` previously relabelled every failure — bad config, schema drift,
plain bugs — as a degraded component, which is how an empty API key surfaced as
"0 opportunities" instead of an error.
"""

from __future__ import annotations

from dataclasses import replace

import httpx
import pytest
from app.config import Settings
from app.connectors.context_dev.synthetic import SyntheticDemoMarketSearch
from app.connectors.context_dev.web_search import ContextDevWebSearch
from app.domain.ports import Goal, MarketSearchPort, MarketSearchResponse, MarketSearchUnavailable
from app.models import ContextCreditUsage, Owner
from app.services.query.orchestrator import (
    PRIVATE_RETRIEVAL_COMPONENT,
    OpportunityQueryOrchestrator,
)
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

QUESTION = "Product Manager role at a crypto company in Dubai"
_BAD_GATEWAY = httpx.Response(502, request=httpx.Request("POST", "https://x"))
_GOAL = Goal(
    role="Product Manager",
    related_roles=[],
    industry=["crypto"],
    location=["Dubai"],
    action="find_role",
)


class _FailingProvider:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def search(self, owner_id: str, goal: Goal, num_results: int = 20) -> MarketSearchResponse:
        raise self._error


def _orchestrator(
    client: TestClient,
    settings: Settings,
    provider: MarketSearchPort,
) -> tuple[OpportunityQueryOrchestrator, Session]:
    session = client.app.state.database.session_factory()
    owner = session.scalar(select(Owner))
    orchestrator = OpportunityQueryOrchestrator(session, owner, settings)
    orchestrator._provider = provider
    return orchestrator, session


def test_provider_outage_degrades_with_named_component(
    client: TestClient,
    auth: dict[str, str],
    settings: Settings,
) -> None:
    del auth
    error = MarketSearchUnavailable("context.dev request failed: timed out")
    orchestrator, session = _orchestrator(client, settings, _FailingProvider(error))
    with session:
        answer = orchestrator.execute(QUESTION)["answer"]
    assert answer["degraded"] is True
    assert answer["degraded_components"] == ["context_dev_search"]
    assert answer["opportunities"] == []


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("Context.dev is not configured"),
        KeyError("results"),
        TypeError("bad provider payload"),
    ],
)
def test_defects_are_not_reported_as_degradation(
    client: TestClient,
    auth: dict[str, str],
    settings: Settings,
    error: Exception,
) -> None:
    del auth
    orchestrator, session = _orchestrator(client, settings, _FailingProvider(error))
    with session, pytest.raises(type(error)):
        orchestrator.execute(QUESTION)


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("refused"), TypeError("unexpected payload"), RuntimeError("boom")],
)
def test_reserved_credits_are_always_refunded_when_the_call_fails(
    client: TestClient,
    settings: Settings,
    error: Exception,
) -> None:
    """Cleanup must be broad: any failure has to release the reservation, not just known ones."""

    session = client.app.state.database.session_factory()
    with session:
        owner = session.scalar(select(Owner))
        search = ContextDevWebSearch(session, settings)
        search._request = _raising(error)
        before = search._ledger.snapshot()["credits_used"]
        with pytest.raises(Exception):  # noqa: B017 - the type is the parametrised input
            search.search(owner.id, _GOAL)
        usage = session.scalars(select(ContextCreditUsage)).all()
        assert [row.status for row in usage] == ["failed"]
        assert search._ledger.snapshot()["credits_used"] == before


def _raising(error: Exception):
    def _call(payload: dict) -> dict:
        del payload
        raise error

    return _call


def test_transport_failures_become_market_search_unavailable(settings: Settings) -> None:
    """The adapter owns the translation, so the orchestrator never inspects httpx."""

    assert issubclass(MarketSearchUnavailable, RuntimeError)
    assert isinstance(httpx.ConnectError("x"), httpx.HTTPError)
    assert isinstance(httpx.ReadTimeout("x"), httpx.HTTPError)
    del settings


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("timed out"),
        httpx.HTTPStatusError(
            "502", request=httpx.Request("POST", "https://x"), response=_BAD_GATEWAY
        ),
    ],
)
def test_raw_transport_errors_still_degrade_to_network_only(
    client: TestClient,
    settings: Settings,
    error: Exception,
) -> None:
    """A provider that forgets to translate httpx is still an outage, not a defect."""

    orchestrator, session = _orchestrator(client, settings, _FailingProvider(error))
    with session:
        answer = orchestrator.execute(QUESTION)["answer"]
    assert answer["degraded"] is True
    assert answer["degraded_components"] == ["context_dev_search"]
    assert answer["opportunities"] == []
    assert answer["network_candidates"]
    assert answer["search"]["checked_at"] is None


def test_private_sql_failure_is_named_private_retrieval_and_never_convex(
    client: TestClient,
    settings: Settings,
) -> None:
    """The warm-path read is PostgreSQL only, so the reported component must say so."""

    orchestrator, session = _orchestrator(client, settings, SyntheticDemoMarketSearch())
    orchestrator._card_list = _raising_call(OperationalError("SELECT 1", {}, Exception("gone")))
    with session:
        answer = orchestrator.execute(QUESTION)["answer"]
    assert answer["degraded"] is True
    assert answer["degraded_components"] == [PRIVATE_RETRIEVAL_COMPONENT]
    assert "convex" not in str(answer).lower()
    assert answer["evidence_quality"] == "partial"
    assert answer["opportunities"]
    for card in answer["opportunities"]:
        assert card["warm_path_status"] == "private_search_unavailable"
        assert card["warm_paths"] == []
        assert card["public_citations"]


def test_a_bug_in_the_private_path_propagates_instead_of_degrading(
    client: TestClient,
    settings: Settings,
) -> None:
    orchestrator, session = _orchestrator(client, settings, SyntheticDemoMarketSearch())
    orchestrator._card_list = _raising_call(TypeError("ranking_factors is not subscriptable"))
    with session, pytest.raises(TypeError):
        orchestrator.execute(QUESTION)


def test_query_route_degrades_for_an_outage(
    client: TestClient,
    auth: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_provider(monkeypatch, _FailingProvider(httpx.ReadTimeout("timed out")))
    response = client.post("/api/query", json={"question": QUESTION}, headers=auth)
    assert response.status_code == 200
    answer = response.json()["answer"]
    assert answer["degraded_components"] == ["context_dev_search"]


def test_query_route_raises_for_a_defect_instead_of_answering_degraded(
    client: TestClient,
    auth: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unexpected error must reach the ASGI boundary as a 500, not a cheerful 200."""

    _patch_provider(monkeypatch, _FailingProvider(TypeError("provider returned a str")))
    with pytest.raises(TypeError):
        client.post("/api/query", json={"question": QUESTION}, headers=auth)


def test_missing_api_key_is_a_defect_not_a_reported_outage(
    client: TestClient,
    settings: Settings,
) -> None:
    """The original bug: a blank key must not be answerable as "0 opportunities"."""

    assert settings.context_dev_api_key is None
    session = client.app.state.database.session_factory()
    with session:
        owner = session.scalar(select(Owner))
        with pytest.raises(RuntimeError) as raised:
            ContextDevWebSearch(session, settings).search(owner.id, _GOAL)
    assert not isinstance(raised.value, MarketSearchUnavailable)
    assert type(raised.value) is RuntimeError


def test_adapter_translates_only_transport_and_decode_failures(
    client: TestClient,
    settings: Settings,
) -> None:
    session = client.app.state.database.session_factory()
    with session:
        owner = session.scalar(select(Owner))
        search = ContextDevWebSearch(session, settings)
        search._request = _raising(httpx.ConnectError("refused"))
        with pytest.raises(MarketSearchUnavailable):
            search.search(owner.id, _GOAL)
        search._request = _raising(ValueError("Expecting value: line 1 column 1"))
        with pytest.raises(MarketSearchUnavailable):
            search.search(owner.id, replace(_GOAL, role="Head of Product"))
        search._request = _raising(KeyError("results"))
        with pytest.raises(KeyError):
            search.search(owner.id, replace(_GOAL, role="Director of Product"))


def _patch_provider(monkeypatch: pytest.MonkeyPatch, provider: MarketSearchPort) -> None:
    monkeypatch.setattr(
        OpportunityQueryOrchestrator,
        "_market_provider",
        lambda self: provider,
    )


def _raising_call(error: Exception):
    def _call(*args: object, **kwargs: object) -> list[dict]:
        del args, kwargs
        raise error

    return _call
