"""Governed, code-reviewed profile fact definitions for Household Radar."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, select

from sahaayak_common.ids import new_id
from sahaayak_common.models import ProfileFactDefinition

# These are schema definitions, not benefit data. They describe the smallest
# set of fact types the first household flow may ask about. Sensitive facts
# such as disability and social category are intentionally not enabled by this
# baseline until their purpose copy and policy are reviewed separately.
DEFAULT_HOUSEHOLD_FACT_DEFINITIONS: tuple[dict, ...] = (
    {
        "fact_key": "state_code",
        "scope": "household",
        "data_type": "text",
        "allowed_values": [],
        "validation": {"pattern": "^[A-Z]{2}$"},
        "sensitivity": "personal",
        "allowed_purposes": ["benefit_matching", "routing"],
        "inheritance_allowed": True,
        "reconfirmation_days": 365,
        "question": {
            "en": "Which state should we use for this household?",
            "hi": "इस परिवार के लिए किस राज्य का उपयोग करें?",
            "kn": "ಈ ಕುಟುಂಬಕ್ಕೆ ಯಾವ ರಾಜ್ಯವನ್ನು ಬಳಸಬೇಕು?",
        },
        "help_text": {
            "en": "This helps us show state-specific services and offices.",
            "hi": "इससे राज्य-विशिष्ट सेवाएं और कार्यालय दिखाने में मदद मिलेगी।",
            "kn": "ರಾಜ್ಯ-ನಿರ್ದಿಷ್ಟ ಸೇವೆಗಳು ಮತ್ತು ಕಚೇರಿಗಳನ್ನು ತೋರಿಸಲು ಇದು ಸಹಾಯ ಮಾಡುತ್ತದೆ.",
        },
        "matcher_slot": "state_code",
    },
    {
        "fact_key": "district",
        "scope": "household",
        "data_type": "text",
        "allowed_values": [],
        "validation": {"min_length": 2, "max_length": 120},
        "sensitivity": "personal",
        "allowed_purposes": ["benefit_matching", "routing"],
        "inheritance_allowed": True,
        "reconfirmation_days": 365,
        "question": {
            "en": "Which district is this household in?",
            "hi": "यह परिवार किस जिले में है?",
            "kn": "ಈ ಕುಟುಂಬ ಯಾವ ಜಿಲ್ಲೆಯಲ್ಲಿ ಇದೆ?",
        },
        "help_text": {
            "en": "We use this only for local scheme and department routing.",
            "hi": "इसे केवल स्थानीय योजना और विभाग तक पहुंचाने के लिए उपयोग किया जाता है।",
            "kn": "ಸ್ಥಳೀಯ ಯೋಜನೆ ಮತ್ತು ಇಲಾಖೆಯ ಮಾರ್ಗದರ್ಶನಕ್ಕಾಗಿ ಮಾತ್ರ ಇದನ್ನು ಬಳಸುತ್ತೇವೆ.",
        },
        "matcher_slot": "district",
    },
    {
        "fact_key": "age_band",
        "scope": "member",
        "data_type": "select",
        "allowed_values": ["child", "youth", "adult", "senior"],
        "validation": {},
        "sensitivity": "personal",
        "allowed_purposes": ["benefit_matching", "application_preparation"],
        "inheritance_allowed": False,
        "reconfirmation_days": 365,
        "question": {
            "en": "Which age group is this person in?",
            "hi": "यह व्यक्ति किस आयु वर्ग में है?",
            "kn": "ಈ ವ್ಯಕ್ತಿ ಯಾವ ವಯೋಮಾನದವರು?",
        },
        "help_text": {
            "en": "An age group is enough for discovery; an exact date is not needed.",
            "hi": "योजना खोजने के लिए आयु वर्ग पर्याप्त है; सटीक तारीख की जरूरत नहीं है।",
            "kn": "ಯೋಜನೆಗಳನ್ನು ಹುಡುಕಲು ವಯೋಮಾನ ಸಾಕು; ನಿಖರ ದಿನಾಂಕದ ಅಗತ್ಯವಿಲ್ಲ.",
        },
        "matcher_slot": "age_band",
    },
    {
        "fact_key": "education_level",
        "scope": "member",
        "data_type": "select",
        "allowed_values": [
            "none",
            "primary",
            "secondary",
            "higher_secondary",
            "graduate",
            "postgraduate",
            "vocational",
        ],
        "validation": {},
        "sensitivity": "personal",
        "allowed_purposes": ["benefit_matching", "application_preparation"],
        "inheritance_allowed": False,
        "reconfirmation_days": 730,
        "question": {
            "en": "What is this person's highest education level?",
            "hi": "इस व्यक्ति की उच्चतम शिक्षा का स्तर क्या है?",
            "kn": "ಈ ವ್ಯಕ್ತಿಯ ಗರಿಷ್ಠ ಶಿಕ್ಷಣದ ಮಟ್ಟ ಯಾವುದು?",
        },
        "help_text": {
            "en": "Choose the closest option. You can correct it later.",
            "hi": "सबसे उपयुक्त विकल्प चुनें। आप इसे बाद में ठीक कर सकते हैं।",
            "kn": "ಹತ್ತಿರವಾದ ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ. ನಂತರ ಸರಿಪಡಿಸಬಹುದು.",
        },
        "matcher_slot": "education_level",
    },
    {
        "fact_key": "annual_household_income",
        "scope": "household",
        "data_type": "integer",
        "allowed_values": [],
        "validation": {"min": 0, "max": 100000000},
        "sensitivity": "confidential",
        "allowed_purposes": ["benefit_matching", "application_preparation"],
        "inheritance_allowed": True,
        "reconfirmation_days": 365,
        "question": {
            "en": "What is the approximate annual household income?",
            "hi": "परिवार की अनुमानित वार्षिक आय कितनी है?",
            "kn": "ಕುಟುಂಬದ ಅಂದಾಜು ವಾರ್ಷಿಕ ಆದಾಯ ಎಷ್ಟು?",
        },
        "help_text": {
            "en": "Use an approximate amount. It is stored encrypted and shown masked.",
            "hi": "अनुमानित राशि दें। इसे एन्क्रिप्ट करके रखा जाता है और छिपाकर दिखाया जाता है।",
            "kn": "ಅಂದಾಜು ಮೊತ್ತವನ್ನು ನೀಡಿ. ಇದನ್ನು ಎನ್‌ಕ್ರಿಪ್ಟ್ ಮಾಡಿ, ಮರೆಮಾಡಿ ತೋರಿಸಲಾಗುತ್ತದೆ.",
        },
        "matcher_slot": "annual_household_income",
    },
)


def ensure_household_fact_definitions(db: Session) -> int:
    """Insert the reviewed baseline definitions without overwriting edits."""
    created = 0
    now = datetime.now(UTC)
    for definition_data in DEFAULT_HOUSEHOLD_FACT_DEFINITIONS:
        fact_key = definition_data["fact_key"]
        version = 1
        existing = db.exec(
            select(ProfileFactDefinition).where(
                ProfileFactDefinition.fact_key == fact_key,
                ProfileFactDefinition.version == version,
            )
        ).first()
        if existing is not None:
            continue
        db.add(
            ProfileFactDefinition(
                id=new_id("factdef"),
                version=version,
                review_status="approved",
                reviewed_by="policy-seed-v1",
                reviewed_at=now,
                created_at=now,
                updated_at=now,
                **definition_data,
            )
        )
        created += 1
    return created
