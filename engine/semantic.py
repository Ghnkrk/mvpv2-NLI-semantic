"""
Semantic evidence enhancement layer (Hybrid NLI Version).

Uses a Lexical Pre-Filter and a Natural Language Inference (NLI) Cross-Encoder
to determine if document sentences strictly entail compliance rule signals and
clause intent.
"""

import re
from sentence_transformers import CrossEncoder

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ENTAILMENT_THRESHOLD = 0.85   # Strict threshold for entailment (Requirement: >= 0.85)
ENTAILMENT_INDEX = 1          # NLI model index for 'entailment'

# Stop words for lexical filtering
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "when", "where", "how", "who", "which", "this", "that", "these", "those",
    "then", "just", "so", "than", "such", "both", "through", "about", "for",
    "is", "of", "while", "during", "to", "what", "with", "process", "procedure",
    "documented", "defined", "system", "plan", "management"
}

# Load model once globally (Cross-Encoder for NLI)
_model = CrossEncoder("cross-encoder/nli-deberta-v3-small")


def _tokenize(text: str) -> set[str]:
    """Tokenizer that lowercases, removes punctuation, filters stop words and words < 3 chars."""
    words = re.findall(r'\b[a-z]+\b', text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) >= 3}


def lexical_pre_filter(sentence: str, signal: str) -> bool:
    """
    Check if a sentence and signal have at least one meaningful keyword overlap.
    Returns True if overlap exists, False otherwise.
    """
    sent_tokens = _tokenize(sentence)
    signal_tokens = _tokenize(signal)
    
    # If the signal was completely stripped by filters, fallback to inclusion
    if not signal_tokens:
        return signal.lower() in sentence.lower()
        
    return len(sent_tokens.intersection(signal_tokens)) > 0


def semantic_match_block(
    sentences: list[str],
    signals: list[str],
    clause_intent: str,
    similarity_threshold: float = ENTAILMENT_THRESHOLD,
) -> tuple[float, list[str], dict]:
    """
    Compute semantic entailment using a two-stage hybrid filter.

    Stage 1: Lexical Filter
             Only sentences that share >=1 meaningful keyword with the signal are evaluated.
    Stage 2: Clause-Intent Grounded NLI
             Evaluate selected sentences against the clause intent.

    Returns:
        (semantic_score, matched_sentences, debug_context_dict)
    """
    if not signals or not sentences:
        return 0.0, [], {}

    matched_count = 0
    matched_sentences: list[str] = []
    seen: set[str] = set()
    
    # Debug context to return
    # we want to return the best raw scores for the block
    max_raw_entailment = 0.0
    lexical_passed_overall = False

    for signal in signals:
        valid_pairs = []
        valid_sentences = []
        
        # --- Stage 1: Lexical Pre-Filter ---
        for sentence in sentences:
            if lexical_pre_filter(sentence, signal):
                lexical_passed_overall = True
                valid_sentences.append(sentence)
                # --- Stage 4: Clause-Intent Grounding ---
                # Premise is the intent; Hypothesis is the sentence.
                valid_pairs.append([clause_intent, sentence])
                
        if not valid_pairs:
            continue

        # --- Stage 2: NLI Entailment (filtered scope) ---
        scores = _model.predict(valid_pairs, apply_softmax=True)
        
        # CrossEncoder.predict returns a 2D array if a list of pairs is passed.
        # Shape: (len(valid_pairs), num_labels)
        if len(valid_pairs) == 1 and scores.ndim == 1:
            entailment_scores = [scores[ENTAILMENT_INDEX]]
        elif scores.ndim == 2:
            entailment_scores = scores[:, ENTAILMENT_INDEX]
        else:
            # Fallback for unexpected shapes
            entailment_scores = [scores[1]] if scores.ndim == 1 else [scores[0][1]]
            
        # Find best match
        best_idx = max(range(len(entailment_scores)), key=entailment_scores.__getitem__)
        best_score = entailment_scores[best_idx]
        
        max_raw_entailment = max(max_raw_entailment, float(best_score))

        # Gating: Lexical Filter (already inside branch) AND Entailment Threshold
        if best_score >= similarity_threshold:
            matched_count += 1
            sentence = valid_sentences[best_idx]
            if sentence not in seen:
                matched_sentences.append(sentence)
                seen.add(sentence)

    semantic_score = matched_count / len(signals)
    debug_context = {
        "raw_entailment_score": round(max_raw_entailment, 4),
        "lexical_filter_passed": lexical_passed_overall
    }
    return round(semantic_score, 4), matched_sentences, debug_context
