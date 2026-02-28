import os
from engine.loader import load_rules
from engine.matcher import normalize_text, split_sentences
from engine.evaluator import evaluate_clause


def test_generic_document():
    """
    Stress test for Semantic Stabilization v2.
    Tests generic text to ensure semantics (NLI + Lexical) do not hallucinate compliance.
    """
    rules = load_rules("rules.json")
    
    # Generic text provided by user requirements
    raw_text = "Policies are documented and reviewed annually."
    
    text = normalize_text(raw_text)
    sentences = split_sentences(raw_text)
    
    print("\n" + "="*60)
    print("  GENERIC DOCUMENT STRESS TEST")
    print("  Text: 'Policies are documented and reviewed annually.'")
    print("="*60 + "\n")
    
    all_non_compliant = True
    
    for clause_id, clause in rules.items():
        result = evaluate_clause(clause, text, sentences)
        status = result["status"]
        
        if status != "NON_COMPLIANT":
            all_non_compliant = False
            print(f"❌ FAIL: {clause_id} evaluated to {status} instead of NON_COMPLIANT.")
            print(f"   Trace: {result['decision_trace']}")
            print(f"   Final Clause score: {result['clause_score']}")
            
            # Print breakdown
            for b_name in result["block_scores"]:
                print(f"     -> Block '{b_name}' final: {result['block_scores'][b_name]} "
                      f"(Exact: {result['block_details'][b_name]['exact_score']}, "
                      f"Semantic: {result['block_details'][b_name]['semantic_score']})")
        else:
            print(f"✅ PASS: {clause_id} correctly evaluated to NON_COMPLIANT.")
            
    print("\n" + "="*60)
    if all_non_compliant:
        print("🎉 STRESS TEST SUCCESS: Generic document perfectly rejected.")
        return 0
    else:
        print("🚨 STRESS TEST FAILED: Over-permissive entailment detected.")
        print("   Recommendation: Raise ENTAILMENT_THRESHOLD to 0.85")
        return 1

if __name__ == "__main__":
    exit(test_generic_document())
