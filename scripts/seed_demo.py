"""Seed a small illustrative dataset so the agent is runnable before ingestion.

This is scaffolding for development and tests, not a substitute for the
pipeline. The entries are modelled on real schemes and carry their real source
URLs, but the eligibility values were hand-entered rather than extracted and
verified, so they must not be presented as authoritative. Anything shown to a
real caller should come from scripts 01 to 06.

Usage:
    python scripts/seed_demo.py
    python scripts/seed_demo.py --reset
"""

from __future__ import annotations

import argparse
from datetime import date

from sqlmodel import select

from sahaayak_agent.bootstrap import ensure_reference_data
from sahaayak_common import Benefit, init_db, session_scope
from sahaayak_contracts import Domain, VerificationStatus

DEMO_BENEFITS: list[dict] = [
    {
        "id": "demo-csss-cus",
        "domain": Domain.SCHOLARSHIP,
        "name": "Central Sector Scheme of Scholarship for College and University Students",
        "state_code": None,
        "category": "Education & Learning",
        "description": "A central scholarship for students in undergraduate or "
        "postgraduate study whose family income is below the limit.",
        "eligibility_initial": {
            "age_min": 18,
            "age_max": 25,
            "max_annual_family_income_inr": 450000,
            "education_level": ["UG", "PG"],
            "enrollment_mode": ["regular"],
            "exclusions": ["already receiving another central scholarship"],
        },
        "benefits_text": "Rupees 12,000 per year for undergraduate study and "
        "Rupees 20,000 per year for postgraduate study.",
        "documents_required": [
            "Aadhaar card",
            "Income certificate",
            "Class 12 marksheet",
            "Bank account details",
        ],
        "application_process": "Apply on the National Scholarship Portal at scholarships.gov.in.",
        "source_url": "https://www.myscheme.gov.in/schemes/csss-cus",
        "localized_summary": {
            "en": "Rupees 12,000 a year for college students from lower-income families.",
            "hi": "कम आमदनी वाले परिवारों के कॉलेज विद्यार्थियों के लिए साल में बारह हज़ार रुपये।",
            "kn": "ಕಡಿಮೆ ಆದಾಯದ ಕುಟುಂಬಗಳ ಕಾಲೇಜು ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ವರ್ಷಕ್ಕೆ ಹನ್ನೆರಡು ಸಾವಿರ ರೂಪಾಯಿ.",
        },
    },
    {
        "id": "demo-post-matric-sc",
        "domain": Domain.SCHOLARSHIP,
        "name": "Post Matric Scholarship for Scheduled Caste Students",
        "state_code": None,
        "category": "Education & Learning",
        "description": "Support for Scheduled Caste students continuing study after Class 10.",
        "eligibility_initial": {
            "max_annual_family_income_inr": 250000,
            "category": ["SC"],
            "min_education_level": "class_10",
            "enrollment_mode": ["regular"],
        },
        "benefits_text": "Course fees plus a monthly maintenance allowance.",
        "documents_required": ["Caste certificate", "Income certificate", "Admission proof"],
        "application_process": "Apply on the National Scholarship Portal at scholarships.gov.in.",
        "source_url": "https://www.myscheme.gov.in/schemes/pmsss",
        "localized_summary": {
            "en": "Fees and a monthly allowance for Scheduled Caste students after Class 10.",
            "hi": "दसवीं के बाद पढ़ने वाले अनुसूचित जाति के विद्यार्थियों के लिए फीस और मासिक भत्ता।",
            "kn": "ಹತ್ತನೇ ತರಗತಿಯ ನಂತರ ಓದುವ ಪರಿಶಿಷ್ಟ ಜಾತಿ ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ಶುಲ್ಕ ಮತ್ತು ಮಾಸಿಕ ಭತ್ಯೆ.",
        },
    },
    {
        "id": "demo-ka-vidyasiri",
        "domain": Domain.SCHOLARSHIP,
        "name": "Karnataka Vidyasiri Scholarship",
        "state_code": "KA",
        "category": "Education & Learning",
        "description": "Karnataka state support for hostel and food costs for "
        "backward-class students.",
        "eligibility_initial": {
            "max_annual_family_income_inr": 250000,
            "category": ["SC", "ST", "OBC"],
            "state_residency_required": True,
            "min_education_level": "class_10",
            "exclusions": ["already staying in a government hostel"],
        },
        "benefits_text": "A monthly food and accommodation allowance for ten months a year.",
        "documents_required": ["Caste certificate", "Income certificate", "Domicile certificate"],
        "application_process": "Apply through the State Scholarship Portal or your taluk office.",
        "source_url": "https://www.myscheme.gov.in/schemes/vidyasiri",
        "localized_summary": {
            "en": "Monthly hostel and food support for backward-class students in Karnataka.",
            "hi": "कर्नाटक में पिछड़े वर्ग के विद्यार्थियों के लिए हर महीने छात्रावास और भोजन की मदद।",
            "kn": "ಕರ್ನಾಟಕದ ಹಿಂದುಳಿದ ವರ್ಗದ ವಿದ್ಯಾರ್ಥಿಗಳಿಗೆ ಪ್ರತಿ ತಿಂಗಳು ವಸತಿ ಮತ್ತು ಊಟದ ನೆರವು.",
        },
    },
    {
        "id": "demo-pm-kisan",
        "domain": Domain.SCHEME,
        "name": "Pradhan Mantri Kisan Samman Nidhi",
        "state_code": None,
        "category": "Agriculture",
        "description": "Income support paid directly to land-holding farmer families.",
        "eligibility_initial": {
            "age_min": 18,
            "occupation": ["farmer"],
            "exclusions": [
                "income tax payers in the last assessment year",
                "serving or retired government employees above Group D",
            ],
        },
        "benefits_text": "Rupees 6,000 a year, paid in three instalments straight to a "
        "bank account.",
        "documents_required": ["Aadhaar card", "Land records", "Bank account details"],
        "application_process": "Register at pmkisan.gov.in or at your nearest "
        "Common Service Centre.",
        "source_url": "https://www.myscheme.gov.in/schemes/pm-kisan",
        "localized_summary": {
            "en": "Rupees 6,000 a year paid directly to farming families who own land.",
            "hi": "ज़मीन वाले किसान परिवारों को सीधे खाते में साल के छह हज़ार रुपये।",
            "kn": "ಜಮೀನು ಇರುವ ರೈತ ಕುಟುಂಬಗಳಿಗೆ ನೇರವಾಗಿ ಖಾತೆಗೆ ವರ್ಷಕ್ಕೆ ಆರು ಸಾವಿರ ರೂಪಾಯಿ.",
        },
    },
    {
        "id": "demo-igndps",
        "domain": Domain.SCHEME,
        "name": "Indira Gandhi National Old Age Pension Scheme",
        "state_code": None,
        "category": "Social Welfare",
        "description": "A monthly pension for older people from below-poverty-line households.",
        "eligibility_initial": {
            "age_min": 60,
            "max_annual_family_income_inr": 100000,
        },
        "benefits_text": "A monthly pension, with a higher rate from age 80.",
        "documents_required": ["Aadhaar card", "Age proof", "BPL card"],
        "application_process": "Apply at your gram panchayat or municipal office.",
        "source_url": "https://www.myscheme.gov.in/schemes/ignoaps",
        "localized_summary": {
            "en": "A monthly pension for people aged 60 and over from poor households.",
            "hi": "गरीब परिवारों के साठ साल से ऊपर के लोगों के लिए हर महीने पेंशन।",
            "kn": "ಬಡ ಕುಟುಂಬಗಳ ಅರವತ್ತು ವರ್ಷ ಮೇಲ್ಪಟ್ಟವರಿಗೆ ಪ್ರತಿ ತಿಂಗಳು ಪಿಂಚಣಿ.",
        },
    },
    {
        "id": "demo-ka-anganwadi-helper",
        "domain": Domain.JOB,
        "name": "Anganwadi Helper Recruitment, Karnataka",
        "state_code": "KA",
        "category": "Government Jobs",
        "description": "District-level recruitment of Anganwadi helpers under the "
        "Women and Child Development Department.",
        "eligibility_initial": {
            "age_min": 19,
            "age_max": 35,
            "gender": "female",
            "min_education_level": "class_10",
            "state_residency_required": True,
            "locations": ["Karnataka"],
        },
        "benefits_text": "A monthly honorarium set by the state government.",
        "documents_required": ["Class 10 marksheet", "Domicile certificate", "Aadhaar card"],
        "application_process": "Apply through the district Women and Child Development office "
        "when a notification is published.",
        "source_url": "https://www.myscheme.gov.in/",
        "localized_summary": {
            "en": "Anganwadi helper posts for women in Karnataka who have passed Class 10.",
            "hi": "कर्नाटक में दसवीं पास महिलाओं के लिए आंगनवाड़ी सहायिका के पद।",
            "kn": "ಹತ್ತನೇ ತರಗತಿ ಪಾಸಾದ ಕರ್ನಾಟಕದ ಮಹಿಳೆಯರಿಗೆ ಅಂಗನವಾಡಿ ಸಹಾಯಕಿ ಹುದ್ದೆಗಳು.",
        },
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true", help="delete existing demo rows before seeding"
    )
    args = parser.parse_args()

    init_db()
    ensure_reference_data()

    with session_scope() as db:
        if args.reset:
            for row in db.exec(select(Benefit).where(Benefit.id.startswith("demo-"))).all():
                db.delete(row)

        for entry in DEMO_BENEFITS:
            db.merge(
                Benefit(
                    **entry,
                    eligibility_renewal=None,
                    last_verified_date=date.today(),
                    verification_status=VerificationStatus.ILLUSTRATIVE,
                    source_title="myScheme reference (illustrative demo)",
                    source_document_url=entry.get("source_url", ""),
                    is_active=True,
                )
            )

    print(f"Seeded {len(DEMO_BENEFITS)} illustrative benefits.")
    print(
        "These are hand-entered for development. Run the ingestion pipeline "
        "(scripts 01-06) for data that is actually sourced and verified."
    )


if __name__ == "__main__":
    main()
