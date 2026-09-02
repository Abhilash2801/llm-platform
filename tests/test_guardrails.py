import pytest

from app.executor.guardrails import banned_words_check, max_length_check, run_output_guardrails
from app.schemas import GuardrailSpec


def test_banned_words_detects_phrase():
    result = banned_words_check("hello BANNED_PHRASE_42 there", ["BANNED_PHRASE_42"])
    assert result.passed is False


def test_max_length_fails_when_too_long():
    result = max_length_check("abcd", 3)
    assert result.passed is False


def test_run_output_guardrails_ok():
    spec = GuardrailSpec(output=["banned_words", "max_length"], banned_words=["nope"], max_length=100)
    assert run_output_guardrails("hello", spec).passed is True
