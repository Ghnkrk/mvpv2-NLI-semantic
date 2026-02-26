from engine.matcher import compute_block_score, extract_snippets


def evaluate_clause(clause: dict, text: str, sentences: list[str]) -> dict:
    """
    Evaluate a single clause against normalized text.

    Returns dict with: status, clause_score, block_scores, mandatory_failures,
    matched_evidence, matched_snippets, decision_trace.
    """
    evidence_blocks = clause["evidence_blocks"]
    params = clause["evaluation_params"]
    archetype = clause["archetype"]
    threshold = params.get("mandatory_threshold", 0.5)

    # --- Compute block scores ---
    block_results = {}
    matched_evidence = {}
    matched_snippets = {}
    clause_score = 0.0

    for name, block in evidence_blocks.items():
        score, matched_signals = compute_block_score(text, block["signals"])
        block_results[name] = score
        matched_evidence[name] = matched_signals
        matched_snippets[name] = extract_snippets(sentences, matched_signals)
        clause_score += score * block["weight"]

    clause_score = round(clause_score, 4)

    # --- Identify mandatory vs optional ---
    mandatory_names = [
        name for name, block in evidence_blocks.items()
        if block.get("mandatory", False)
    ]
    optional_names = [
        name for name, block in evidence_blocks.items()
        if not block.get("mandatory", False)
    ]

    # A mandatory block "fails" when it has ZERO signal matches.
    # Blocks with any match (score > 0) are considered present —
    # the semantic layer will later strengthen weak matches.
    mandatory_failures = [
        name for name in mandatory_names
        if block_results[name] == 0.0
    ]

    # Blocks below the threshold but with some evidence (used in traces)
    mandatory_weak = [
        name for name in mandatory_names
        if 0 < block_results[name] < threshold
    ]

    # --- Apply archetype logic ---
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
        "decision_trace": decision_trace,
    }


# -----------------------------------------------------------------------
# Archetype Dispatch
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

    mandatory_failures = blocks with zero signal matches (score == 0.0)
    mandatory_weak     = blocks with some matches but below threshold

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
# POLICY_PROCEDURE
# -----------------------------------------------------------------------

def _eval_policy_procedure(*, mandatory_names, mandatory_failures, mandatory_weak, clause_score, params, **_kw):
    overall = params.get("overall_compliance_threshold", 0.7)

    # All mandatory blocks have zero matches → NON_COMPLIANT
    if len(mandatory_failures) == len(mandatory_names) and mandatory_names:
        return (
            "NON_COMPLIANT",
            f"All {len(mandatory_names)} mandatory blocks have zero signal matches"
        )

    # Some mandatory blocks have zero matches → PARTIAL
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
# LIFECYCLE_MANAGEMENT
# -----------------------------------------------------------------------

def _eval_lifecycle_management(*, mandatory_names, mandatory_failures, mandatory_weak, params, **_kw):
    # No mandatory failures (zero-match) at all
    if not mandatory_failures:
        weak_note = f" (weak matches in: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "COMPLIANT",
            f"All mandatory blocks have signal matches{weak_note}"
        )

    # ≥2 blocks with zero matches → NON_COMPLIANT
    if len(mandatory_failures) >= 2:
        return (
            "NON_COMPLIANT",
            f"{len(mandatory_failures)} mandatory blocks have zero matches: "
            f"{', '.join(mandatory_failures)}"
        )

    # 1 block with zero matches → PARTIAL
    return (
        "PARTIAL",
        f"Mandatory block with no evidence: {mandatory_failures[0]}"
    )


# -----------------------------------------------------------------------
# MONITORING_IMPROVEMENT
# -----------------------------------------------------------------------

def _eval_monitoring_improvement(*, mandatory_names, mandatory_failures, mandatory_weak, block_results, params, **_kw):
    threshold = params.get("mandatory_threshold", 0.5)
    chain_required = params.get("chain_required", False)

    # First mandatory block is the indicator — zero match → NON_COMPLIANT
    if mandatory_names:
        indicator_name = mandatory_names[0]
        if block_results[indicator_name] == 0.0:
            return (
                "NON_COMPLIANT",
                f"Indicator block '{indicator_name}' has zero signal matches"
            )

    # Any mandatory block with zero matches → PARTIAL
    if mandatory_failures:
        return (
            "PARTIAL",
            f"Mandatory blocks with no evidence: {', '.join(mandatory_failures)}"
        )

    # Chain-required: blocks below threshold weaken the chain → PARTIAL
    if chain_required and mandatory_weak:
        return (
            "PARTIAL",
            f"Chain incomplete — weak evidence in: {', '.join(mandatory_weak)} "
            f"(below threshold {threshold})"
        )

    # All mandatory have sufficient evidence
    return (
        "COMPLIANT",
        f"All mandatory blocks have signal matches"
    )


# -----------------------------------------------------------------------
# HR_GOVERNANCE
# -----------------------------------------------------------------------

def _eval_hr_governance(*, mandatory_names, mandatory_failures, mandatory_weak, optional_names, block_results, clause_score, params, **_kw):
    # All mandatory blocks have zero matches → NON_COMPLIANT
    if len(mandatory_failures) == len(mandatory_names) and mandatory_names:
        return (
            "NON_COMPLIANT",
            f"All {len(mandatory_names)} mandatory blocks have zero signal matches"
        )

    # Some mandatory blocks have zero matches → PARTIAL
    if mandatory_failures:
        weak_note = f" (weak but present: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "PARTIAL",
            f"Mandatory blocks with no evidence: {', '.join(mandatory_failures)}{weak_note}"
        )

    # All mandatory pass — check optional blocks for zero matches
    optional_failures = [
        name for name in optional_names
        if block_results[name] == 0.0
    ]
    if optional_failures:
        return (
            "PARTIAL",
            f"All mandatory present but optional blocks missing: {', '.join(optional_failures)}"
        )

    # All blocks (mandatory + optional) have evidence → COMPLIANT
    weak_note = f" (weak matches in: {', '.join(mandatory_weak)})" if mandatory_weak else ""
    return (
        "COMPLIANT",
        f"All blocks have evidence; clause_score {clause_score}{weak_note}"
    )
