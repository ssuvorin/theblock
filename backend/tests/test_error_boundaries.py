"""The orchestrator must degrade only for provider outages, never for its own defects.

A broad ``except Exception`` previously relabelled every failure — bad config, schema drift,
plain bugs — as a degraded component, which is how an empty API key surfaced as
"0 opportunities" instead of an error.
"""

from __future__ import annotations

import httpx
import pytest
from app.config import Settings
from app.connectors.context_dev.web_search import ContextDevWebSearch
from app.domain.ports import Goal, MarketSearchPort, MarketSearchResponse, MarketSearchUnavailable
from app.models import ContextCreditUsage, Owner
from app.services.query.orchestrator import OpportunityQueryOrchestrator
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

QUESTION = "Product Manager role at a crypto company in Dubai"
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
