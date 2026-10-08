"""Fixed server-side messages in the UI languages.

Cost decision: these are static, so no Translate/LLM call is ever spent on them.
Languages outside this table fall back to English.
"""

from __future__ import annotations

from .textutil import base_lang

_MESSAGES = {
    "rate_limited": {
        "en": "I'm receiving too many requests right now. Please wait a few seconds and try again.",
        "hi": "अभी बहुत अधिक अनुरोध आ रहे हैं। कृपया कुछ सेकंड प्रतीक्षा करें और फिर कोशिश करें।",
        "fr": "Je reçois trop de demandes en ce moment. Veuillez patienter quelques secondes et réessayer.",
        "de": "Ich erhalte gerade zu viele Anfragen. Bitte warte ein paar Sekunden und versuche es erneut.",
        "es": "Estoy recibiendo demasiadas solicitudes. Espera unos segundos e inténtalo de nuevo.",
        "ta": "இப்போது அதிகமான கோரிக்கைகள் வருகின்றன. சில விநாடிகள் காத்திருந்து மீண்டும் முயற்சிக்கவும்.",
    },
    "location_not_found": {
        "en": "I couldn't find that location. Please check the spelling or try a nearby city.",
        "hi": "मुझे वह स्थान नहीं मिला। कृपया वर्तनी जाँचें या किसी पास के शहर को आज़माएँ।",
        "fr": "Je n'ai pas trouvé ce lieu. Vérifiez l'orthographe ou essayez une ville voisine.",
        "de": "Ich konnte diesen Ort nicht finden. Prüfe die Schreibweise oder versuche eine nahe Stadt.",
        "es": "No encontré ese lugar. Revisa la ortografía o prueba con una ciudad cercana.",
        "ta": "அந்த இடத்தை என்னால் கண்டுபிடிக்க முடியவில்லை. எழுத்துப்பிழையைச் சரிபார்க்கவும் அல்லது அருகிலுள்ள நகரத்தை முயற்சிக்கவும்.",
    },
    "agent_unavailable": {
        "en": "The weather assistant is temporarily unavailable. Please try again shortly.",
        "hi": "मौसम सहायक अभी अस्थायी रूप से उपलब्ध नहीं है। कृपया थोड़ी देर में फिर कोशिश करें।",
        "fr": "L'assistant météo est temporairement indisponible. Veuillez réessayer dans un instant.",
        "de": "Der Wetterassistent ist vorübergehend nicht verfügbar. Bitte versuche es gleich noch einmal.",
        "es": "El asistente del tiempo no está disponible temporalmente. Inténtalo de nuevo en breve.",
        "ta": "வானிலை உதவியாளர் தற்காலிகமாகக் கிடைக்கவில்லை. சிறிது நேரத்தில் மீண்டும் முயற்சிக்கவும்.",
    },
    "no_answer": {
        "en": "I couldn't put together an answer for that. Could you rephrase your question?",
        "hi": "मैं इसका उत्तर तैयार नहीं कर सका। क्या आप अपना प्रश्न दूसरे शब्दों में पूछ सकते हैं?",
        "fr": "Je n'ai pas pu formuler de réponse. Pouvez-vous reformuler votre question ?",
        "de": "Ich konnte dazu keine Antwort formulieren. Kannst du deine Frage umformulieren?",
        "es": "No pude preparar una respuesta. ¿Puedes reformular tu pregunta?",
        "ta": "இதற்கு என்னால் பதில் தயாரிக்க முடியவில்லை. உங்கள் கேள்வியை வேறு விதமாகக் கேட்க முடியுமா?",
    },
}


def t(key: str, lang: str | None) -> str:
    table = _MESSAGES[key]
    return table.get(base_lang(lang), table["en"])
