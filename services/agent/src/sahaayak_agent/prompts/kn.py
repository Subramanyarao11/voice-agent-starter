"""Kannada phrases.

Written for the ear rather than the page: these are read aloud by a TTS voice
to callers who may not read Kannada, so the wording favours everyday spoken
forms over formal administrative vocabulary.

Pending native-speaker review before the demo — see docs/spec-v2.md, day 7.
"""

REVIEW_STATUS = "review_required"

PHRASES: dict[str, str] = {
    "greeting": (
        "ನಮಸ್ಕಾರ. ನಾನು ಸಹಾಯಕ. ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು, ವಿದ್ಯಾರ್ಥಿವೇತನ ಮತ್ತು ಉದ್ಯೋಗಗಳ ಬಗ್ಗೆ "
        "ನಾನು ಮಾಹಿತಿ ನೀಡಬಲ್ಲೆ. ನಿಮಗೆ ಯಾವುದರ ಬಗ್ಗೆ ತಿಳಿಯಬೇಕು?"
    ),
    "acknowledge": "ಸರಿ.",
    "didnt_understand": "ಕ್ಷಮಿಸಿ, ನನಗೆ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಇನ್ನೊಮ್ಮೆ ಹೇಳಿ.",
    "goodbye": "ಕರೆ ಮಾಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು. ನಮಸ್ಕಾರ.",
    "ask_intent": "ನೀವು ಸರ್ಕಾರಿ ಯೋಜನೆ ಹುಡುಕುತ್ತಿದ್ದೀರಾ, ವಿದ್ಯಾರ್ಥಿವೇತನವೇ, ಅಥವಾ ಉದ್ಯೋಗವೇ?",
    "knowledge_unavailable": (
        "ಈಗ ಮೂಲ ದಾಖಲೆಗಳನ್ನು ಪ್ರವೇಶಿಸಲು ಸಾಧ್ಯವಾಗುತ್ತಿಲ್ಲ. ಯೋಜನೆಯ ಹೆಸರನ್ನು ಹೇಳಿದರೆ "
        "ಅಥವಾ ಯೋಜನೆ ಹುಡುಕಲು ಕೇಳಿದರೆ ನಾನು ಸಹಾಯ ಮಾಡಬಹುದು."
    ),
    "ask_age": "ನಿಮ್ಮ ವಯಸ್ಸು ಎಷ್ಟು?",
    "ask_income": "ನಿಮ್ಮ ಕುಟುಂಬದ ವರ್ಷದ ಒಟ್ಟು ಆದಾಯ ಎಷ್ಟು?",
    "ask_social_category": (
        "ನೀವು ಯಾವ ವರ್ಗಕ್ಕೆ ಸೇರಿದವರು — ಎಸ್ ಸಿ, ಎಸ್ ಟಿ, ಒ ಬಿ ಸಿ, ಇ ಡಬ್ಲ್ಯು ಎಸ್, ಅಥವಾ ಸಾಮಾನ್ಯ?"
    ),
    "ask_education": "ನೀವು ಎಷ್ಟರವರೆಗೆ ಓದಿದ್ದೀರಿ?",
    "ask_gender": "ನೀವು ಪುರುಷರೇ, ಮಹಿಳೆಯೇ, ಅಥವಾ ಇತರರೇ?",
    "ask_occupation": "ನೀವು ಯಾವ ಕೆಲಸ ಮಾಡುತ್ತೀರಿ?",
    "ask_enrollment_mode": "ನೀವು ನಿಯಮಿತವಾಗಿ ಓದುತ್ತಿದ್ದೀರಾ, ಅಥವಾ ದೂರಶಿಕ್ಷಣದ ಮೂಲಕವೇ?",
    "ask_disability": "ನಿಮ್ಮ ಬಳಿ ವಿಕಲಚೇತನ ಪ್ರಮಾಣಪತ್ರ ಇದೆಯೇ?",
    "ask_state_residency": "ನೀವು {state} ನಿವಾಸಿಯೇ?",
    "ask_experience": "ನಿಮಗೆ ಎಷ್ಟು ವರ್ಷಗಳ ಕೆಲಸದ ಅನುಭವ ಇದೆ?",
    "ask_location": "ನೀವು ಯಾವ ಊರಿನಲ್ಲಿ ಅಥವಾ ಜಿಲ್ಲೆಯಲ್ಲಿ ಕೆಲಸ ಮಾಡಲು ಬಯಸುತ್ತೀರಿ?",
    "results_intro": "ನೀವು ಹೇಳಿದ ಮಾಹಿತಿಯ ಪ್ರಕಾರ, ನಿಮಗೆ ಅರ್ಹತೆ ಇರುವ {count} ಸಿಕ್ಕಿವೆ.",
    "results_intro_one": "ನೀವು ಹೇಳಿದ ಮಾಹಿತಿಯ ಪ್ರಕಾರ, ನಿಮಗೆ ಅರ್ಹತೆ ಇರುವ ಒಂದು ಸಿಕ್ಕಿದೆ.",
    "no_matches": (
        "ಈಗ ನಿಮ್ಮ ಮಾಹಿತಿಗೆ ಹೊಂದುವ ಯೋಜನೆ ಸಿಗಲಿಲ್ಲ. "
        "ನಾನು ಒಬ್ಬ ವ್ಯಕ್ತಿಯಿಂದ ಇದನ್ನು ಪರಿಶೀಲಿಸಿ ಹೇಳಿಸಬಲ್ಲೆ."
    ),
    "need_more_details": (
        "ಸಂಬಂಧಿತ {count} ಆಯ್ಕೆಗಳು ಸಿಕ್ಕಿವೆ. ಯಾವುದಕ್ಕೆ ಅರ್ಹತೆ ಇದೆ ಎಂದು ಖಚಿತಪಡಿಸಲು ಇನ್ನೂ ಕೆಲವು ವಿವರಗಳು ಬೇಕು."
    ),
    "related_options": (
        "ಸಂಬಂಧಿತ {count} ಆಯ್ಕೆಗಳು ಸಿಕ್ಕಿವೆ, ಆದರೆ ನೀವು ನೀಡಿದ ಮಾಹಿತಿಯಿಂದ ಯಾವುದಕ್ಕೂ ಅರ್ಹತೆ ಖಚಿತವಾಗಿಲ್ಲ. "
        "ಪ್ರತಿ ಆಯ್ಕೆಯೊಂದಿಗೆ ನೀಡಿರುವ ಕಾರಣಗಳನ್ನು ನೋಡಿ, ಅಥವಾ ಒಂದು ಯೋಜನೆಯ ಹೆಸರು ಹೇಳಿ ಕೇಳಿ."
    ),
    "eligible_item": "{name}. ಇದಕ್ಕೆ ನಿಮಗೆ ಅರ್ಹತೆ ಇದೆ. {summary}",
    "ineligible_item": "{name}. ಇದಕ್ಕೆ ನಿಮಗೆ ಅರ್ಹತೆ ಇಲ್ಲ, ಏಕೆಂದರೆ {reason}.",
    "caveat": "ಒಂದು ವಿಷಯ ಗಮನಿಸಿ: {caveat}.",
    "how_to_apply": "ಅರ್ಜಿ ಸಲ್ಲಿಸುವ ವಿಧಾನ: {process}",
    "documents_needed": "ಇದಕ್ಕೆ ಈ ದಾಖಲೆಗಳು ಬೇಕು: {documents}.",
    "ask_continue": "ಮುಂದಿನದರ ಬಗ್ಗೆ ಹೇಳಲೇ?",
    "escalation_offer": "ಸಹಾಯ ಮಾಡಬಲ್ಲ ಒಬ್ಬ ವ್ಯಕ್ತಿಯ ಜೊತೆ ನಿಮ್ಮನ್ನು ಮಾತನಾಡಿಸಲೇ?",
    "escalation_confirmed": (
        "ನಿಮ್ಮ ಕೋರಿಕೆಯನ್ನು ದಾಖಲಿಸಿದ್ದೇನೆ. ಒಬ್ಬರು ಇದೇ ಸಂಖ್ಯೆಗೆ ಮರಳಿ ಕರೆ ಮಾಡುತ್ತಾರೆ."
    ),
}
