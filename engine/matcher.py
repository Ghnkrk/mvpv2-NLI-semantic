import re


def normalize_text(text: str) -> str:
    """Normalize input text: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_sentences(raw_text: str) -> list[str]:
    """
    Split raw text into sentences on period/newline boundaries.
    Returns cleaned sentences preserving original casing.
    """
    parts = re.split(r'[.\n]+', raw_text)
    sentences = [s.strip() for s in parts if s.strip()]
    return sentences


def compute_block_score(text: str, signals: list) -> tuple[float, list[str]]:
    """
    Compute the match score for a single evidence block.

    Score = min(1.0, matched_count / total_signal_count), rounded to 4 decimals.

    Returns:
        (score, matched_signals)
    """
    if not signals:
        return 0.0, []

    matched = []
    for signal in signals:
        if signal.lower() in text:
            matched.append(signal)

    score = min(1.0, len(matched) / len(signals))
    return round(score, 4), matched


def extract_snippets(sentences: list[str], signals: list) -> list[str]:
    """
    For each matched signal, find sentences containing it.
    Returns unique sentences as evidence snippets (case-insensitive match).
    """
    snippets = []
    seen = set()
    for signal in signals:
        sig_lower = signal.lower()
        for sentence in sentences:
            if sig_lower in sentence.lower() and sentence not in seen:
                snippets.append(sentence)
                seen.add(sentence)
    return snippets
