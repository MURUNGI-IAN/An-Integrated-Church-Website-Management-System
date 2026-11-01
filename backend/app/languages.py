DEFAULT_LANGUAGE = "en"
PHASE_1_LANGUAGES = ("en", "lg", "nyn", "rw")
PHASE_2_LANGUAGES = ("sw",)
ALL_LANGUAGES = PHASE_1_LANGUAGES + PHASE_2_LANGUAGES
LANGUAGE_NAMES = {
    "en": "English",
    "lg": "Luganda",
    "nyn": "Runyankole",
    "rw": "Kinyarwanda",
    "sw": "Swahili",
}
CAPTION_LANGUAGES = PHASE_1_LANGUAGES
CAPTION_FORMATS = ("srt", "vtt")
TRANSLATION_STATUSES = ("draft", "pending_review", "approved", "rejected")
CAPTION_STATUSES = ("draft", "pending_review", "approved", "rejected")
CONTENT_SOURCES = ("human", "ai_draft")


def is_phase_1_language(language: str) -> bool:
    return language in PHASE_1_LANGUAGES


def language_name(language: str) -> str:
    return LANGUAGE_NAMES.get(language, language)
