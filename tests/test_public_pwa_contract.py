"""Public projection/cache headers used by the safe PWA layer."""

from sqlmodel import select

from sahaayak_common import Benefit, session_scope
from sahaayak_contracts import VerificationStatus


def test_public_catalog_is_reviewed_only_and_explicitly_cacheable(client):
    with session_scope() as db:
        benefit = db.exec(select(Benefit).where(Benefit.id == "demo-csss-cus")).one()
        benefit.verification_status = VerificationStatus.HUMAN_VERIFIED
        db.add(benefit)

    response = client.get("/api/public/catalog?state_code=KA&limit=20")
    assert response.status_code == 200
    assert response.headers["x-sahaayak-cache-class"] == "public-reviewed-v1"
    assert "public" in response.headers["cache-control"]
    assert response.headers["etag"]
    assert all(
        item["verification_status"] == "human_verified"
        for item in response.json()["benefits"]
    )
    assert all("source_document_url" in item for item in response.json()["benefits"])

    detail = client.get("/api/public/benefits/demo-csss-cus")
    assert detail.status_code == 200
    assert detail.headers["x-sahaayak-cache-class"] == "public-reviewed-v1"
    assert detail.json()["id"] == "demo-csss-cus"


def test_public_benefit_detail_does_not_expose_unreviewed_rows(client):
    with session_scope() as db:
        benefit = db.exec(select(Benefit).where(Benefit.id == "demo-pm-kisan")).one()
        benefit.verification_status = VerificationStatus.ILLUSTRATIVE
        db.add(benefit)

    response = client.get("/api/public/benefits/demo-pm-kisan")
    assert response.status_code == 404
