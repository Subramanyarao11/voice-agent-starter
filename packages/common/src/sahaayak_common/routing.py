"""Safe default routing for human handoffs.

The application can route a ticket by the caller's state, domain, and stated
location without pretending that it knows the current government directory.
An operator can replace this fallback on the ticket, and the source field is
kept so later directory integrations can be measured separately.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sahaayak_contracts import Domain

_STATE_NAMES = {
    "AP": "Andhra Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CG": "Chhattisgarh",
    "DL": "Delhi",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UK": "Uttarakhand",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal",
    "JK": "Jammu and Kashmir",
    "LA": "Ladakh",
    "PY": "Puducherry",
    "CH": "Chandigarh",
    "AN": "Andaman and Nicobar Islands",
    "GA": "Goa",
    "DN": "Dadra and Nagar Haveli and Daman and Diu",
    "AR": "Arunachal Pradesh",
    "CT": "Chhattisgarh",
}

_DOMAIN_LABELS = {
    Domain.SCHEME: "welfare schemes helpdesk",
    Domain.SCHOLARSHIP: "education and scholarships helpdesk",
    Domain.JOB: "employment and careers helpdesk",
}


@dataclass(frozen=True)
class EscalationRoute:
    department: str
    routing_location: str
    routing_source: str


def resolve_escalation_route(
    *,
    state_code: str | None,
    domain: Domain | None,
    slots: Mapping[object, object] | None = None,
) -> EscalationRoute:
    """Return a bounded, explainable fallback route.

    `location` is only a caller-stated city/district value. It is never
    geocoded or treated as a verified pincode, so the operator must confirm
    the destination before a real handoff.
    """

    normalized_state = (state_code or "").strip().upper()
    state_name = _STATE_NAMES.get(normalized_state, "National")
    label = _DOMAIN_LABELS.get(domain, "citizen-support helpdesk")
    department = f"{state_name} {label}"

    location = ""
    for key, value in (slots or {}).items():
        key_value = getattr(key, "value", key)
        if key_value == "location" and value is not None:
            location = str(value).strip()[:120]
            break

    return EscalationRoute(
        department=department[:160],
        routing_location=location,
        routing_source="state_domain_fallback",
    )
