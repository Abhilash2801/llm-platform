# Approximate USD per 1K tokens (input, output). Used for demo cost estimates.
RATES_PER_1K: dict[tuple[str, str], tuple[float, float]] = {
    ("openai", "gpt-4o-mini"): (0.00015, 0.00060),
    ("openai", "gpt-4.1-nano"): (0.00010, 0.00040),
    ("groq", "llama-3.1-8b-instant"): (0.00005, 0.00008),
    ("groq", "llama-3.3-70b-versatile"): (0.00059, 0.00079),
}

DEFAULT_RATE = (0.00020, 0.00060)


def estimate_cost_usd(provider: str | None, model: str | None, tokens_in: int, tokens_out: int) -> float:
    in_rate, out_rate = RATES_PER_1K.get((provider or "", model or ""), DEFAULT_RATE)
    return round((tokens_in / 1000.0) * in_rate + (tokens_out / 1000.0) * out_rate, 6)
