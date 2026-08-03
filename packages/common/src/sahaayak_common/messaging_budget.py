"""Spend limits for outbound messaging.

Deliberately not the OpenAI ledger. That one is a lifetime USD reservation file
for a data pipeline; this is a rolling local-currency cap on a live channel
that a bug, a retry loop, or a compromised session could otherwise drive at the
speed of an API. The two units are different, the windows are different, and
sharing one ledger would let a messaging incident silently exhaust the budget
the ingestion pipeline depends on.

Spend is computed from the delivery rows themselves rather than a separate
counter. There is then no way for the ledger and the record of what was
actually sent to disagree, and no reconciliation job to write.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from sahaayak_common.models import NotificationDelivery
from sahaayak_common.settings import settings


@dataclass(frozen=True, slots=True)
class BudgetPosture:
    """What has been spent, what is allowed, and whether to proceed."""

    allowed: bool
    reason: str = ""
    currency: str = "INR"
    daily_spent_minor_units: int = 0
    daily_budget_minor_units: int | None = None
    monthly_spent_minor_units: int = 0
    monthly_budget_minor_units: int | None = None

    @property
    def daily_remaining_minor_units(self) -> int | None:
        if self.daily_budget_minor_units is None:
            return None
        return max(0, self.daily_budget_minor_units - self.daily_spent_minor_units)

    @property
    def monthly_remaining_minor_units(self) -> int | None:
        if self.monthly_budget_minor_units is None:
            return None
        return max(0, self.monthly_budget_minor_units - self.monthly_spent_minor_units)


def spend_since(db: Session, since: datetime, *, channel: str | None = None) -> int:
    """Total recorded cost of deliveries created since ``since``.

    Rows whose cost the provider has not yet reported count as zero. That
    understates in-flight spend, so the cap is a floor rather than a guarantee
    — worth knowing when setting the number, and the reason the ceiling should
    be set below the amount that would actually hurt.
    """
    statement = select(func.coalesce(func.sum(NotificationDelivery.cost_minor_units), 0)).where(
        NotificationDelivery.created_at >= since
    )
    if channel is not None:
        statement = statement.where(NotificationDelivery.channel == channel)
    return int(db.exec(statement).one() or 0)


def evaluate_budget(
    db: Session, *, channel: str | None = None, now: datetime | None = None
) -> BudgetPosture:
    """Whether another message may be sent under the configured caps.

    With no caps configured the posture is permissive: a deployment that has
    not set a budget has not asked to be stopped, and refusing to send would
    make the feature look broken rather than protected.
    """
    moment = now or datetime.now(UTC)
    daily_cap = settings.infobip_daily_budget_minor_units
    monthly_cap = settings.infobip_monthly_budget_minor_units
    currency = settings.infobip_cost_currency

    daily_spent = spend_since(db, moment - timedelta(days=1), channel=channel)
    monthly_spent = spend_since(db, moment - timedelta(days=30), channel=channel)

    reason = ""
    allowed = True
    if daily_cap is not None and daily_spent >= daily_cap:
        allowed, reason = False, "daily_budget_exhausted"
    elif monthly_cap is not None and monthly_spent >= monthly_cap:
        allowed, reason = False, "monthly_budget_exhausted"

    return BudgetPosture(
        allowed=allowed,
        reason=reason,
        currency=currency,
        daily_spent_minor_units=daily_spent,
        daily_budget_minor_units=daily_cap,
        monthly_spent_minor_units=monthly_spent,
        monthly_budget_minor_units=monthly_cap,
    )
