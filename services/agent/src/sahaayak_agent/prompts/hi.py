"""Hindi phrases.

Written for the ear rather than the page: these are read aloud by a TTS voice
to callers who may not read Hindi, so the wording favours everyday spoken forms
over formal administrative vocabulary.

Pending native-speaker review before the demo — see docs/spec-v2.md, day 7.
"""

PHRASES: dict[str, str] = {
    "greeting": (
        "नमस्ते। मैं सहायक हूँ। मैं आपको सरकारी योजनाओं, छात्रवृत्ति और नौकरियों "
        "के बारे में बता सकता हूँ। आप किस बारे में जानना चाहते हैं?"
    ),
    "acknowledge": "ठीक है।",
    "didnt_understand": "माफ़ कीजिए, मैं समझ नहीं पाया। कृपया एक बार फिर बताइए।",
    "goodbye": "फ़ोन करने के लिए धन्यवाद। नमस्ते।",
    "ask_intent": "आप सरकारी योजना ढूँढ रहे हैं, छात्रवृत्ति, या नौकरी?",
    "ask_age": "आपकी उम्र कितनी है?",
    "ask_income": "आपके परिवार की साल भर की कुल आमदनी कितनी है?",
    "ask_social_category": (
        "आप किस वर्ग से हैं — एस सी, एस टी, ओ बी सी, ई डब्ल्यू एस, या सामान्य?"
    ),
    "ask_education": "आपने कहाँ तक पढ़ाई की है?",
    "ask_gender": "आप पुरुष हैं, महिला हैं, या अन्य?",
    "ask_occupation": "आप क्या काम करते हैं?",
    "ask_enrollment_mode": "आप नियमित पढ़ाई कर रहे हैं, या दूरस्थ शिक्षा से?",
    "ask_disability": "क्या आपके पास विकलांगता प्रमाण पत्र है?",
    "ask_state_residency": "क्या आप {state} के निवासी हैं?",
    "ask_experience": "आपके पास कितने साल का काम का अनुभव है?",
    "ask_location": "आप किस शहर या ज़िले में काम करना चाहते हैं?",
    "results_intro": "आपने जो बताया, उसके हिसाब से मुझे {count} मिली हैं जिनके लिए आप पात्र हैं।",
    "results_intro_one": "आपने जो बताया, उसके हिसाब से एक मिली है जिसके लिए आप पात्र हैं।",
    "no_matches": (
        "अभी आपकी जानकारी से कोई योजना नहीं मिली। "
        "मैं किसी व्यक्ति से इसकी जाँच करवा सकता हूँ।"
    ),
    "eligible_item": "{name}। इसके लिए आप पात्र हैं। {summary}",
    "ineligible_item": "{name}। इसके लिए आप पात्र नहीं हैं, क्योंकि {reason}।",
    "caveat": "एक बात ध्यान रखिए: {caveat}।",
    "how_to_apply": "आवेदन कैसे करें: {process}",
    "documents_needed": "इसके लिए ये कागज़ात चाहिए: {documents}।",
    "ask_continue": "क्या मैं अगली योजना के बारे में बताऊँ?",
    "escalation_offer": "क्या मैं आपकी बात किसी व्यक्ति से कराऊँ जो मदद कर सके?",
    "escalation_confirmed": (
        "मैंने आपका अनुरोध दर्ज कर लिया है। कोई व्यक्ति आपको इसी नंबर पर वापस फ़ोन करेगा।"
    ),
}
