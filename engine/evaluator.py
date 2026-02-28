from engine.matcher import compute_block_score, extract_snippets
from engine.semantic import semantic_match_block


def evaluate_clause(clause: dict, text: str, sentences: list[str]) -> dict:
    """
    Evaluate a single clause against normalized text.

    For each evidence block:
      1. Compute exact score via signal matching
      2. If exact_score < threshold → run semantic matching
      3. final_score = max(exact_score, semantic_score), capped at 1.0 (0.49 for semantic-only)
      4. Tracks semantic-only safeguard logic.
    """
    evidence_blocks = clause["evidence_blocks"]
    params = clause["evaluation_params"]
    archetype = clause["archetype"]
    intent = clause.get("intent", "")
    threshold = params.get("mandatory_threshold", 0.5)

    block_results = {}
    exact_scores = {}
    matched_evidence = {}
    matched_snippets = {}
    semantic_matches = {}
    semantic_only_blocks = []
    block_details = {}
    clause_score = 0.0

    for name, block in evidence_blocks.items():
        signals = block["signals"]

        # --- Step 1: Exact matching ---
        exact_score, exact_signals = compute_block_score(text, signals)
        exact_snippets = extract_snippets(sentences, exact_signals)

        exact_scores[name] = exact_score
        matched_evidence[name] = exact_signals
        matched_snippets[name] = exact_snippets

        # --- Step 2: Semantic enhancement ---
        semantic_score = 0.0
        semantic_sents = []
        semantic_used = False
        semantic_only = False
        debug_context = {}

        if exact_score < threshold:
            # Phase 4: Pass intent to semantic matching
            semantic_score, semantic_sents, debug_context = semantic_match_block(sentences, signals, clause_intent=intent)
            
            # Phase 3v2: Semantic Score Capping (0.49)
            if exact_score == 0.0:
                # If block is satisfied purely via semantic --> Cap at 0.49
                final_score = min(semantic_score, 0.49)
            else:
                # If exact_score > 0 --> Max combo but cap at 1.0
                final_score = min(max(exact_score, semantic_score), 1.0)
                
            semantic_used = (final_score > exact_score)
        else:
            final_score = exact_score

        # Phase 4 / 5 Trackers
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
            "lexical_filter_passed": debug_context.get("lexical_filter_passed", False),
            "raw_entailment_score": debug_context.get("raw_entailment_score", 0.0)
        }

        clause_score += final_score * block["weight"]

    clause_score = round(clause_score, 4)

    # Identifiers
    mandatory_names = [name for name, b in evidence_blocks.items() if b.get("mandatory", False)]
    optional_names = [name for name, b in evidence_blocks.items() if not b.get("mandatory", False)]

    # Mandatory logic ALWAYS from exact scores
    mandatory_failures = [name for name in mandatory_names if exact_scores[name] == 0.0]
    mandatory_weak = [name for name in mandatory_names if 0 < exact_scores[name] < threshold]

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
        semantic_only_blocks=semantic_only_blocks,       # Added for reporting
        semantic_matches=semantic_matches                # Added for reporting
    )

    # v2 Fix: Mandatory Must Have At Least One Exact Block
    if status == "COMPLIANT" and mandatory_names:
        # Check if ANY mandatory block has exact_score >= threshold
        has_strong_exact_mandatory = any((exact_scores[name] >= threshold) for name in mandatory_names)
        if not has_strong_exact_mandatory:
            status = "PARTIAL"
            decision_trace = "No mandatory block satisfied via exact evidence"

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
# Archetype Dispatch
# -----------------------------------------------------------------------

def _apply_archetype(*, archetype: str, **kwargs) -> tuple[str, str]:
    dispatch = {
        "POLICY_PROCEDURE": _eval_policy_procedure,
        "LIFECYCLE_MANAGEMENT": _eval_lifecycle_management,
        "MONITORING_IMPROVEMENT": _eval_monitoring_improvement,
        "HR_GOVERNANCE": _eval_hr_governance,
        "SAFETY_RISK_CONTROL": _eval_safety_risk_control, # Phase 1 fix
    }

    fn = dispatch.get(archetype)
    if fn is None:
        return "NON_COMPLIANT", f"Unknown archetype '{archetype}' — defaulting to NON_COMPLIANT"

    return fn(**kwargs)


# -----------------------------------------------------------------------
# Phase 6 Helper
# -----------------------------------------------------------------------
def _format_failure_msg(base_msg: str, failures: list, semantic_matches: dict) -> str:
    """Appends '(semantic evidence detected)' if any semantic sentences were found for the failures."""
    has_semantic = any(len(semantic_matches.get(f, [])) > 0 for f in failures)
    if has_semantic:
        return f"{base_msg} (semantic evidence detected)"
    return base_msg


# -----------------------------------------------------------------------
# SAFETY_RISK_CONTROL (Phase 1 Fix)
# -----------------------------------------------------------------------

def _eval_safety_risk_control(*, evidence_blocks, block_results, mandatory_names, mandatory_failures, mandatory_weak, clause_score, params, semantic_matches, **_kw):
    threshold = params.get("mandatory_threshold", 0.5)
    overall = params.get("overall_compliance_threshold", 0.7)
    
    # We must explicitly evaluate based on the archetype logic you provided:
    # failed = blocks where final_score < mandatory_threshold (using block_results)
    failed = [name for name in mandatory_names if block_results[name] < threshold]

    if len(failed) == len(mandatory_names) and mandatory_names:
        return "NON_COMPLIANT", _format_failure_msg("Mandatory blocks lack sufficient exact evidence", failed, semantic_matches)
        
    if len(failed) > 0:
        return "PARTIAL", _format_failure_msg(f"Mandatory blocks below threshold: {', '.join(failed)}", failed, semantic_matches)
        
    if clause_score >= overall:
        return "COMPLIANT", f"Clause score {clause_score} >= {overall}"
    else:
        return "PARTIAL", f"Clause score {clause_score} < {overall}"


# -----------------------------------------------------------------------
# POLICY_PROCEDURE
# -----------------------------------------------------------------------

def _eval_policy_procedure(*, mandatory_names, mandatory_failures, mandatory_weak, clause_score, params, semantic_matches, **_kw):
    overall = params.get("overall_compliance_threshold", 0.7)

    if len(mandatory_failures) == len(mandatory_names) and mandatory_names:
        return (
            "NON_COMPLIANT",
            _format_failure_msg(f"Mandatory blocks lack sufficient exact evidence", mandatory_failures, semantic_matches)
        )

    if mandatory_failures:
        weak_note = f" (weak but present: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "PARTIAL",
            _format_failure_msg(f"Mandatory blocks with no exact evidence: {', '.join(mandatory_failures)}{weak_note}", mandatory_failures, semantic_matches)
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

def _eval_lifecycle_management(*, mandatory_names, mandatory_failures, mandatory_weak, params, semantic_matches, **_kw):
    if not mandatory_failures:
        weak_note = f" (weak matches in: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "COMPLIANT",
            f"All mandatory blocks have signal matches{weak_note}"
        )

    if len(mandatory_failures) >= 2:
        return (
            "NON_COMPLIANT",
            _format_failure_msg("Mandatory blocks lack sufficient exact evidence", mandatory_failures, semantic_matches)
        )

    return (
        "PARTIAL",
        _format_failure_msg(f"Mandatory block with no exact evidence: {mandatory_failures[0]}", mandatory_failures, semantic_matches)
    )


# -----------------------------------------------------------------------
# MONITORING_IMPROVEMENT
# -----------------------------------------------------------------------

def _eval_monitoring_improvement(*, mandatory_names, mandatory_failures, mandatory_weak, block_results, params, semantic_matches, **_kw):
    threshold = params.get("mandatory_threshold", 0.5)
    chain_required = params.get("chain_required", False)

    if mandatory_names:
        indicator_name = mandatory_names[0]
        if block_results[indicator_name] == 0.0:
            return (
                "NON_COMPLIANT",
                _format_failure_msg(f"Indicator block '{indicator_name}' lacks sufficient exact evidence", [indicator_name], semantic_matches)
            )

    if mandatory_failures:
        return (
            "PARTIAL",
            _format_failure_msg(f"Mandatory blocks with no exact evidence: {', '.join(mandatory_failures)}", mandatory_failures, semantic_matches)
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
# HR_GOVERNANCE
# -----------------------------------------------------------------------

def _eval_hr_governance(*, mandatory_names, mandatory_failures, mandatory_weak, optional_names, block_results, clause_score, params, semantic_matches, **_kw):
    if len(mandatory_failures) == len(mandatory_names) and mandatory_names:
        return (
            "NON_COMPLIANT",
            _format_failure_msg(f"Mandatory blocks lack sufficient exact evidence", mandatory_failures, semantic_matches)
        )

    if mandatory_failures:
        weak_note = f" (weak but present: {', '.join(mandatory_weak)})" if mandatory_weak else ""
        return (
            "PARTIAL",
            _format_failure_msg(f"Mandatory blocks with no exact evidence: {', '.join(mandatory_failures)}{weak_note}", mandatory_failures, semantic_matches)
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
