import re


def normalize_text(text: str) -> str:
    """Normalize input text: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def split_sentences(raw_text: str) -> list[str]:
    """
    Split raw text into sentences on period boundaries.
    Returns lowercased sentences for matching.
    """
    # Split on period, question mark, or newline boundaries
    parts = re.split(r'[.\n]+', raw_text)
    sentences = [s.strip() for s in parts if s.strip()]
    return sentences


def compute_block_score(text: str, signals: list) -> tuple[float, list[str]]:
    """
    Compute the match score for a single evidence block.

    Returns:
        (score, matched_signals) — score is fraction of signals found,
        matched_signals lists which signals were detected.
    """
    if not signals:
        return 0.0, []

    matched = []
    for signal in signals:
        if signal.lower() in text:
            matched.append(signal)

    score = len(matched) / len(signals)
    return score, matched


def extract_snippets(sentences: list[str], signals: list) -> list[str]:
    """
    For each signal, find sentences containing it and return as evidence snippets.
    Sentences are matched case-insensitively.
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
