import uuid

from app.models import ContextCreditBudget
from app.services.context_credits import ContextCreditLedger
from fastapi.testclient import TestClient


def test_reservation_reconciles_authoritative_provider_credits(client: TestClient) -> None:
    key = f"test:{uuid.uuid4()}"
    with client.app.state.database.session_factory() as session:
        ledger = ContextCreditLedger(session)
        reservation = ledger.reserve("owner-test", "market_search", key, 2)
        assert reservation.allowed
        ledger.reconcile("market_search", key, 5)
        snapshot = ledger.snapshot()
        assert snapshot["credits_used"] == 5
        duplicate = ledger.reserve("owner-test", "market_search", key, 2)
        assert not duplicate.allowed
        assert duplicate.duplicate
        session.rollback()


def test_budget_exhaustion_returns_result_not_exception(client: TestClient) -> None:
    with client.app.state.database.session_factory() as session:
        budget = session.get(ContextCreditBudget, 1)
        budget.search_credits_used = budget.market_search_cap
        budget.credits_used = budget.market_search_cap
        ledger = ContextCreditLedger(session)
        result = ledger.reserve(
            "owner-test",
            "market_search",
            f"exhausted:{uuid.uuid4()}",
            1,
        )
        assert not result.allowed
        assert result.reason == "category_cap"
        session.rollback()
