"""Persistent, fail-closed spending guard for OpenAI calls.

The ingestion pipeline and local development agent can be run repeatedly. A
per-process counter is not enough because it resets every time a command is
started, so this module keeps a small, local ledger under ``data/usage``.

The guard reserves a conservative upper bound *before* a request is sent. A
failed request keeps its reservation because a network failure does not prove
that the provider did not process the request. The ledger therefore fails
closed and cannot silently overspend the configured ceiling across reruns.

The rates below are the standard text-token rates used for accounting. The
reservation applies a safety multiplier and a conservative character-to-token
estimate; the result is intentionally an upper bound, not a billing invoice.
"""

from __future__ import annotations

import json
import math
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

try:  # pragma: no cover - fcntl is available on the supported macOS/Linux hosts
    import fcntl
except ImportError:  # pragma: no cover - keeps the module importable on Windows
    fcntl = None


# This is an application-level ceiling. A deployment can choose $5 or $10,
# but cannot accidentally turn a public endpoint into an uncapped account.
MAX_CONFIGURED_BUDGET_USD = Decimal("10.00")
DEFAULT_SAFETY_MULTIPLIER = Decimal("2.00")
TOKENS_PER_MILLION = Decimal("1000000")


class BudgetError(RuntimeError):
    """Base class for budget-ledger errors."""


class BudgetExceeded(BudgetError):
    """Raised before an API call when its reservation would cross the cap."""


@dataclass(frozen=True)
class ChatPricing:
    input_per_million: Decimal
    output_per_million: Decimal


# These are the currently published standard text-token prices. Unknown model
# aliases deliberately use a much higher fallback so a newly configured model
# cannot bypass the guard by being absent from this table.
CHAT_PRICING: dict[str, ChatPricing] = {
    "gpt-4o-mini": ChatPricing(Decimal("0.15"), Decimal("0.60")),
    "gpt-4o": ChatPricing(Decimal("2.50"), Decimal("10.00")),
}
UNKNOWN_CHAT_PRICING = ChatPricing(Decimal("10.00"), Decimal("50.00"))


@dataclass(frozen=True)
class BudgetReservation:
    reservation_id: str
    operation: str
    model: str
    reserved_cost_usd: Decimal
    input_tokens_estimate: int | None = None
    output_tokens_estimate: int | None = None


def _decimal(value: object, *, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise BudgetError(f"Invalid {field} in OpenAI budget ledger: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise BudgetError(f"Invalid {field} in OpenAI budget ledger: {value!r}")
    return result


def _money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.000001')):.6f}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def pricing_for_model(model: str) -> ChatPricing:
    """Return known pricing, including snapshot aliases, or a safe fallback."""
    normalised = model.strip().lower()
    if normalised in CHAT_PRICING:
        return CHAT_PRICING[normalised]
    for name, pricing in CHAT_PRICING.items():
        if normalised.startswith(f"{name}-"):
            return pricing
    return UNKNOWN_CHAT_PRICING


def _usage_counts(response: object) -> dict[str, int] | None:
    """Extract usage fields from Chat Completions or Responses-style objects."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return None

    input_tokens = getattr(usage, "prompt_tokens", None)
    if input_tokens is None:
        input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "completion_tokens", None)
    if output_tokens is None:
        output_tokens = getattr(usage, "output_tokens", None)

    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    total_tokens = getattr(usage, "total_tokens", None)
    if not isinstance(total_tokens, int):
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


class OpenAIBudgetLedger:
    """Reserve and account for OpenAI requests across process restarts.

    ``budget_usd`` is intentionally limited to ``$10``. The first ledger run
    stores the configured ceiling; later runs use the lower of the stored and
    current configuration so an accidental environment change cannot enlarge
    an existing test allowance.
    """

    def __init__(
        self,
        budget_usd: float | Decimal | str,
        ledger_path: Path,
        *,
        safety_multiplier: Decimal = DEFAULT_SAFETY_MULTIPLIER,
    ) -> None:
        configured = _decimal(budget_usd, field="budget_usd")
        if configured <= 0:
            raise BudgetError("OpenAI budget_usd must be greater than zero")
        if configured > MAX_CONFIGURED_BUDGET_USD:
            raise BudgetError(
                f"OpenAI budget_usd cannot exceed ${MAX_CONFIGURED_BUDGET_USD:.2f}"
            )
        if safety_multiplier < 1:
            raise BudgetError("OpenAI budget safety_multiplier must be at least 1")

        self.configured_budget_usd = configured
        self.ledger_path = ledger_path
        self.lock_path = ledger_path.with_suffix(f"{ledger_path.suffix}.lock")
        self.safety_multiplier = safety_multiplier
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
            raise BudgetError(
                f"Cannot safely read OpenAI budget ledger at {self.ledger_path}; "
                "no API call will be made"
            ) from exc
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise BudgetError(
                f"Unsupported OpenAI budget ledger at {self.ledger_path}; no API call will be made"
            )
        calls = payload.get("calls")
        if not isinstance(calls, list):
            raise BudgetError(
                f"Invalid calls list in OpenAI budget ledger at {self.ledger_path}"
            )
        return payload

    def _effective_budget(self, ledger: dict[str, Any]) -> Decimal:
        stored = _decimal(ledger.get("budget_usd"), field="budget_usd")
        if stored <= 0 or stored > MAX_CONFIGURED_BUDGET_USD:
            raise BudgetError(
                f"Unsafe budget_usd in OpenAI budget ledger at {self.ledger_path}"
            )
        return min(self.configured_budget_usd, stored)

    def _write_ledger(self, ledger: dict[str, Any]) -> None:
        temporary_path = self.ledger_path.with_suffix(f"{self.ledger_path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary_path.replace(self.ledger_path)

    def _reserve(
        self,
        *,
        operation: str,
        model: str,
        reserved_cost_usd: Decimal,
        input_tokens_estimate: int | None = None,
        output_tokens_estimate: int | None = None,
    ) -> BudgetReservation:
        if reserved_cost_usd <= 0:
            raise BudgetError("OpenAI reservation must be greater than zero")

        reservation = BudgetReservation(
            reservation_id=f"oai_{uuid.uuid4().hex}",
            operation=operation,
            model=model,
            reserved_cost_usd=reserved_cost_usd,
            input_tokens_estimate=input_tokens_estimate,
            output_tokens_estimate=output_tokens_estimate,
        )

        with self._thread_lock, self._file_lock():
            ledger = self._read_ledger()
            budget = self._effective_budget(ledger)
            reserved = _decimal(ledger.get("reserved_usd"), field="reserved_usd")
            observed = _decimal(ledger.get("observed_usd"), field="observed_usd")
            # Reservations are deliberately conservative. If provider-reported
            # usage ever exceeds one, observed spend becomes the stronger
            # boundary so a pricing/estimation surprise cannot open a second
            # path past the configured cap.
            committed = max(reserved, observed)
            if committed + reserved_cost_usd > budget:
                remaining = max(Decimal("0"), budget - committed)
                raise BudgetExceeded(
                    f"OpenAI budget cap reached: ${remaining:.4f} remains, but "
                    f"${reserved_cost_usd:.4f} is needed for {operation}."
                )

            calls = ledger["calls"]
            calls.append(
                {
                    "reservation_id": reservation.reservation_id,
                    "operation": operation,
                    "model": model,
                    "status": "reserved",
                    "reserved_usd": _money(reserved_cost_usd),
                    "observed_usd": None,
                    "input_tokens_estimate": input_tokens_estimate,
                    "output_tokens_estimate": output_tokens_estimate,
                    "usage": None,
                    "created_at": _now(),
                    "completed_at": None,
                }
            )
            ledger["budget_usd"] = _money(budget)
            ledger["reserved_usd"] = _money(reserved + reserved_cost_usd)
            self._write_ledger(ledger)
        return reservation

    def reserve_chat(
        self,
        *,
        model: str,
        input_characters: int,
        max_output_tokens: int,
        operation: str,
    ) -> BudgetReservation:
        """Reserve a conservative upper bound for one text chat request."""
        if input_characters < 0 or max_output_tokens <= 0:
            raise BudgetError("Invalid input/output bounds for OpenAI chat request")

        # Two characters per token plus a small framing allowance is safer for
        # Indic scripts than the usual four-character heuristic.
        input_tokens = max(1, math.ceil(input_characters / 2) + 128)
        pricing = pricing_for_model(model)
        raw_cost = (
            (Decimal(input_tokens) * pricing.input_per_million)
            + (Decimal(max_output_tokens) * pricing.output_per_million)
        ) / TOKENS_PER_MILLION
        reserved_cost = raw_cost * self.safety_multiplier
        return self._reserve(
            operation=operation,
            model=model,
            reserved_cost_usd=reserved_cost,
            input_tokens_estimate=input_tokens,
            output_tokens_estimate=max_output_tokens,
        )

    def reserve_fixed(
        self, *, model: str, cost_usd: Decimal | float | str, operation: str
    ) -> BudgetReservation:
        """Reserve a fixed amount for an API operation with no token usage."""
        return self._reserve(
            operation=operation,
            model=model,
            reserved_cost_usd=_decimal(cost_usd, field="cost_usd"),
        )

    def _finish(
        self,
        reservation: BudgetReservation,
        *,
        status: str,
        observed_usd: Decimal | None,
        usage: dict[str, int] | None,
        error_type: str | None = None,
    ) -> None:
        with self._thread_lock, self._file_lock():
            ledger = self._read_ledger()
            target = next(
                (
                    call
                    for call in ledger["calls"]
                    if call.get("reservation_id") == reservation.reservation_id
                ),
                None,
            )
            if target is None:
                raise BudgetError(
                    f"Reservation {reservation.reservation_id} is missing from the ledger"
                )
            if target.get("status") != "reserved":
                return

            target["status"] = status
            target["observed_usd"] = _money(observed_usd) if observed_usd is not None else None
            target["usage"] = usage
            target["error_type"] = error_type
            target["completed_at"] = _now()
            if observed_usd is not None:
                observed_total = _decimal(ledger.get("observed_usd"), field="observed_usd")
                ledger["observed_usd"] = _money(observed_total + observed_usd)
            self._write_ledger(ledger)

    def record_chat_response(
        self, reservation: BudgetReservation, response: object
    ) -> Decimal | None:
        """Record provider-reported usage and return its observed cost."""
        usage = _usage_counts(response)
        if usage is None:
            self._finish(reservation, status="completed", observed_usd=None, usage=None)
            return None

        pricing = pricing_for_model(reservation.model)
        observed = (
            (Decimal(usage["input_tokens"]) * pricing.input_per_million)
            + (Decimal(usage["output_tokens"]) * pricing.output_per_million)
        ) / TOKENS_PER_MILLION
        self._finish(
            reservation,
            status="completed",
            observed_usd=observed,
            usage=usage,
        )
        return observed

    def record_failure(self, reservation: BudgetReservation, error: BaseException) -> None:
        """Close a reservation without releasing it, failing closed."""
        self._finish(
            reservation,
            status="failed",
            observed_usd=None,
            usage=None,
            error_type=error.__class__.__name__,
        )

    def record_completion(self, reservation: BudgetReservation) -> None:
        """Close a completed request whose provider exposes no usage fields."""
        self._finish(
            reservation,
            status="completed",
            observed_usd=None,
            usage=None,
        )

    def summary(self) -> dict[str, Any]:
        """Return a safe, prompt-free summary suitable for logs or CI output."""
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
                        "observed_usd": Decimal("0"),
                    },
                )
                bucket["calls"] += 1
                status = call.get("status")
                if status == "completed":
                    bucket["completed_calls"] += 1
                elif status == "failed":
                    bucket["failed_calls"] += 1
                elif status == "reserved":
                    bucket["pending_calls"] += 1
                bucket["reserved_usd"] += _decimal(
                    call.get("reserved_usd", "0"), field="call.reserved_usd"
                )
                if call.get("observed_usd") is not None:
                    bucket["observed_usd"] += _decimal(
                        call["observed_usd"], field="call.observed_usd"
                    )

            for bucket in by_operation.values():
                bucket["reserved_usd"] = _money(bucket["reserved_usd"])
                bucket["observed_usd"] = _money(bucket["observed_usd"])
            return {
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

    def print_summary(self) -> None:
        summary = self.summary()
        print(
            "OpenAI budget: "
            f"reserved ${summary['reserved_usd']} / ${summary['budget_usd']} "
            f"(observed ${summary['observed_usd']}, "
            f"remaining ${summary['remaining_usd']}); "
            f"calls={summary['calls']}"
        )
