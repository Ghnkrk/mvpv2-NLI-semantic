"""
Semantic evidence enhancement layer.

Uses sentence-transformers to find paraphrased / semantically similar
evidence that exact keyword matching would miss.

The semantic layer ONLY increases block scores — it never decreases them
and never overrides mandatory failure logic.
"""

from sentence_transformers import SentenceTransformer, util

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SIMILARITY_THRESHOLD = 0.75   # Do NOT go below 0.7

# Load model once globally
_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def semantic_match_block(
    sentences: list[str],
    signals: list[str],
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> tuple[float, list[str]]:
    """
    Compute semantic similarity between signals and document sentences.

    For each signal:
        - Compute cosine similarity against every sentence.
        - If best similarity >= similarity_threshold → count as match,
          store the matched sentence.

    Returns:
        (semantic_score, matched_sentences)

        semantic_score = matched_count / len(signals)
        matched_sentences = list of unique sentences that matched
    """
    if not signals or not sentences:
        return 0.0, []

    signal_embeddings = _model.encode(signals, convert_to_tensor=True)
    sentence_embeddings = _model.encode(sentences, convert_to_tensor=True)

    # cosine_scores shape: (len(signals), len(sentences))
    cosine_scores = util.cos_sim(signal_embeddings, sentence_embeddings)

    matched_count = 0
    matched_sentences: list[str] = []
    seen: set[str] = set()

    for i, signal in enumerate(signals):
        best_score = cosine_scores[i].max().item()
        if best_score >= similarity_threshold:
            matched_count += 1
            best_idx = cosine_scores[i].argmax().item()
            sentence = sentences[best_idx]
            if sentence not in seen:
                matched_sentences.append(sentence)
                seen.add(sentence)

    semantic_score = matched_count / len(signals)
    return round(semantic_score, 4), matched_sentences
