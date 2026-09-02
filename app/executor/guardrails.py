import re
from dataclasses import dataclass

from app.schemas import GuardrailSpec


@dataclass
class GuardrailResult:
    passed: bool
    reason: str | None = None


def banned_words_check(text: str, words: list[str]) -> GuardrailResult:
    lowered = text.lower()
    for word in words:
        if not word:
            continue
        pattern = re.compile(rf"\b{re.escape(word.lower())}\b")
        if pattern.search(lowered) or word.lower() in lowered:
            return GuardrailResult(False, f"banned word: {word}")
    return GuardrailResult(True)


def max_length_check(text: str, max_length: int) -> GuardrailResult:
    if len(text) > max_length:
        return GuardrailResult(False, f"response length {len(text)} exceeds {max_length}")
    return GuardrailResult(True)


def run_output_guardrails(text: str, spec: GuardrailSpec | None) -> GuardrailResult:
    if spec is None or not spec.output:
        return GuardrailResult(True)
    for name in spec.output:
        if name == "banned_words":
            result = banned_words_check(text, spec.banned_words)
        elif name == "max_length":
            result = max_length_check(text, spec.max_length)
        else:
            continue
        if not result.passed:
            return result
    return GuardrailResult(True)
