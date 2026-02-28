import os
from engine.text_utils import tokenize_and_stem, normalize_text

# Check for debug mode via environment variable
DEBUG_MODE = os.environ.get("NABH_DEBUG", "false").lower() == "true"

def split_sentences(raw_text: str) -> list[str]:
    """
    Split raw text into sentences on period/newline boundaries.
    Returns cleaned sentences preserving original casing.
    """
    import re
    parts = re.split(r'[.\n]+', raw_text)
    sentences = [s.strip() for s in parts if s.strip()]
    return sentences

def match_signal_to_sentence(signal: str, sentence: str, debug: bool = False) -> bool:
    """
    Check if a signal matches a sentence based on 0.6 token overlap ratio.
    """
    signal_tokens = tokenize_and_stem(signal)
    sentence_tokens = tokenize_and_stem(sentence)
    
    if not signal_tokens:
        return False
        
    overlap = set(signal_tokens) & set(sentence_tokens)
    overlap_ratio = len(overlap) / len(signal_tokens)
    
    is_match = overlap_ratio >= 0.6
    
    # Enable printing if either local or global debug flag is set
    if debug or DEBUG_MODE:
        print(f"--- Debug Match ---")
        print(f"Signal: {signal}")
        print(f"Signal tokens: {signal_tokens}")
        print(f"Sentence: {sentence.strip()[:100]}...") # Truncate long sentences for cleaner logs
        print(f"Sentence tokens: {sentence_tokens}")
        print(f"Overlap tokens: {list(overlap)}")
        print(f"Overlap ratio: {overlap_ratio:.4f}")
        print(f"Match accepted: {is_match}")
        
    return is_match

def compute_block_score(sentences: list[str], signals: list) -> tuple[float, list[str]]:
    """
    Compute the match score for a single evidence block.
    A signal matches if it meets the 0.6 token overlap threshold in any sentence.
    """
    if not signals:
        return 0.0, []

    matched = []
    for signal in signals:
        found = False
        for sentence in sentences:
            if match_signal_to_sentence(signal, sentence):
                found = True
                break
        if found:
            matched.append(signal)

    score = min(1.0, len(matched) / len(signals))
    return round(score, 4), matched

def extract_snippets(sentences: list[str], signals: list) -> list[str]:
    """
    For each matched signal, find sentences containing it using token overlap.
    """
    snippets = []
    seen = set()
    for signal in signals:
        for sentence in sentences:
            if sentence not in seen and match_signal_to_sentence(signal, sentence):
                snippets.append(sentence)
                seen.add(sentence)
    return snippets
