import argparse
import os
import sys
import json
from datetime import datetime

from engine.loader import load_rules
from engine.matcher import normalize_text, split_sentences
from engine.evaluator import evaluate_clause
from engine.pdf_reader import extract_text_from_pdf, get_pdfs_from_folder
from engine.report import generate_report, generate_pdf_report
from engine.llm_suggester import generate_suggestions


INPUT_FOLDER = "checkPdf"
OUTPUT_FOLDER = "reports"
RULES_PATH = "rules.json"


def run_engine(pdf_path: str) -> dict:
    """Run the compliance engine on a single PDF and return results."""
    rules = load_rules(RULES_PATH)
    raw_text = extract_text_from_pdf(pdf_path)

    if not raw_text.strip():
        print(f"  ⚠  No text extracted from {pdf_path}")
        return {}

    text = normalize_text(raw_text)
    sentences = split_sentences(raw_text)

    results = {}
    for clause_id, clause in rules.items():
        results[clause_id] = evaluate_clause(clause, text, sentences)

    return results


def print_debug(results: dict, filename: str):
    """Print detailed evaluation trace with exact, semantic, and NLI enforcement breakdown."""
    print(f"\n{'='*60}")
    print(f"  DEBUG TRACE — {filename}")
    print(f"{'='*60}")

    for clause_id, r in results.items():
        status = r["status"]
        print(f"\n{clause_id}:")
        print(f"  Clause score:       {r['clause_score']}")
        print(f"  Mandatory failures: {r['mandatory_failures'] or '(none)'}")
        print(f"  Status:             {status}")
        print(f"  Reason:             {r['decision_trace']}")

        sem_only = r.get("semantic_only_blocks", [])
        if sem_only:
            print(f"  ⚠ Semantic-only:   {sem_only}")

        # Per-block detail
        details = r.get("block_details", {})
        for block_name in r["block_scores"]:
            d = details.get(block_name, {})
            exact = d.get("exact_score", r["block_scores"][block_name])
            semantic = d.get("semantic_score", 0.0)
            final = d.get("final_score", r["block_scores"][block_name])
            used = d.get("semantic_used", False)
            only = d.get("semantic_only", False)
            
            # Since semantic is threshold filtered >= 0.8, if semantic > 0 then lexical & entailment passed.
            lexical_pass = "Yes" if semantic > 0 else "No"
            entail = f"{semantic} (cap enforced)" if semantic > 0 else "0.0"

            exact_signals = r["matched_evidence"].get(block_name, [])
            sem_sents = r.get("semantic_matches", {}).get(block_name, [])

            flag = ""
            if only:
                flag = " [SEMANTIC-ONLY]"
            elif used:
                flag = " [SEMANTIC-ENHANCED]"

            print(f"    {block_name}:{flag}")
            print(f"      exact_score:           {exact}  (signals={exact_signals})")
            print(f"      semantic_raw_score:    {semantic}  (sentences={len(sem_sents)})")
            
            # Show capped value specifically in debug (v2 requirement)
            capped_sem = min(semantic, 0.49) if exact == 0.0 else semantic
            print(f"      semantic_capped_score: {capped_sem}")
            
            print(f"      lexical_filter_passed: {d.get('lexical_filter_passed', False)}")
            print(f"      entailment_score:      {d.get('raw_entailment_score', 0.0)}")
            print(f"      final_score:           {final}")

    print(f"\n{'='*60}\n")


def main():
    """Process provided PDFs or all PDFs in checkPdf/ and generate gap reports in reports/."""
    parser = argparse.ArgumentParser(description="NABH Compliance Engine")
    parser.add_argument("pdf_paths", nargs="*", help="Path(s) to PDF file(s) to process")
    parser.add_argument("--debug", action="store_true", help="Print evaluation trace")
    args = parser.parse_args()

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    if args.pdf_paths:
        pdf_files = [p for p in args.pdf_paths if os.path.exists(p)]
        missing = [p for p in args.pdf_paths if not os.path.exists(p)]
        for p in missing:
            print(f"  ⚠  File not found: {p}")
        if not pdf_files:
            print("No valid PDF files provided. Exiting.")
            return
        print(f"Processing {len(pdf_files)} specified PDF(s)...\n")
    else:
        pdf_files = get_pdfs_from_folder(INPUT_FOLDER)
        print(f"Found {len(pdf_files)} PDF(s) in {INPUT_FOLDER}/\n")

    if not pdf_files:
        print(f"No PDF files found in {INPUT_FOLDER}/. Exiting.")
        return

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        stem = os.path.splitext(filename)[0]

        print(f"▶ Processing: {filename}")

        results = run_engine(pdf_path)

        if not results:
            continue

        # Debug trace (optional)
        if args.debug:
            print_debug(results, filename)

        # JSON report
        report_json_str = generate_report(results)
        report_data = json.loads(report_json_str)

        # Generate LLM Suggestions (Phases 6 & 8)
        print(f"  ✨ Generating AI suggestions...")
        suggestions = generate_suggestions(report_data)
        report_data["llm_suggestions"] = suggestions

        # Re-serialize with suggestions
        final_json_str = json.dumps(report_data, indent=2)
        
        json_out = os.path.join(OUTPUT_FOLDER, f"{stem}_report.json")
        with open(json_out, "w") as f:
            f.write(final_json_str)
        print(f"  ✓ JSON report → {json_out}")

        # PDF report
        pdf_out = os.path.join(OUTPUT_FOLDER, f"{stem}_report.pdf")
        generate_pdf_report(results, filename, pdf_out)
        print(f"  ✓ PDF report  → {pdf_out}")

        print()

    print("Done.")


if __name__ == "__main__":
    main()
