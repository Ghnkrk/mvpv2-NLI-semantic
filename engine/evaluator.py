from engine.matcher import compute_block_score, extract_snippets


def evaluate_clause(clause: dict, text: str, sentences: list[str]) -> dict:
    """
    Evaluate a single clause against normalized text.

    Args:
        clause: clause definition from rules.json
        text: normalized full text for scoring
        sentences: list of raw sentences for snippet extraction

    Returns dict with: status, clause_score, block_scores, matched_evidence,
                       matched_snippets.
    """
    evidence_blocks = clause["evidence_blocks"]
    params = clause["evaluation_params"]
    archetype = clause["archetype"]

    block_results = {}
    matched_evidence = {}
    matched_snippets = {}
    clause_score = 0.0

    for name, block in evidence_blocks.items():
        score, matched_signals = compute_block_score(text, block["signals"])
        block_results[name] = round(score, 4)
        matched_evidence[name] = matched_signals
        matched_snippets[name] = extract_snippets(sentences, matched_signals)
        clause_score += score * block["weight"]

    status = apply_archetype_logic(
        archetype,
        evidence_blocks,
        block_results,
        clause_score,
        params,
    )

    return {
        "status": status,
        "clause_score": round(clause_score, 4),
        "block_scores": block_results,
        "matched_evidence": matched_evidence,
        "matched_snippets": matched_snippets,
    }


def apply_archetype_logic(
    archetype: str,
    evidence_blocks: dict,
    block_results: dict,
    clause_score: float,
    params: dict,
) -> str:
    """
    Determine compliance status based on archetype-specific logic.

    Uses the mandatory flag from evidence_blocks to distinguish mandatory
    vs optional blocks. Only mandatory block failures drive status downward.

    Returns one of: COMPLIANT, PARTIAL, NON_COMPLIANT.
    """
    threshold = params.get("mandatory_threshold", 0.5)
    overall_threshold = params.get("overall_compliance_threshold", 0.7)

    # Separate mandatory vs optional blocks
    mandatory_names = [
        name for name, block in evidence_blocks.items()
        if block.get("mandatory", False)
    ]
    mandatory_scores = {
        name: block_results[name] for name in mandatory_names
    }
    mandatory_failures = [
        name for name, score in mandatory_scores.items()
        if score < threshold
    ]

    # -----------------------------------------------------------
    # POLICY_PROCEDURE
    # -----------------------------------------------------------
    if archetype == "POLICY_PROCEDURE":
        if len(mandatory_failures) == len(mandatory_scores):
            return "NON_COMPLIANT"

        if mandatory_failures:
            return "PARTIAL"

        if clause_score >= overall_threshold:
            return "COMPLIANT"

        return "PARTIAL"

    # -----------------------------------------------------------
    # LIFECYCLE_MANAGEMENT
    # -----------------------------------------------------------
    if archetype == "LIFECYCLE_MANAGEMENT":
        if len(mandatory_failures) == 0:
            return "COMPLIANT"
        if len(mandatory_failures) == 1:
            return "PARTIAL"
        return "NON_COMPLIANT"

    # -----------------------------------------------------------
    # MONITORING_IMPROVEMENT
    # -----------------------------------------------------------
    if archetype == "MONITORING_IMPROVEMENT":
        # First mandatory block is the "indicator" — must pass
        if mandatory_names:
            indicator_name = mandatory_names[0]
            if mandatory_scores.get(indicator_name, 0) < threshold:
                return "NON_COMPLIANT"

        if mandatory_failures:
            return "PARTIAL"

        return "COMPLIANT"

    # -----------------------------------------------------------
    # HR_GOVERNANCE
    # -----------------------------------------------------------
    if archetype == "HR_GOVERNANCE":
        if len(mandatory_failures) == len(mandatory_scores):
            return "NON_COMPLIANT"

        if mandatory_failures:
            return "PARTIAL"

        if clause_score >= overall_threshold:
            return "COMPLIANT"

        return "PARTIAL"

    # Fallback for unknown archetypes
    return "NON_COMPLIANT"
