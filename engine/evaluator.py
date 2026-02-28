from engine.matcher import compute_block_score, extract_snippets
from engine.semantic import semantic_match_block


def evaluate_clause(clause: dict, text: str, sentences: list[str]) -> dict:
    """
    Evaluate a single clause against normalized text.

    For each evidence block:
      1. Compute exact score via signal matching
      2. If exact_score < threshold → run semantic matching
      3. final_score = max(exact_score, semantic_score), capped at 1.0
      4. Track semantic_used and semantic_only flags

    Mandatory failures are ALWAYS computed from exact scores only.
    Archetype logic is NOT modified.
    """
    evidence_blocks = clause["evidence_blocks"]
    params = clause["evaluation_params"]
    archetype = clause["archetype"]
    threshold = params.get("mandatory_threshold", 0.5)

    # --- Compute block scores ---
    block_results = {}          # final scores (exact or enhanced)
    exact_scores = {}           # exact-only scores (for mandatory logic)
    matched_evidence = {}       # exact matched signals
    matched_snippets = {}       # exact snippets
    semantic_matches = {}       # semantic-only snippets (separate)
    semantic_only_blocks = []   # blocks satisfied ONLY via semantic
    block_details = {}          # per-block debug info
    clause_score = 0.0

    for name, block in evidence_blocks.items():
        signals = block["signals"]

        # --- Step 1: Exact matching ---
        exact_score, exact_signals = compute_block_score(text, signals)
        exact_snippets = extract_snippets(sentences, exact_signals)

        exact_scores[name] = exact_score
        matched_evidence[name] = exact_signals
        matched_snippets[name] = exact_snippets

        # --- Step 2: Semantic enhancement (only if exact is below threshold) ---
        semantic_score = 0.0
        semantic_sents = []
        semantic_used = False
        semantic_only = False

        if exact_score < threshold:
            semantic_score, semantic_sents = semantic_match_block(sentences, signals)
            final_score = max(exact_score, semantic_score)
            semantic_used = (semantic_score > exact_score)
        else:
            final_score = exact_score

        final_score = min(round(final_score, 4), 1.0)

        # --- Step 3: Semantic-only safeguard (Phase 4) ---
        if exact_score == 0.0 and semantic_score > 0 and block.get("mandatory", False):
            semantic_only = True

        block_results[name] = final_score
        semantic_matches[name] = semantic_sents if semantic_used else []
        if semantic_only:
            semantic_only_blocks.append(name)

        block_details[name] = {
            "exact_score": exact_score,
            "semantic_score": semantic_score,
            "final_score": final_score,
            "semantic_used": semantic_used,
            "semantic_only": semantic_only,
        }

        clause_score += final_score * block["weight"]

    clause_score = round(clause_score, 4)

    # --- Identify mandatory vs optional (ALWAYS from exact scores) ---
    mandatory_names = [
        name for name, block in evidence_blocks.items()
        if block.get("mandatory", False)
    ]
    optional_names = [
        name for name, block in evidence_blocks.items()
        if not block.get("mandatory", False)
    ]

    # Mandatory failure = zero EXACT matches (semantic does NOT rescue this)
    mandatory_failures = [
        name for name in mandatory_names
        if exact_scores[name] == 0.0
    ]

    # Blocks below threshold but with some exact evidence
    mandatory_weak = [
        name for name in mandatory_names
        if 0 < exact_scores[name] < threshold
    ]

    # --- Apply archetype logic (UNCHANGED) ---
    status, decision_trace = _apply_archetype(
        archetype=archetype,
        evidence_blocks=evidence_blocks,
        block_results=block_results,
        mandatory_names=mandatory_names,
        mandatory_failures=mandatory_failures,
        mandatory_weak=mandatory_weak,
        optional_names=optional_names,
        clause_score=clause_score,
        params=params,
    )

    return {
        "status": status,
        "clause_score": clause_score,
        "block_scores": block_results,
        "mandatory_failures": mandatory_failures,
        "matched_evidence": matched_evidence,
        "matched_snippets": matched_snippets,
        "semantic_matches": semantic_matches,
        "semantic_only_blocks": semantic_only_blocks,
        "block_details": block_details,
        "decision_trace": decision_trace,
    }


# -----------------------------------------------------------------------
# Archetype Dispatch  (COMPLETELY UNCHANGED)
# -----------------------------------------------------------------------

def _apply_archetype(
    *,
    archetype: str,
    evidence_blocks: dict,
    block_results: dict,
    mandatory_names: list,
    mandatory_failures: list,
    mandatory_weak: list,
    optional_names: list,
    clause_score: float,
    params: dict,
) -> tuple[str, str]:
    """
    Route to the correct archetype evaluator.

    mandatory_failures = blocks with zero EXACT signal matches (score == 0.0)
    mandatory_weak     = blocks with some exact matches but below threshold

    Returns (status, decision_trace).
    """
    dispatch = {
        "POLICY_PROCEDURE": _eval_policy_procedure,
        "LIFECYCLE_MANAGEMENT": _eval_lifecycle_management,
        "MONITORING_IMPROVEMENT": _eval_monitoring_improvement,
        "HR_GOVERNANCE": _eval_hr_governance,
    }

    fn = dispatch.get(archetype)
    if fn is None:
        return "NON_COMPLIANT", f"Unknown archetype '{archetype}' — defaulting to NON_COMPLIANT"

    return fn(
        evidence_blocks=evidence_blocks,
        block_results=block_results,
        mandatory_names=mandatory_names,
        mandatory_failures=mandatory_failures,
        mandatory_weak=mandatory_weak,
        optional_names=optional_names,
        clause_score=clause_score,
        params=params,
    )


# -----------------------------------------------------------------------
# POLICY_PROCEDURE  (UNCHANGED)
# -----------------------------------------------------------------------

def _eval_policy_procedure(*, mandatory_names, mandatory_failures, mandatory_weak, clause_score, params, **_kw):
    overall = params.get("overall_compliance_threshold", 0.7)

    if len(mandatory_failures) == len(mandatory_names) and mandatory_names:
        return (
            "NON_COMPLIANT",
            f"All {len(mandatory_names)} mandatory blocks lack sufficient exact evidence"
        )

    if mandatory_failures:
        weak_note = f" (weak but present: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "PARTIAL",
            f"Mandatory blocks with no evidence: {', '.join(mandatory_failures)}{weak_note}"
        )

    if clause_score >= overall:
        weak_note = f" (weak matches in: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "COMPLIANT",
            f"All mandatory blocks have evidence; clause_score {clause_score} >= {overall}{weak_note}"
        )

    return (
        "PARTIAL",
        f"All mandatory blocks have evidence but clause_score {clause_score} < {overall}"
    )


# -----------------------------------------------------------------------
# LIFECYCLE_MANAGEMENT  (UNCHANGED)
# -----------------------------------------------------------------------

def _eval_lifecycle_management(*, mandatory_names, mandatory_failures, mandatory_weak, params, **_kw):
    if not mandatory_failures:
        weak_note = f" (weak matches in: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "COMPLIANT",
            f"All mandatory blocks have signal matches{weak_note}"
        )

    if len(mandatory_failures) >= 2:
        return (
            "NON_COMPLIANT",
            f"{len(mandatory_failures)} mandatory blocks lack sufficient exact evidence: "
            f"{', '.join(mandatory_failures)}"
        )

    return (
        "PARTIAL",
        f"Mandatory block with no evidence: {mandatory_failures[0]}"
    )


# -----------------------------------------------------------------------
# MONITORING_IMPROVEMENT  (UNCHANGED)
# -----------------------------------------------------------------------

def _eval_monitoring_improvement(*, mandatory_names, mandatory_failures, mandatory_weak, block_results, params, **_kw):
    threshold = params.get("mandatory_threshold", 0.5)
    chain_required = params.get("chain_required", False)

    if mandatory_names:
        indicator_name = mandatory_names[0]
        if block_results[indicator_name] == 0.0:
            return (
                "NON_COMPLIANT",
                f"Indicator block '{indicator_name}' lacks sufficient exact evidence"
            )

    if mandatory_failures:
        return (
            "PARTIAL",
            f"Mandatory blocks with no evidence: {', '.join(mandatory_failures)}"
        )

    if chain_required and mandatory_weak:
        return (
            "PARTIAL",
            f"Chain incomplete — weak evidence in: {', '.join(mandatory_weak)} "
            f"(below threshold {threshold})"
        )

    return (
        "COMPLIANT",
        f"All mandatory blocks have signal matches"
    )


# -----------------------------------------------------------------------
# HR_GOVERNANCE  (UNCHANGED)
# -----------------------------------------------------------------------

def _eval_hr_governance(*, mandatory_names, mandatory_failures, mandatory_weak, optional_names, block_results, clause_score, params, **_kw):
    if len(mandatory_failures) == len(mandatory_names) and mandatory_names:
        return (
            "NON_COMPLIANT",
            f"All {len(mandatory_names)} mandatory blocks lack sufficient exact evidence"
        )

    if mandatory_failures:
        weak_note = f" (weak but present: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "PARTIAL",
            f"Mandatory blocks with no evidence: {', '.join(mandatory_failures)}{weak_note}"
        )

    optional_failures = [
        name for name in optional_names
        if block_results[name] == 0.0
    ]
    if optional_failures:
        return (
            "PARTIAL",
            f"All mandatory present but optional blocks missing: {', '.join(optional_failures)}"
        )

    weak_note = f" (weak matches in: {', '.join(mandatory_weak)})" if mandatory_weak else ""
    return (
        "COMPLIANT",
        f"All blocks have evidence; clause_score {clause_score}{weak_note}"
    )
