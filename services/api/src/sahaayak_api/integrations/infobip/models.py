"""Wire shapes for the Infobip HTTP surface.

Only the fields Sahaayak actually reads are modelled, and every model ignores
unknown keys. A provider adding a field must never turn into a 500 in a webhook
handler, and modelling their whole schema would be a standing maintenance cost
for data the product does not use.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InfobipStatus(BaseModel):
    """The status block Infobip attaches to sends and delivery reports."""

    model_config = ConfigDict(extra="ignore")

    group_id: int | None = Field(default=None, alias="groupId")
    group_name: str = Field(default="", alias="groupName")
    id: int | None = None
    name: str = ""
    description: str = ""

    @property
    def code(self) -> str:
        return str(self.id) if self.id is not None else ""


class InfobipError(BaseModel):
    model_config = ConfigDict(extra="ignore")

    group_id: int | None = Field(default=None, alias="groupId")
    group_name: str = Field(default="", alias="groupName")
    id: int | None = None
    name: str = ""
    description: str = ""
    permanent: bool | None = None


class InfobipPrice(BaseModel):
    model_config = ConfigDict(extra="ignore")

    price_per_message: float | None = Field(default=None, alias="pricePerMessage")
    currency: str = ""

    def minor_units(self) -> int | None:
        """Convert a decimal price to integer minor units.

        Money is stored as integers because float arithmetic over thousands of
        sub-rupee message charges accumulates error, and a cost report that
        drifts is worse than no cost report.
        """
        if self.price_per_message is None:
            return None
        return int(round(self.price_per_message * 100))


class InfobipMessageResponse(BaseModel):
    """One entry of the `messages` array returned by a send call."""

    model_config = ConfigDict(extra="ignore")

    message_id: str = Field(default="", alias="messageId")
    to: str | Any = ""
    status: InfobipStatus | None = None


class InfobipSendResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bulk_id: str = Field(default="", alias="bulkId")
    messages: list[InfobipMessageResponse] = Field(default_factory=list)

    def first(self) -> InfobipMessageResponse | None:
        return self.messages[0] if self.messages else None


class InfobipRequestError(BaseModel):
    """Infobip's `requestError.serviceException` envelope for 4xx responses."""

    model_config = ConfigDict(extra="ignore")

    message_id: str = Field(default="", alias="messageId")
    text: str = ""

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> InfobipRequestError | None:
        if not isinstance(payload, dict):
            return None
        envelope = payload.get("requestError")
        if not isinstance(envelope, dict):
            return None
        exception = envelope.get("serviceException") or envelope.get("badRequest")
        if not isinstance(exception, dict):
            return None
        return cls.model_validate(exception)


class InfobipDeliveryReport(BaseModel):
    """One delivery report, shared in shape by SMS, WhatsApp, and email."""

    model_config = ConfigDict(extra="ignore")

    message_id: str = Field(default="", alias="messageId")
    bulk_id: str = Field(default="", alias="bulkId")
    to: str | Any = ""
    sent_at: str = Field(default="", alias="sentAt")
    done_at: str = Field(default="", alias="doneAt")
    # Our own opaque correlation value, echoed back by the provider. It is an
    # internal message ID, never anything derived from the destination.
    callback_data: str = Field(default="", alias="callbackData")
    status: InfobipStatus | None = None
    error: InfobipError | None = None
    price: InfobipPrice | None = None


class InfobipDeliveryReportBatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    results: list[InfobipDeliveryReport] = Field(default_factory=list)
