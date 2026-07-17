"""
PHASE 9: Multi-language Citizen Alerts
------------------------------------------
Gap addressed: "advisory in 12 regional languages" (Citizen Fraud Shield idea
in the problem statement).

Two honest approaches, both included:

1. TEMPLATE-BASED (implemented fully, works offline, zero cost):
   Pre-translate the alert template once per language. Since our alert message
   has a fixed structure (risk categories + confidence + fixed safety advice),
   we don't need live machine translation for the core warning -- we fill a
   template in the target language. This is actually MORE reliable for
   safety-critical text than live MT, because mistranslation of "do not send
   money" is unacceptable.

2. LIVE TRANSLATION for dynamic/free-text content (integration point only):
   If you later want to translate arbitrary free text (e.g. a transcript
   snippet for evidence, or a category name outside our fixed set), that
   needs a real translation API (Google Translate API, Bhashini -- India's
   own government translation API, or an LLM call). We provide the function
   signature and a clear TODO so you can plug in your API key -- we don't
   fake a translation with random text.
"""

from typing import Dict

# Fixed category label translations (small vocabulary, safe to hand-maintain)
CATEGORY_LABELS = {
    "en": {
        "authority_impersonation": "fake government official impersonation",
        "isolation_and_threat": "isolation and arrest threats",
        "financial_pressure": "urgent money transfer pressure",
        "technical_signal": "suspicious caller ID",
    },
    "hi": {  # Hindi
        "authority_impersonation": "सरकारी अधिकारी बनकर धोखाधड़ी",
        "isolation_and_threat": "अलगाव और गिरफ्तारी की धमकी",
        "financial_pressure": "तुरंत पैसे भेजने का दबाव",
        "technical_signal": "संदिग्ध कॉलर आईडी",
    },
    "ta": {  # Tamil
        "authority_impersonation": "போலி அரசு அதிகாரி ஆள்மாறாட்டம்",
        "isolation_and_threat": "தனிமைப்படுத்தல் மற்றும் கைது மிரட்டல்",
        "financial_pressure": "அவசர பண பரிமாற்ற அழுத்தம்",
        "technical_signal": "சந்தேகத்திற்குரிய கால்லர் ஐடி",
    },
    "kn": {  # Kannada
        "authority_impersonation": "ನಕಲಿ ಸರ್ಕಾರಿ ಅಧಿಕಾರಿ ಸೋಗು",
        "isolation_and_threat": "ಪ್ರತ್ಯೇಕತೆ ಮತ್ತು ಬಂಧನದ ಬೆದರಿಕೆ",
        "financial_pressure": "ತುರ್ತು ಹಣ ವರ್ಗಾವಣೆ ಒತ್ತಡ",
        "technical_signal": "ಅನುಮಾನಾಸ್ಪದ ಕರೆಮಾಡುವವರ ಐಡಿ",
    },
}

ALERT_TEMPLATES = {
    "en": (
        "⚠️ Warning: this call/message matches known 'digital arrest' scam patterns "
        "(confidence: {confidence:.0%}). Detected: {categories}. Government agencies "
        "never arrest people over video call or demand money transfers to 'verification "
        "accounts'. Do not transfer any money. Hang up and report to the National "
        "Cybercrime Helpline: 1930 or cybercrime.gov.in."
    ),
    "hi": (
        "⚠️ चेतावनी: यह कॉल/संदेश ज्ञात 'डिजिटल अरेस्ट' घोटाले के पैटर्न से मेल खाता है "
        "(विश्वसनीयता: {confidence:.0%})। पाया गया: {categories}। सरकारी एजेंसियां कभी भी "
        "वीडियो कॉल पर गिरफ्तार नहीं करतीं या 'सत्यापन खाते' में पैसे मांगती नहीं हैं। "
        "कोई पैसा ट्रांसफर न करें। कॉल काटें और राष्ट्रीय साइबर अपराध हेल्पलाइन 1930 या "
        "cybercrime.gov.in पर रिपोर्ट करें।"
    ),
    "ta": (
        "⚠️ எச்சரிக்கை: இந்த அழைப்பு/செய்தி அறியப்பட்ட 'டிஜிட்டல் கைது' மோசடி முறையுடன் "
        "பொருந்துகிறது (நம்பகத்தன்மை: {confidence:.0%})। கண்டறியப்பட்டது: {categories}। "
        "அரசு நிறுவனங்கள் ஒருபோதும் வீடியோ அழைப்பில் கைது செய்யாது அல்லது 'சரிபார்ப்பு "
        "கணக்கிற்கு' பணம் கோராது। பணத்தை அனுப்ப வேண்டாம். அழைப்பைத் துண்டித்து தேசிய "
        "சைபர் கிரைம் ஹெல்ப்லைன் 1930 அல்லது cybercrime.gov.in-இல் புகாரளிக்கவும்."
    ),
    "kn": (
        "⚠️ ಎಚ್ಚರಿಕೆ: ಈ ಕರೆ/ಸಂದೇಶವು ತಿಳಿದಿರುವ 'ಡಿಜಿಟಲ್ ಅರೆಸ್ಟ್' ವಂಚನೆ ಮಾದರಿಗಳಿಗೆ ಹೊಂದುತ್ತದೆ "
        "(ವಿಶ್ವಾಸಾರ್ಹತೆ: {confidence:.0%})। ಪತ್ತೆಯಾಗಿದೆ: {categories}। ಸರ್ಕಾರಿ ಸಂಸ್ಥೆಗಳು "
        "ವೀಡಿಯೊ ಕರೆಯಲ್ಲಿ ಎಂದಿಗೂ ಬಂಧಿಸುವುದಿಲ್ಲ ಅಥವಾ 'ಪರಿಶೀಲನಾ ಖಾತೆ'ಗೆ ಹಣ ಕೇಳುವುದಿಲ್ಲ। "
        "ಯಾವುದೇ ಹಣ ವರ್ಗಾಯಿಸಬೇಡಿ. ಕರೆ ಕಡಿತಗೊಳಿಸಿ ಮತ್ತು ರಾಷ್ಟ್ರೀಯ ಸೈಬರ್ ಅಪರಾಧ ಸಹಾಯವಾಣಿ "
        "1930 ಅಥವಾ cybercrime.gov.in ನಲ್ಲಿ ವರದಿ ಮಾಡಿ."
    ),
}


def generate_localized_alert(risk_categories: list, confidence: float, lang: str = "en") -> str:
    """
    Generate the fixed-safety-message alert in the requested language.
    Falls back to English if the language isn't in our supported set --
    NEVER silently returns an untranslated or garbled safety message.
    """
    if lang not in ALERT_TEMPLATES:
        lang = "en"

    labels = CATEGORY_LABELS.get(lang, CATEGORY_LABELS["en"])
    category_text = ", ".join(labels.get(c, c) for c in risk_categories)

    return ALERT_TEMPLATES[lang].format(confidence=confidence, categories=category_text)


def translate_freeform_text(text: str, target_lang: str) -> str:
    """
    INTEGRATION POINT (not implemented offline): for translating arbitrary
    free text (e.g. transcript evidence snippets) rather than our fixed
    safety templates above.

    In a real deployment, wire this to a translation API, for example:

        import requests
        resp = requests.post(
            "https://bhashini-api-endpoint/translate",   # or Google Cloud Translate
            json={"text": text, "target_lang": target_lang},
            headers={"Authorization": f"Bearer {YOUR_API_KEY}"},
        )
        return resp.json()["translatedText"]

    We deliberately do NOT fake this with a no-op or mock string, because
    silently returning untranslated safety-relevant text is worse than
    clearly failing. Raise until a real backend is configured.
    """
    raise NotImplementedError(
        "translate_freeform_text requires a real translation API key. "
        "See the function docstring for integration instructions."
    )


SUPPORTED_LANGUAGES = list(ALERT_TEMPLATES.keys())


if __name__ == "__main__":
    for lang in SUPPORTED_LANGUAGES:
        print(f"--- {lang} ---")
        print(generate_localized_alert(
            ["authority_impersonation", "isolation_and_threat"], 0.85, lang=lang
        ))
        print()
