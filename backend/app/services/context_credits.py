from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContextCreditBudget, ContextCreditUsage, utcnow


@dataclass(frozen=True)
class Reservation:
    allowed: bool
    request_key: str
    credits_reserved: int
    reason: str | None = None
    duplicate: bool = False


class ContextCreditLedger:
    """Atomic reservation/reconciliation gate for Context.dev calls."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def reserve(
        self,
        owner_id: str,
        category: str,
        request_key: str,
        estimated_credits: int,
    ) -> Reservation:
        existing = self._existing(category, request_key)
        if existing:
            return Reservation(
                False,
                request_key,
                existing.credits_reserved,
                reason="already_processed",
                duplicate=True,
            )
        budget = self._budget(lock=True)
        reason = self._exhaustion_reason(budget, category, estimated_credits)
        if reason:
            return Reservation(False, request_key, 0, reason=reason)
        self._increment(budget, category, estimated_credits)
        usage = ContextCreditUsage(
            owner_id=owner_id,
            category=category,
            request_key=request_key,
            credits_reserved=estimated_credits,
            status="reserved",
        )
        self._session.add(usage)
        self._session.flush()
        return Reservation(True, request_key, estimated_credits)

    def reconcile(self, category: str, request_key: str, actual_credits: int) -> None:
        usage = self._existing(category, request_key)
        if not usage or usage.status != "reserved":
            return
        budget = self._budget(lock=True)
        delta = actual_credits - usage.credits_reserved
        self._increment(budget, category, delta)
        usage.credits_consumed = actual_credits
        usage.status = "reconciled"
        usage.reconciled_at = utcnow()
        self._session.flush()

    def fail(self, category: str, request_key: str) -> None:
        usage = self._existing(category, request_key)
        if not usage or usage.status != "reserved":
            return
        budget = self._budget(lock=True)
        self._increment(budget, category, -usage.credits_reserved)
        usage.credits_consumed = 0
        usage.status = "failed"
        usage.reconciled_at = utcnow()
        self._session.flush()

    def snapshot(self) -> dict[str, int]:
        budget = self._budget()
        return {
            "total_cap": budget.total_cap,
            "credits_used": budget.credits_used,
            "credits_remaining": budget.total_cap - budget.credits_used,
            "spendable_credits_remaining": max(
                0,
                budget.total_cap - budget.reserve_floor - budget.credits_used,
            ),
            "market_search_remaining": budget.market_search_cap - budget.search_credits_used,
            "brand_remaining": budget.brand_cap - budget.brand_credits_used,
            "reserve_floor": budget.reserve_floor,
        }

    def _budget(self, *, lock: bool = False) -> ContextCreditBudget:
        statement = select(ContextCreditBudget).where(ContextCreditBudget.id == 1)
        if lock:
            statement = statement.with_for_update()
        budget = self._session.scalar(statement)
        if budget is None:
            budget = ContextCreditBudget(id=1)
            self._session.add(budget)
            self._session.flush()
        return budget

    def _existing(self, category: str, request_key: str) -> ContextCreditUsage | None:
        return self._session.scalar(
            select(ContextCreditUsage).where(
                ContextCreditUsage.category == category,
                ContextCreditUsage.request_key == request_key,
            )
        )

    @staticmethod
    def _increment(budget: ContextCreditBudget, category: str, amount: int) -> None:
        budget.credits_used += amount
        if category == "brand":
            budget.brand_credits_used += amount
        else:
            budget.search_credits_used += amount
        budget.updated_at = utcnow()

    @staticmethod
    def _exhaustion_reason(
        budget: ContextCreditBudget,
        category: str,
        estimate: int,
    ) -> str | None:
        if estimate < 0:
            return "invalid_estimate"
        if budget.credits_used + estimate > budget.total_cap - budget.reserve_floor:
            return "reserve_floor"
        category_used = (
            budget.brand_credits_used if category == "brand" else budget.search_credits_used
        )
        category_cap = budget.brand_cap if category == "brand" else budget.market_search_cap
        if category_used + estimate > category_cap:
            return "category_cap"
        return None
