"""Localised names for the subjects shipped with the question bank.

Subject ids and codes are the stable identity.  The English ``Subject.name`` stays
canonical; these rows only provide display names for the supported Indian languages.
Keeping the catalogue in code makes the initial question bank useful immediately after
seeding, while the translation tables still allow an examiner to replace any label later.
"""

# Localised labels are one-line script data; keeping each locale on its own line makes the
# catalogue reviewable, while the project's 100-column limit would otherwise force the
# translations into unreadable string concatenation.
# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.db.models import Subject
from app.db.models.translations import SubjectTranslation
from app.db.session import SessionLocal
from app.services.i18n import upsert_translations

logger = get_logger("subject-translations")

#: Canonical subject code -> locale -> localised subject name.
SUBJECT_NAME_TRANSLATIONS: dict[str, dict[str, str]] = {
    "PY101": {"ml": "പൈത്തൺ", "ta": "பைத்தான்", "hi": "पाइथन", "kn": "ಪೈಥನ್", "te": "పైథాన్"},
    "CS101": {"ml": "കമ്പ്യൂട്ടർ സയൻസിന്റെ അടിപ്പാദങ്ങൾ", "ta": "கணினி அறிவியலின் அடிப்படைகள்", "hi": "कंप्यूटर विज्ञान के मूल विषय", "kn": "ಕಂಪ್ಯೂಟರ್ ಸೈನ್ಸ್‌ನ ಮೂಲಾಂಶಗಳು", "te": "కంప్యూటర్ సైన్స్ ప్రాథమిక అంశాలు"},
    "CS102": {"ml": "ഡാറ്റാ ഘടനകളും അൽഗോറിതമുകളും", "ta": "தரவுக் கட்டமைப்புகளும் அல்கோரிதம்களும்", "hi": "डेटा संरचनाएँ और एल्गोरिदम", "kn": "ಡೇಟಾ ರಚನೆಗಳು ಮತ್ತು ಅಲ್ಗೋರಿದಮ್‌ಗಳು", "te": "డేటా స్ట్రక్చర్లు మరియు అల్గోరిథమ్‌లు"},
    "CS201": {"ml": "ഡാറ്റാബേസ് മാനേജ്മെന്റ് സിസ്റ്റംസ്", "ta": "தரவகள்வு மேலாண்மைத் தொகுதிகள்", "hi": "डेटाबेस प्रबंधन प्रणालियाँ", "kn": "ಡೇಟಾಬೇಸ್ ನಿರ್ವಹಣಾ ವ್ಯವಸ್ಥೆಗಳು", "te": "డేటాబేస్ నిర్వహణ వ్యవస్థలు"},
    "CS202": {"ml": "ഓപ്പറേറ്റിംഗ് സിസ്റ്റംസ്", "ta": "இயக்க முறைகள்", "hi": "ऑपरेटिंग सिस्टम", "kn": "ಆಪರೇಟಿಂಗ್ ಸಿಸ್ಟಂಗ್‌ಗಳು", "te": "ఆపరేటింగ్ సిస్టమ్స్"},
    "CS203": {"ml": "കമ്പ്യൂട്ടർ നെറ്റ്‌വർക്കുകൾ", "ta": "கணினி வலைப்பின்னல்கள்", "hi": "कंप्यूटर नेटवर्क", "kn": "ಕಂಪ್ಯೂಟರ್ ನೆಟ್‌ವರ್ಕ್‌ಗಳು", "te": "కంప్యూటర్ నెట్‌వర్క్‌లు"},
    "CS301": {"ml": "വെബ് & സോഫ്റ്റ്‌വെയർ എഞ്ചിനീയറിംഗ്", "ta": "இணைய & மென்பொருள் பொறியியல்", "hi": "वेब और सॉफ़्टवेयर इंजीनियरिंग", "kn": "ವೆಬ್ ಮತ್ತು ಸಾಫ್ಟ್‌ವೇರ್ ಎಂಜಿನಿಯರಿಂಗ್", "te": "వెబ్ & సాఫ్ట్‌వేర్ ఇంజనీరింగ్"},
    "MATH101": {"ml": "എഞ്ചിനീയറിംഗ് ഗണിതം", "ta": "பொறியியல் கணிதம்", "hi": "अभियांत्रिकी गणित", "kn": "ಎಂಜಿನಿಯರಿಂಗ್ ಗಣಿತ", "te": "ఇంజనీరింగ్ గణితం"},
    "SQL101": {"ml": "SQL & ഡാറ്റാബേസുകൾ", "ta": "SQL & தரவகளங்கள்", "hi": "SQL और डेटाबेस", "kn": "SQL ಮತ್ತು ಡೇಟಾಬೇಸ್‌ಗಳು", "te": "SQL & డేటాబేస్‌లు"},
    "ML101": {"ml": "യന്ത്ര പഠനം", "ta": "இயந்தக் கற்றல்", "hi": "मशीन लर्निंग", "kn": "ಯಂತ್ರಾಲೋಕ ಕಲಿಕೆ", "te": "యంత్ర నేర్చుకోవడం"},
    "NLP101": {"ml": "നാച്ചുറൽ ഭാഷാ പ്രോസസിംഗ്", "ta": "இயற்கை மொழி செயலாக்கம்", "hi": "प्राकृतिक भाषा प्रसंस्करण", "kn": "ನೈಸರ್ಗಿಕ ಭಾಷಾ ಸಂಸ್ಕರಣೆ", "te": "సహజ భాషా ప్రాసెసింగ్"},
    "AI101": {"ml": "കൃതക ബുദ്ധിമത്ത", "ta": "செயற்கை அறிவு", "hi": "कृत्रिम बुद्धिमत्ता", "kn": "ಕೃತಕ ಬುದ್ಧಿಮತ್ತೆ", "te": "కృత్రిమ మేధస్సు"},
    "DL101": {"ml": "ആഴമുളള പഠനം", "ta": "ஆழ்கற்றல்", "hi": "डीप लर्निंग", "kn": "ಆಳವಾದ ಕಲಿಕೆ", "te": "డీప్ లెర్నింగ్"},
    "APT101": {"ml": "അളിയാക്കുന്ന അപ്ടിയൂഡ്", "ta": "அளவில்லா திறன்", "hi": "संख्यात्मक अभिरुचि", "kn": "ಸಂಖ್ಯಾತ್ಮಕ ಸಾಮರ್ಥ್ಯ", "te": "పరిమాణాత్మక సామర్థ్యం"},
    "LOG101": {"ml": "താർക്കിക ചിന്തനിരത", "ta": "தர்க்க ரீசனிங்", "hi": "तार्किक तर्क", "kn": "ತಾರ್ಕಿಕ ತರ್ಕೋಟಟಿ", "te": "తార్కిక చార్చన"},
    "VRB101": {"ml": "വാക്കാക്ഷമതയും ഇംഗ്ലീഷും", "ta": "சொற்கள் திறனும் ஆங்கிலமும்", "hi": "शाब्दिक क्षमता और अंग्रेज़ी", "kn": "ಪದಕ್ಷಮತೆ ಮತ್ತು ಇಂಗ್ಲಿಷ್", "te": "వాక్య సామర్థ్యం మరియు ఇంగ్లీష్"},
    "TECH101": {"ml": "കോർ ടെക്നിക്കൽ & സിസ്റ്റം ഡിസൈൻ", "ta": "முக்கிய தொழில்நுட்பம் & அமைப்பு வடிவமைப்பு", "hi": "मुख्य तकनीक और सिस्टम डिज़ाइन", "kn": "ಕೋರ್ ಟೆಕ್ನಿಕಲ್ & ಸಿಸ್ಟಂ ವಿನ್ಯಾಸ", "te": "కోర్ టెక్నికల్ & సిస్టమ్ డిజైన్"},
    "CODE101": {"ml": "പ്രോഗ്രാമിംഗ് ചാലഞ്ഞഞ്ജറുകൾ", "ta": "நிரலாக்க சவால்கள்", "hi": "प्रोग्रामिंग चुनौतियाँ", "kn": "ಪ್ರೊಗ್ರಾಮಿಂಗ್ ಸವಾಲುಗಳು", "te": "ప్రోగ్రామింగ్ సవాళ్లు"},
    "QA-APTITUDE-3137": {"ml": "അപ്ടിയൂഡ്", "ta": "திறன்", "hi": "अभिरुचि", "kn": "ಅಭಿರುಚಿ", "te": "అప్టిట్యూడ్"},
    "QA-DBMS-57A3": {"ml": "ഡിബിഎംഎസ്", "ta": "DBMS", "hi": "डीबीएमएस", "kn": "ಡಿಬಿಎಂಎಸ್", "te": "డీబీఎమ్‌ఎస్"},
    "QA-JAVA-BFC4": {"ml": "ജാവ", "ta": "ஜாவா", "hi": "जावा", "kn": "ಜಾವ", "te": "జావా"},
}


def seed_subject_translations(db: Session, subjects: Iterable[Subject] | None = None) -> int:
    """Upsert the built-in subject names and return the number of subjects touched."""
    by_code = {subject.code: subject for subject in (subjects or db.scalars(select(Subject)).all())}
    touched = 0
    for code, translations in SUBJECT_NAME_TRANSLATIONS.items():
        subject = by_code.get(code)
        if subject is None:
            continue
        upsert_translations(
            db,
            model_cls=SubjectTranslation,
            parent_fk="subject_id",
            parent_id=subject.id,
            kind="subject",
            base_values={"name": subject.name, "description": subject.description},
            translations_payload={
                locale: {"name": localised_name} for locale, localised_name in translations.items()
            },
        )
        touched += 1
    db.flush()
    logger.info("Seeded localised names for %d subjects", touched)
    return touched


def main() -> None:
    """Apply the catalogue to an already-running database without reseeding questions."""
    db = SessionLocal()
    try:
        count = seed_subject_translations(db)
        db.commit()
        print(f"Updated {count} subjects with Malayalam, Tamil, Hindi, Kannada and Telugu names.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
