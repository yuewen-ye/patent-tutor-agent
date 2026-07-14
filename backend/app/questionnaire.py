from __future__ import annotations

from pathlib import Path

_QUESTIONNAIRE_PATH = Path(__file__).resolve().parent / "assets" / "onboarding-questionnaire.md"


def onboarding_questionnaire() -> dict[str, str]:
    return {
        "id": "patent-tutor-onboarding",
        "version": "1.0.0",
        "content_type": "text/markdown",
        "markdown": _QUESTIONNAIRE_PATH.read_text(encoding="utf-8"),
    }
