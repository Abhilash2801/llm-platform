from collections import Counter

from app.executor.strategies import pick_weighted_target
from app.schemas import Target


def test_weighted_split_within_tolerance():
    targets = [
        Target(provider="openai", model="gpt-4o-mini", weight=0.7),
        Target(provider="groq", model="llama-3.1-8b-instant", weight=0.3),
    ]
    counts = Counter(pick_weighted_target(targets).provider for _ in range(400))
    openai_share = counts["openai"] / 400
    assert 0.6 <= openai_share <= 0.8
