"""Small, persistent, fail-closed budget ledgers for external providers.

OpenAI has a dedicated token-aware ledger because its APIs return token usage.
Sarvam's current contract does not expose a reliable application-side dollar
meter, so its voice adapters use this generic reservation ledger instead. A
reservation is written before the network request and is never released on a
failure: a timeout does not prove that the provider did not process the call.

The ledger is deliberately capped in code. It is an application safety brake,
not a replacement for provider account billing or an account-level spending
limit. Production Compose mounts the ledger directory as durable storage.
Deployments that run independent API containers must use a shared durable
volume or a shared budget service before scaling beyond one container.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:  # pragma: no cover - available on supported macOS/Linux deployments
    import fcntl
except ImportError:  # pragma: no cover - keeps imports portable
    fcntl = None


MAX_PROVIDER_BUDGET_USD = Decimal("10.00")


class ProviderBudgetError(RuntimeError):
    """Base class for provider budget failures."""


class ProviderBudgetExceeded(ProviderBudgetError):
    """Raised before a provider call would cross the configured cap."""


@dataclass(frozen=True)
class ProviderBudgetReservation:
    reservation_id: str
    provider: str
    operation: str
    model: str
    reserved_cost_usd: Decimal


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ProviderBudgetError(f"Invalid {field}: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise ProviderBudgetError(f"Invalid {field}: {value!r}")
    return result


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.000001')):.6f}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ProviderBudgetLedger:
    """Process-safe persistent reservation ledger for one external provider."""

    def __init__(
        self,
        provider: str,
        budget_usd: float | Decimal | str,
        ledger_path: Path,
        *,
        max_budget_usd: Decimal = MAX_PROVIDER_BUDGET_USD,
    ) -> None:
        provider = provider.strip().lower()
        if not provider or len(provider) > 64:
            raise ProviderBudgetError("provider name must be present and bounded")
        configured = _decimal(budget_usd, field="budget_usd")
        if configured <= 0:
            raise ProviderBudgetError("budget_usd must be greater than zero")
        if configured > max_budget_usd:
            raise ProviderBudgetError(
                f"{provider} budget_usd cannot exceed ${max_budget_usd:.2f}"
            )

        self.provider = provider
        self.configured_budget_usd = configured
        self.ledger_path = ledger_path
        self.lock_path = ledger_path.with_suffix(f"{ledger_path.suffix}.lock")
        self.max_budget_usd = max_budget_usd
        self._thread_lock = threading.RLock()

    @contextmanager
    def _file_lock(self) -> Iterator[None]:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _new_ledger(self) -> dict[str, Any]:
        return {
            "version": 1,
            "provider": self.provider,
            "budget_usd": _money(self.configured_budget_usd),
            "reserved_usd": _money(Decimal("0")),
            "observed_usd": _money(Decimal("0")),
            "calls": [],
        }

    def _read_ledger(self) -> dict[str, Any]:
        if not self.ledger_path.exists():
            return self._new_ledger()
        try:
            payload = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderBudgetError(
                f"Cannot safely read {self.provider} budget ledger at {self.ledger_path}"
            ) from exc
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ProviderBudgetError(
                f"Unsupported {self.provider} budget ledger; no provider call will be made"
            )
        if payload.get("provider") not in {None, self.provider}:
            raise ProviderBudgetError("Budget ledger belongs to a different provider")
        calls = payload.get("calls")
        if not isinstance(calls, list):
            raise ProviderBudgetError("Invalid calls list in provider budget ledger")
        # Validate the aggregate fields before trusting them as an authorization
        # boundary. A hand-edited or truncated ledger must stop provider calls.
        _decimal(payload.get("budget_usd"), field="budget_usd")
        _decimal(payload.get("reserved_usd"), field="reserved_usd")
        _decimal(payload.get("observed_usd"), field="observed_usd")
        return payload

    def _write_ledger(self, ledger: dict[str, Any]) -> None:
        temporary = self.ledger_path.with_suffix(f"{self.ledger_path.suffix}.tmp")
        temporary.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.ledger_path)

    def _effective_budget(self, ledger: dict[str, Any]) -> Decimal:
        stored = _decimal(ledger.get("budget_usd"), field="budget_usd")
        if stored <= 0 or stored > self.max_budget_usd:
            raise ProviderBudgetError("Stored provider budget is outside the safe ceiling")
        return min(self.configured_budget_usd, stored)

    def _reserve(
        self, *, operation: str, model: str, cost_usd: Decimal
    ) -> ProviderBudgetReservation:
        if cost_usd <= 0:
            raise ProviderBudgetError("A provider reservation must be greater than zero")
        reservation = ProviderBudgetReservation(
            reservation_id=f"{self.provider}-{uuid.uuid4().hex}",
            provider=self.provider,
            operation=operation[:96],
            model=model[:96],
            reserved_cost_usd=cost_usd,
        )
        with self._thread_lock, self._file_lock():
            ledger = self._read_ledger()
            budget = self._effective_budget(ledger)
            reserved = _decimal(ledger.get("reserved_usd"), field="reserved_usd")
            observed = _decimal(ledger.get("observed_usd"), field="observed_usd")
            committed = max(reserved, observed)
            if committed + cost_usd > budget:
                remaining = max(Decimal("0"), budget - committed)
                raise ProviderBudgetExceeded(
                    f"{self.provider} budget cap reached: ${remaining:.4f} remains, "
                    f"but ${cost_usd:.4f} is needed for {operation}."
                )
            ledger["provider"] = self.provider
            ledger["budget_usd"] = _money(budget)
            ledger["reserved_usd"] = _money(reserved + cost_usd)
            ledger["calls"].append(
                {
                    "reservation_id": reservation.reservation_id,
                    "provider": self.provider,
                    "operation": reservation.operation,
                    "model": reservation.model,
                    "status": "reserved",
                    "reserved_usd": _money(cost_usd),
                    "observed_usd": None,
                    "created_at": _now(),
                    "completed_at": None,
                }
            )
            self._write_ledger(ledger)
        return reservation

    def reserve_fixed(
        self, *, model: str, cost_usd: float | Decimal | str, operation: str
    ) -> ProviderBudgetReservation:
        """Reserve a conservative fixed amount before one network request."""
        return self._reserve(
            operation=operation,
            model=model,
            cost_usd=_decimal(cost_usd, field="cost_usd"),
        )

    def _finish(
        self,
        reservation: ProviderBudgetReservation,
        *,
        status: str,
        observed_usd: Decimal | None = None,
        metadata: dict[str, Any] | None = None,
        error_type: str | None = None,
    ) -> None:
        if reservation.provider != self.provider:
            raise ProviderBudgetError("Reservation belongs to a different provider")
        with self._thread_lock, self._file_lock():
            ledger = self._read_ledger()
            target = next(
                (
                    item
                    for item in ledger["calls"]
                    if item.get("reservation_id") == reservation.reservation_id
                ),
                None,
            )
            if target is None:
                raise ProviderBudgetError("Provider budget reservation is missing")
            if target.get("status") != "reserved":
                return
            target["status"] = status
            target["observed_usd"] = _money(observed_usd) if observed_usd is not None else None
            target["metadata"] = {
                str(key)[:64]: value
                for key, value in (metadata or {}).items()
                if isinstance(key, str) and isinstance(value, (str, int, float, bool))
            }
            target["error_type"] = error_type
            target["completed_at"] = _now()
            if observed_usd is not None:
                observed_total = _decimal(ledger.get("observed_usd"), field="observed_usd")
                ledger["observed_usd"] = _money(observed_total + observed_usd)
            self._write_ledger(ledger)

    def record_completion(
        self,
        reservation: ProviderBudgetReservation,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._finish(reservation, status="completed", metadata=metadata)

    def record_failure(self, reservation: ProviderBudgetReservation, error: BaseException) -> None:
        """Close the reservation but keep it committed, failing closed."""
        self._finish(
            reservation,
            status="failed",
            error_type=error.__class__.__name__,
        )

    def summary(self) -> dict[str, Any]:
        """Return a prompt-free, dashboard-safe summary."""
        with self._thread_lock, self._file_lock():
            ledger = self._read_ledger()
            budget = self._effective_budget(ledger)
            reserved = _decimal(ledger.get("reserved_usd"), field="reserved_usd")
            observed = _decimal(ledger.get("observed_usd"), field="observed_usd")
            calls = ledger["calls"]
            by_operation: dict[str, dict[str, Any]] = {}
            for call in calls:
                operation = str(call.get("operation") or "unknown")[:96]
                bucket = by_operation.setdefault(
                    operation,
                    {
                        "calls": 0,
                        "completed_calls": 0,
                        "failed_calls": 0,
                        "pending_calls": 0,
                        "reserved_usd": Decimal("0"),
                    },
                )
                bucket["calls"] += 1
                if call.get("status") == "completed":
                    bucket["completed_calls"] += 1
                elif call.get("status") == "failed":
                    bucket["failed_calls"] += 1
                elif call.get("status") == "reserved":
                    bucket["pending_calls"] += 1
                bucket["reserved_usd"] += _decimal(
                    call.get("reserved_usd", "0"), field="call.reserved_usd"
                )
            for bucket in by_operation.values():
                bucket["reserved_usd"] = _money(bucket["reserved_usd"])
            return {
                "provider": self.provider,
                "budget_usd": _money(budget),
                "reserved_usd": _money(reserved),
                "observed_usd": _money(observed),
                "remaining_usd": _money(max(Decimal("0"), budget - max(reserved, observed))),
                "calls": len(calls),
                "completed_calls": sum(call.get("status") == "completed" for call in calls),
                "failed_calls": sum(call.get("status") == "failed" for call in calls),
                "pending_calls": sum(call.get("status") == "reserved" for call in calls),
                "by_operation": by_operation,
                "ledger_path": str(self.ledger_path),
            }
