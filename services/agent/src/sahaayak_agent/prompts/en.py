"""English phrases. This is the reference catalog every other language mirrors.

Keys are stable identifiers referenced by the slot registry and the response
composer. A translation is a new dictionary with the same keys — never a new
code path.
"""

REVIEW_STATUS = "reference"

PHRASES: dict[str, str] = {
    # --- Conversation frame ---
    "greeting": (
        "Namaste. I can help you find government schemes, scholarships, and jobs "
        "you may qualify for. What would you like to know about?"
    ),
    "acknowledge": "Got it.",
    "didnt_understand": "Sorry, I did not catch that. Could you say it again?",
    "goodbye": "Thank you for calling. Namaste.",
    "ask_intent": (
        "Are you looking for a government scheme, a scholarship, or a job?"
    ),
    "knowledge_unavailable": (
        "I cannot access the source documents right now. I can still help you "
        "check a scheme if you tell me its name or ask for a benefit search."
    ),
    # --- Slot questions, keyed by SlotSpec.prompt_key ---
    "ask_age": "How old are you?",
    "ask_income": "What is your family's total yearly income?",
    "ask_social_category": (
        "Which category do you belong to — SC, ST, OBC, EWS, or General?"
    ),
    "ask_education": "How far have you studied?",
    "ask_gender": "Are you male, female, or other?",
    "ask_occupation": "What work do you do?",
    "ask_enrollment_mode": "Are you studying full time, or through distance learning?",
    "ask_disability": "Do you have a disability certificate?",
    "ask_state_residency": "Are you a resident of {state}?",
    "ask_experience": "How many years of work experience do you have?",
    "ask_location": "Which city or district would you like to work in?",
    # --- Results ---
    "results_intro": "Based on what you told me, I found {count} that you qualify for.",
    "results_intro_one": "Based on what you told me, I found one that you qualify for.",
    "no_matches": (
        "I could not find anything matching your details right now. "
        "I can have someone look into this for you."
    ),
    "related_options": (
        "I found {count} related options, but none is a confirmed eligibility match "
        "from the details I have. Review the reasons shown with each option, or I can "
        "have a person help you check them."
    ),
    "eligible_item": "{name}. You qualify for this. {summary}",
    "ineligible_item": "{name}. You do not qualify because {reason}.",
    "caveat": "One condition to check: {caveat}.",
    "how_to_apply": "To apply: {process}",
    "documents_needed": "You will need these documents: {documents}.",
    "ask_continue": "Would you like to hear about the next one?",
    # --- Escalation ---
    "escalation_offer": "Shall I connect you to a person who can help?",
    "escalation_confirmed": (
        "I have noted your request. Someone will call you back on this number."
    ),
}
