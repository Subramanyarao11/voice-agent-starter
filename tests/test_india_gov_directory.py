"""India.gov directory adapter contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx

from scripts.india_gov_directory import IndiaGovDirectoryClient, normalize_records


def test_normalize_records_keeps_scope_and_source_attestation_separate():
    rows = normalize_records(
        state={"state_id": "KA", "stateName": "Karnataka"},
        records=[
            {
                "_organization_type": "E003",
                "orgName": "Departments",
                "title": "Social Welfare Department, Karnataka",
                "url": "https://socialwelfare.karnataka.gov.in",
                "url_1": "https://socialwelfare.karnataka.gov.in/contact",
            },
            {
                "_organization_type": "E042",
                "orgName": "Districts",
                "title": "Mysuru",
                "url": "https://mysuru.nic.in",
            },
        ],
        fetched_at=datetime(2026, 8, 9, tzinfo=UTC),
    )

    assert rows[0]["state_code"] == "KA"
    assert rows[0]["district_name"] == ""
    assert rows[0]["service_domain"] == "citizen_support"
    assert rows[0]["source_url"].endswith("/ka")
    assert rows[0]["website_url"].endswith("/contact")
    assert rows[0]["safe_metadata"]["source_scope"] == "state"
    assert rows[0]["safe_metadata"]["source_snapshot_hash"]
    assert rows[1]["district_name"] == "Mysuru"
    assert rows[1]["department_name"] == "Mysuru District Administration"
    assert rows[1]["safe_metadata"]["source_scope"] == "district"


def test_client_decodes_official_response_shapes_without_live_network():
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        query_type = payload["dataval"]["querytype"]
        if query_type == "All_States":
            return httpx.Response(
                200,
                json={"resultdata": {"data": {"getIgodAllState": {"results": []}}}},
            )
        return httpx.Response(
            200,
            json={
                "resultdata": {
                    "data": {
                        "getIgodWebDirectoryByFilters": {
                            "results": [{"title": "Mysuru", "orgName": "Districts"}]
                        }
                    }
                }
            },
        )

    client = IndiaGovDirectoryClient(transport=httpx.MockTransport(handler))
    try:
        assert client.states() == []
        records = client.state_records("KA", organization_types=("E042",))
    finally:
        client.close()

    assert records[0]["_organization_type"] == "E042"
    assert requests[1]["dataval"]["mustvalue"][-1] == {
        "fieldName": "state_id",
        "fieldValue": "KA",
    }
